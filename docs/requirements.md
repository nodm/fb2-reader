# FB2 to MP3 Conversion Pipeline — Requirements

## 1. Overview

This pipeline converts `.fb2` (FictionBook 2) eBook files into `.mp3` audiobook files using
local, fully offline, GPU-accelerated text-to-speech synthesis via **XTTS v2** (Coqui TTS).
The goal is to produce high-quality, natural-sounding audiobooks from FB2 sources without
relying on cloud services or internet connectivity.

---

## 2. Supported Languages

| Code | Language   |
|------|------------|
| `en` | English    |
| `uk` | Ukrainian  |
| `ru` | Russian    |

---

## 3. Voice Selection

Two modes are supported and are mutually exclusive.

### Mode 1 — Built-in Speaker

Select from XTTS v2's built-in named speakers via a CLI argument:

```
--speaker "Ana Florence"
```

XTTS v2 ships with a curated set of named speakers that can be used without any additional
reference audio.

### Mode 2 — Custom Voice Cloning

Provide a reference audio file via a CLI argument:

```
--voice narrator.wav
```

XTTS v2 will clone the voice characteristics from the provided sample and use them throughout
the book synthesis.

**Requirements for the reference audio file:**

| Property        | Requirement                          |
|-----------------|--------------------------------------|
| Duration        | 6–30 seconds                         |
| Format          | WAV (mono preferred)                 |
| Sample rate     | 22050 Hz recommended                 |
| Background noise| None or minimal                      |

---

## 4. Pipeline Architecture

The pipeline is composed of six sequential stages:

### Stage 1 — FB2 Parser

Extract structured text (title, chapters, paragraphs) from the `.fb2` XML format.

- **Library:** `lxml` or `BeautifulSoup`
- FB2 is XML-based; key elements are `<section>`, `<title>`, and `<p>`.
- Output: ordered list of text blocks with chapter metadata.

### Stage 2 — Text Cleaner

Normalize and sanitize extracted text before synthesis.

- Normalize Unicode (NFC normalization).
- Strip footnotes, annotations, and unspeakable markup.
- Handle Cyrillic and Latin text mixed within the same document.
- Remove or replace non-speakable characters (e.g., soft hyphens, zero-width spaces).

### Stage 3 — Sentence Chunker

Split cleaned text into chunks that respect XTTS v2's input length limit.

- Target chunk size: ~250 characters.
- Split at sentence boundaries to avoid mid-sentence cuts.
- **Library:** `nltk` (`sent_tokenize`) or `spacy`.
- Output: ordered list of text chunks ready for TTS inference.

### Stage 4 — TTS Engine (XTTS v2)

Synthesize each text chunk into a WAV audio segment.

- **Library:** `coqui-tts` with the XTTS v2 model.
- GPU acceleration via CUDA (default device: `cuda`).
- Accepts either a named built-in speaker or a reference WAV for voice cloning.
- Output: one WAV segment per text chunk.

### Stage 5 — Audio Post-Processor

Normalize and optionally smooth the audio segments before final export.

- Normalize volume/loudness across all chunks to ensure consistent playback level.
- Optionally apply crossfade between adjacent segments to remove abrupt transitions.
- **Library:** `pydub`.

### Stage 6 — Audio Exporter

Concatenate all processed segments and export to the final output format.

- Concatenate all WAV segments in order.
- Encode to `.mp3` using `pydub` + `ffmpeg`.
- Default: a single `.mp3` file for the whole book.
- Optional: one `.mp3` per chapter (via `--split-chapters`).
- Populate ID3 tags from FB2 metadata (title, author, language).

---

## 5. CLI Interface

```
fb2mp3 <input.fb2> [OPTIONS]

Options:
  --lang              Language code: en, uk, ru (required)
  --speaker           Built-in XTTS v2 speaker name (mutually exclusive with --voice)
  --voice             Path to reference WAV file for voice cloning (mutually exclusive with --speaker)
  --output            Output path/filename (default: <book_title>.mp3)
  --split-chapters    Output one MP3 per chapter instead of a single file
  --device            Inference device: cuda (default) or cpu
  --help              Show help
```

**Example — built-in speaker:**
```
fb2mp3 book.fb2 --lang uk --speaker "Ana Florence" --output audiobook.mp3
```

**Example — custom voice cloning:**
```
fb2mp3 book.fb2 --lang ru --voice narrator.wav --split-chapters
```

---

## 6. Technology Stack

| Component         | Library / Tool               | Purpose                                      |
|-------------------|------------------------------|----------------------------------------------|
| FB2 parsing       | `lxml`, `beautifulsoup4`     | Extract structured text from FB2 XML         |
| Text segmentation | `nltk` or `spacy`            | Sentence-boundary chunking                   |
| TTS Engine        | `coqui-tts` (XTTS v2 model)  | Neural text-to-speech synthesis              |
| GPU acceleration  | `torch` (CUDA)               | GPU inference on RTX 4060                    |
| Audio processing  | `pydub`                      | Chunk concatenation, normalization           |
| Audio encoding    | `ffmpeg`                     | MP3 export                                   |
| CLI               | `argparse` or `typer`        | Command-line interface                       |

---

## 7. Hardware Requirements

| Component   | Minimum                  | Recommended (Reference Platform)    |
|-------------|--------------------------|--------------------------------------|
| CPU         | Any modern multi-core    | Intel Core i7-14700F                 |
| GPU VRAM    | 6 GB                     | 8 GB (MSI RTX 4060 VENTUS 2X BLACK)  |
| RAM         | 16 GB                    | 64 GB                                |
| Storage     | 5 GB (model + deps)      | 10 GB                                |
| CUDA        | 11.8+                    | 12.x                                 |

> **Note:** CPU-only inference is supported via `--device cpu` but is significantly slower
> (approximately 10–20× slower than GPU inference).

---

## 8. XTTS v2 Constraints & Considerations

- **Input length limit:** ~250 characters / ~50 tokens per inference call — chunking is **mandatory**.
- **Voice cloning quality** depends directly on the cleanliness of the reference audio. Background
  noise or music in the reference file will degrade cloning quality.
- **Mixed-language text:** books that contain passages in a language other than the declared
  `--lang` (e.g., English quotations inside a Russian-language book) may require per-chunk
  language detection to maintain synthesis quality.
- **VRAM usage:** approximately 4–6 GB at FP16 precision on GPU.
- **Inference speed on RTX 4060:** approximately **5–10× real-time**
  (e.g., 10 minutes of audio synthesized in roughly 1–2 minutes).

---

## 9. Output

- **Default:** a single `.mp3` file named after the book title extracted from FB2 metadata
  (e.g., `The_Brothers_Karamazov.mp3`).
- **Per-chapter:** one `.mp3` file per chapter when `--split-chapters` is specified
  (e.g., `Chapter_01.mp3`, `Chapter_02.mp3`, …).
- **ID3 tags** populated from FB2 metadata:
  - Title
  - Author
  - Language

---

## 10. Future Considerations (Out of Scope for v1)

- Streaming synthesis (real-time playback during generation)
- Additional languages beyond `en`, `uk`, `ru`
- GUI / web interface
- Cloud TTS backend as an alternative to local XTTS v2
- Batch processing of multiple books in a single invocation
