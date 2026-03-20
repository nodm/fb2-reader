# FB2 to MP3 Conversion Pipeline — Architecture

## 1. Introduction

This document describes the software architecture and implementation details for the FB2-to-MP3
conversion pipeline. It is derived from the requirements specified in
[`docs/requirements.md`](./requirements.md) and is intended to guide development of the system.

The pipeline converts `.fb2` (FictionBook 2) eBook files into `.mp3` audiobook files using
local, fully offline, GPU-accelerated text-to-speech synthesis via **XTTS v2** (Coqui TTS).

---

## 2. Repository Layout

```
fb2-reader/
├── docs/
│   ├── requirements.md
│   └── architecture.md          # this document
├── src/
│   └── fb2mp3/
│       ├── __init__.py
│       ├── cli.py               # CLI entry-point (argparse / typer)
│       ├── pipeline.py          # Orchestrator: wires all stages together
│       ├── fb2_parser.py        # Stage 1 — FB2 Parser
│       ├── text_cleaner.py      # Stage 2 — Text Cleaner
│       ├── chunker.py           # Stage 3 — Sentence Chunker
│       ├── tts_engine.py        # Stage 4 — TTS Engine (XTTS v2)
│       ├── audio_processor.py   # Stage 5 — Audio Post-Processor
│       ├── audio_exporter.py    # Stage 6 — Audio Exporter
│       └── models.py            # Shared data models / dataclasses
├── tests/
│   ├── conftest.py
│   ├── test_fb2_parser.py
│   ├── test_text_cleaner.py
│   ├── test_chunker.py
│   ├── test_tts_engine.py
│   ├── test_audio_processor.py
│   └── test_audio_exporter.py
├── pyproject.toml               # Project metadata and dependencies
└── README.md
```

---

## 3. Shared Data Models

File: `src/fb2mp3/models.py`

```python
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BookMetadata:
    """Metadata extracted from an FB2 file's <description> block."""
    title: str
    author: str
    language: str                # e.g. "en", "uk", "ru"


@dataclass
class TextBlock:
    """A single addressable unit of text within the book."""
    chapter_index: int           # 0-based chapter number
    chapter_title: Optional[str] # human-readable chapter heading
    text: str                    # cleaned prose text


@dataclass
class ParsedBook:
    """Output of Stage 1 (FB2 Parser)."""
    metadata: BookMetadata
    blocks: List[TextBlock]      # ordered list of all text blocks


@dataclass
class Chunk:
    """A single TTS-ready text fragment produced by Stage 3."""
    chapter_index: int
    chapter_title: Optional[str]
    index: int                   # position within the chapter
    text: str                    # ≤ 250 characters
```

---

## 4. Pipeline Orchestrator

File: `src/fb2mp3/pipeline.py`

The `Pipeline` class owns and sequences all six stages. It accepts a `PipelineConfig` object and
exposes a single `run()` method.

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class PipelineConfig:
    input_path: str              # path to input .fb2 file
    output_path: Optional[str]   # explicit output path; None → derive from title
    lang: str                    # "en" | "uk" | "ru"
    speaker: Optional[str]       # built-in XTTS v2 speaker name
    voice: Optional[str]         # path to reference WAV for voice cloning
    split_chapters: bool         # produce one MP3 per chapter
    device: str                  # "cuda" (default) or "cpu"


class Pipeline:
    def __init__(self, config: PipelineConfig) -> None: ...
    def run(self) -> None: ...
```

### 4.1 Stage Invocation Sequence

```
FB2 file
   │
   ▼
[Stage 1] FB2Parser.parse(path) → ParsedBook
   │
   ▼
[Stage 2] TextCleaner.clean(book) → ParsedBook   (mutates TextBlock.text in-place)
   │
   ▼
[Stage 3] Chunker.chunk(book) → List[Chunk]
   │
   ▼
[Stage 4] TTSEngine.synthesize(chunks, config) → List[AudioSegment]
   │
   ▼
[Stage 5] AudioProcessor.process(segments) → List[AudioSegment]
   │
   ▼
[Stage 6] AudioExporter.export(segments, chunks, metadata, config)
```

---

## 5. Stage 1 — FB2 Parser

File: `src/fb2mp3/fb2_parser.py`

### 5.1 Responsibilities

- Parse the FB2 XML document.
- Extract `BookMetadata` from the `<description>` → `<title-info>` element.
- Walk `<body>` → `<section>` elements to produce an ordered list of `TextBlock` objects.

### 5.2 Key XML Elements

| FB2 Element      | Mapped To                          |
|------------------|------------------------------------|
| `<book-title>`   | `BookMetadata.title`               |
| `<author>`       | `BookMetadata.author` (formatted)  |
| `<lang>`         | `BookMetadata.language`            |
| `<section>`      | one chapter (increments chapter index) |
| `<title>` inside `<section>` | `TextBlock.chapter_title` |
| `<p>`            | one `TextBlock`                    |
| `<subtitle>`     | one `TextBlock`                    |

### 5.3 Interface

```python
from lxml import etree   # primary; fall back to bs4 if lxml unavailable

class FB2Parser:
    def parse(self, path: str) -> ParsedBook: ...

    def _extract_metadata(self, root: etree._Element) -> BookMetadata: ...
    def _extract_blocks(self, root: etree._Element) -> list[TextBlock]: ...
    def _text_from_element(self, el: etree._Element) -> str: ...
```

### 5.4 Implementation Notes

- Use `lxml.etree.parse()` with namespace-aware XPath expressions. The FB2 namespace is
  `http://www.gribuser.ru/xml/fictionbook/2.0`.
- Ignore `<binary>` elements (cover images, etc.).
- Footnote sections (identified by `type="notes"`) are skipped entirely.
- Nested `<section>` elements (sub-chapters) are flattened; each nested section increments
  the chapter index.

---

## 6. Stage 2 — Text Cleaner

File: `src/fb2mp3/text_cleaner.py`

### 6.1 Responsibilities

Apply a series of normalization and sanitization transforms to each `TextBlock.text` value.

### 6.2 Interface

```python
import unicodedata

class TextCleaner:
    def clean(self, book: ParsedBook) -> ParsedBook: ...
    def clean_text(self, text: str) -> str: ...
```

### 6.3 Cleaning Pipeline (applied in order)

| Step | Operation | Detail |
|------|-----------|--------|
| 1 | Unicode NFC normalization | `unicodedata.normalize("NFC", text)` |
| 2 | Remove soft hyphens | Strip `U+00AD` |
| 3 | Remove zero-width characters | Strip `U+200B`, `U+FEFF`, `U+200C`, `U+200D` |
| 4 | Collapse whitespace | Replace runs of whitespace/newlines with a single space |
| 5 | Strip leading/trailing whitespace | `str.strip()` |
| 6 | Drop empty blocks | Remove `TextBlock` entries whose `text` is empty after cleaning |

### 6.4 Implementation Notes

- `clean()` mutates `TextBlock.text` values in the `ParsedBook` passed to it and also removes
  empty blocks from `ParsedBook.blocks`. It returns the same (mutated) object.
- No language detection is performed at this stage; mixed-language passages are left intact for
  the TTS engine to handle (per Section 8 of the requirements).

---

## 7. Stage 3 — Sentence Chunker

File: `src/fb2mp3/chunker.py`

### 7.1 Responsibilities

Split each `TextBlock` into one or more `Chunk` objects whose `text` length does not exceed
the XTTS v2 input limit of **250 characters**.

### 7.2 Interface

```python
from nltk.tokenize import sent_tokenize

class Chunker:
    MAX_CHARS: int = 250

    def __init__(self, lang: str) -> None: ...      # lang: "en" | "uk" | "ru"
    def chunk(self, book: ParsedBook) -> list[Chunk]: ...
    def _chunk_block(self, block: TextBlock, start_index: int) -> list[Chunk]: ...
```

### 7.3 Algorithm

1. Call `sent_tokenize(block.text, language=<nltk_lang>)` to split each block into sentences.
   - Map pipeline language codes to NLTK language names:
     `"en"` → `"english"`, `"uk"` → `"ukrainian"`, `"ru"` → `"russian"`.
2. Greedily accumulate sentences into a buffer until the next sentence would push the buffer
   past `MAX_CHARS`.
3. When the buffer is full (or all sentences are exhausted), emit a `Chunk` and reset the buffer.
4. If a single sentence exceeds `MAX_CHARS`, split it at the last whitespace before the limit.

### 7.4 Implementation Notes

- Chunk `index` values are **global** (across all chapters), not per-chapter, to simplify
  downstream ordering.
- NLTK data (`punkt_tab` tokenizer) must be downloaded at first use; the module calls
  `nltk.download("punkt_tab", quiet=True)` on import.

---

## 8. Stage 4 — TTS Engine

File: `src/fb2mp3/tts_engine.py`

### 8.1 Responsibilities

Load the XTTS v2 model once and synthesize each `Chunk` into a `pydub.AudioSegment`.

### 8.2 Interface

```python
from TTS.api import TTS
from pydub import AudioSegment

class TTSEngine:
    MODEL_NAME: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, config: PipelineConfig) -> None: ...
    def synthesize(self, chunks: list[Chunk]) -> list[AudioSegment]: ...
    def _synthesize_one(self, chunk: Chunk) -> AudioSegment: ...
```

### 8.3 Initialization

```python
def __init__(self, config: PipelineConfig) -> None:
    self.lang = config.lang
    self.speaker = config.speaker          # None when voice cloning is used
    self.voice = config.voice              # None when built-in speaker is used
    self.device = config.device            # "cuda" or "cpu"
    self.tts = TTS(self.MODEL_NAME).to(self.device)
```

### 8.4 Synthesis Dispatch

| Mode | `tts_to_file()` arguments |
|------|--------------------------|
| Built-in speaker | `speaker=self.speaker, language=self.lang` |
| Voice cloning    | `speaker_wav=self.voice, language=self.lang` |

The XTTS v2 API writes synthesized audio to a temporary WAV file; that file is then loaded
into a `pydub.AudioSegment` and the temporary file is deleted.

### 8.5 Implementation Notes

- Use Python's `tempfile.NamedTemporaryFile(suffix=".wav", delete=False)` for per-chunk output.
- Synthesize chunks sequentially (no multi-threading) because the TTS model is not thread-safe.
- Log synthesis progress (chunk index + total count) at `INFO` level.

---

## 9. Stage 5 — Audio Post-Processor

File: `src/fb2mp3/audio_processor.py`

### 9.1 Responsibilities

Normalize and optionally smooth the list of `pydub.AudioSegment` objects produced by Stage 4.

### 9.2 Interface

```python
from pydub import AudioSegment

class AudioProcessor:
    CROSSFADE_MS: int = 50    # milliseconds of crossfade between adjacent segments

    def process(
        self,
        segments: list[AudioSegment],
        apply_crossfade: bool = False,
    ) -> list[AudioSegment]: ...

    def _normalize(self, segment: AudioSegment) -> AudioSegment: ...
```

### 9.3 Normalization

Use `pydub.effects.normalize()` on each segment individually to ensure consistent playback
loudness across all chunks.

### 9.4 Crossfade (Optional)

When `apply_crossfade=True`, adjacent segments are cross-faded using `segment.append(next,
crossfade=CROSSFADE_MS)`. The resulting merged segments replace the original list.

### 9.5 Implementation Notes

- Crossfade merges pairs of segments, so the output list may be shorter than the input.
- Normalization is always applied regardless of the crossfade setting.

---

## 10. Stage 6 — Audio Exporter

File: `src/fb2mp3/audio_exporter.py`

### 10.1 Responsibilities

Concatenate processed `AudioSegment` objects and export to MP3 file(s) with ID3 metadata.

### 10.2 Interface

```python
from pydub import AudioSegment

class AudioExporter:
    BITRATE: str = "192k"

    def export(
        self,
        segments: list[AudioSegment],
        chunks: list[Chunk],
        metadata: BookMetadata,
        config: PipelineConfig,
    ) -> None: ...

    def _output_path(self, config: PipelineConfig, metadata: BookMetadata) -> str: ...
    def _chapter_path(self, base_dir: str, chapter_index: int, title: str | None) -> str: ...
    def _export_segment(self, segment: AudioSegment, path: str, tags: dict) -> None: ...
    def _build_id3_tags(self, metadata: BookMetadata) -> dict: ...
```

### 10.3 Single-File Export (default)

1. Concatenate all `AudioSegment` objects in order using `+` operator.
2. Derive output path:
   - Use `config.output_path` if provided.
   - Otherwise, slugify `metadata.title` (replace spaces with underscores, strip special chars)
     and append `.mp3`.
3. Call `pydub.AudioSegment.export(path, format="mp3", bitrate=BITRATE, tags=id3_tags)`.

### 10.4 Per-Chapter Export (`--split-chapters`)

1. Group `(segment, chunk)` pairs by `chunk.chapter_index`.
2. For each chapter group:
   a. Concatenate the chapter's segments.
   b. Derive filename: `Chapter_{chapter_index + 1:02d}_{slugified_title}.mp3`.
   c. Export with the same ID3 tags as single-file mode, plus the chapter title in the
      `album` tag field (used as a proxy for track grouping).

### 10.5 ID3 Tags

| Tag field | Value source |
|-----------|-------------|
| `title`   | `BookMetadata.title` |
| `artist`  | `BookMetadata.author` |
| `language`| `BookMetadata.language` |

### 10.6 Implementation Notes

- `pydub` delegates MP3 encoding to **ffmpeg**; ffmpeg must be installed and accessible on `PATH`.
- Output directories are created with `os.makedirs(exist_ok=True)` if they do not exist.

---

## 11. CLI Interface

File: `src/fb2mp3/cli.py`

### 11.1 Entry Point

Registered in `pyproject.toml` as:

```toml
[project.scripts]
fb2mp3 = "fb2mp3.cli:main"
```

### 11.2 Argument Definitions

```python
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fb2mp3",
        description="Convert an FB2 eBook to an MP3 audiobook using XTTS v2.",
    )
    parser.add_argument("input", help="Path to the input .fb2 file")
    parser.add_argument("--lang", required=True, choices=["en", "uk", "ru"],
                        help="Language code of the book")
    parser.add_argument("--speaker", default=None,
                        help="Built-in XTTS v2 speaker name")
    parser.add_argument("--voice", default=None,
                        help="Path to reference WAV file for voice cloning")
    parser.add_argument("--output", default=None,
                        help="Output path/filename (default: <book_title>.mp3)")
    parser.add_argument("--split-chapters", action="store_true",
                        help="Output one MP3 per chapter instead of a single file")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"],
                        help="Inference device (default: cuda)")
    return parser
```

### 11.3 Validation

The `main()` function applies the following checks before constructing `PipelineConfig`:

| Check | Error message |
|-------|---------------|
| Exactly one of `--speaker` / `--voice` must be provided | `"Specify exactly one of --speaker or --voice"` |
| `--voice` file must exist and be a `.wav` file | `"Reference audio file not found: <path>"` |
| `input` file must exist and end in `.fb2` | `"Input file not found: <path>"` |

Validation failures call `parser.error()`, which prints the message and exits with code 2.

### 11.4 Logging

- Logging is configured at `INFO` level by default using Python's `logging.basicConfig()`.
- Each stage logs its start and completion with timing information.

---

## 12. Dependencies

### 12.1 `pyproject.toml` (runtime dependencies)

```toml
[project]
name = "fb2mp3"
requires-python = ">=3.10"

dependencies = [
    "lxml>=5.0",
    "beautifulsoup4>=4.12",   # fallback FB2 parser
    "nltk>=3.8",
    "coqui-tts>=0.22",        # XTTS v2
    "torch>=2.2",             # GPU acceleration via CUDA
    "pydub>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov",
]
rich-cli = [
    "typer>=0.12",            # drop-in replacement for argparse with richer output
]
```

### 12.2 System Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `ffmpeg`   | MP3 encoding | Must be on `PATH`; install via OS package manager |
| CUDA 11.8+ | GPU inference | Install matching `torch` wheel for your CUDA version |

---

## 13. Error Handling Strategy

| Failure Mode | Handling |
|---|---|
| Malformed / non-XML FB2 file | `FB2Parser` raises `ValueError` with a descriptive message |
| Empty or whitespace-only text after cleaning | Block silently dropped in Stage 2 |
| NLTK tokenizer data not found | `chunker.py` auto-downloads `punkt_tab` on first import |
| TTS synthesis failure on a chunk | Log error, re-raise; pipeline stops |
| ffmpeg not found | `pydub` raises `FileNotFoundError`; caught in `AudioExporter` and re-raised with a hint to install ffmpeg |
| CUDA out-of-memory | Not caught; user is advised to switch to `--device cpu` |

---

## 14. Testing Strategy

### 14.1 Unit Tests

Each stage module has a corresponding `tests/test_<module>.py` file. Tests use lightweight
fixtures (small in-memory objects) and avoid GPU/TTS model invocation.

| Test file | What it tests |
|-----------|---------------|
| `test_fb2_parser.py` | Parses sample FB2 XML fragments; checks `ParsedBook` structure |
| `test_text_cleaner.py` | Applies cleaning to strings with known dirty inputs; verifies output |
| `test_chunker.py` | Verifies chunks are ≤ 250 chars and sentence boundaries are respected |
| `test_audio_processor.py` | Uses pydub `AudioSegment.silent()` to verify normalization and crossfade |
| `test_audio_exporter.py` | Mocks `AudioSegment.export`; verifies path derivation and ID3 tag building |

### 14.2 TTS Engine Tests

`test_tts_engine.py` mocks the `TTS` class from `coqui-tts` to avoid loading the actual model:

```python
from unittest.mock import MagicMock, patch

@patch("fb2mp3.tts_engine.TTS")
def test_synthesize_calls_tts(mock_tts_cls, tmp_path):
    ...
```

### 14.3 Integration Tests

A small, real FB2 fixture file (`tests/fixtures/sample.fb2`) is used in integration tests that
run all stages except Stage 4 (TTS), which is always mocked.

---

## 15. Configuration & Environment

No external configuration files are used. All runtime parameters are passed via CLI arguments
and propagated through the `PipelineConfig` dataclass.

The XTTS v2 model is cached by the `coqui-tts` library in `~/.local/share/tts/` (Linux) or
the equivalent platform-specific path. No additional setup is required beyond the first run,
which downloads the model automatically.
