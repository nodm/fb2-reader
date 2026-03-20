# fb2mp3 — FB2 eBook to MP3 Audiobook Converter

Convert `.fb2` (FictionBook 2) eBooks into high-quality `.mp3` audiobooks using
**XTTS v2** (Coqui TTS) — fully offline, locally synthesized, and GPU-accelerated.

## Features

- **100 % offline** — no cloud APIs, no internet required after first model download
- **GPU-accelerated** synthesis via CUDA (CPU fallback supported)
- **Three languages:** English (`en`), Ukrainian (`uk`), Russian (`ru`)
- **Two voice modes:** built-in named speaker _or_ custom voice cloning from a short WAV sample
- **Per-chapter splitting** — one MP3 per chapter, or a single file for the whole book
- **ID3 metadata** tags (title, author, language) written to every output file
- Optional **50 ms crossfade** between audio segments for smooth playback

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
   - [Linux / macOS](#linux--macos)
   - [Windows 11](#windows-11)
3. [Running the Pipeline](#running-the-pipeline)
   - [Quick-start examples](#quick-start-examples)
   - [All CLI options](#all-cli-options)
4. [Voice modes](#voice-modes)
5. [Output modes](#output-modes)
6. [GPU usage on Windows 11](#gpu-usage-on-windows-11)
7. [Hardware requirements](#hardware-requirements)
8. [Pipeline architecture](#pipeline-architecture)
9. [Development](#development)

---

## Prerequisites

| Requirement | Minimum version | Notes |
|-------------|----------------|-------|
| Python | 3.10 | 3.11 / 3.12 also work |
| [ffmpeg](https://ffmpeg.org/download.html) | any recent | must be on your `PATH` |
| NVIDIA GPU + CUDA driver | CUDA 11.8 | optional — CPU fallback available |

> **First run:** the XTTS v2 model (~1.8 GB) is downloaded automatically and cached in
> `~/.local/share/tts/` (Linux/macOS) or `%LOCALAPPDATA%\tts\` (Windows).
> Subsequent runs are fully offline.

---

## Installation

### Linux / macOS

```bash
# 1. Clone the repository
git clone https://github.com/nodm/fb2-reader.git
cd fb2-reader

# 2a. Install with uv (recommended — fastest)
pip install uv          # skip if uv is already available
uv sync

# 2b. Or install with pip into a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

After installation the `fb2mp3` command is available inside the virtual environment.

### Windows 11

> **TL;DR — WSL2 is NOT required.**
> The pipeline runs natively on Windows 11 with Python, CUDA, and ffmpeg installed directly
> on the host. See [GPU usage on Windows 11](#gpu-usage-on-windows-11) for CUDA setup details.

#### Option A — Native Windows (recommended for GPU users)

```powershell
# 1. Install Python 3.10+ from https://python.org  (add to PATH during setup)
# 2. Install ffmpeg and add it to PATH (see https://ffmpeg.org/download.html)

# 3. Clone the repository
git clone https://github.com/nodm/fb2-reader.git
cd fb2-reader

# 4a. Install with uv (recommended)
pip install uv
uv sync

# 4b. Or install with pip
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

#### Option B — WSL2 (alternative for Linux-familiar users)

WSL2 is **not required** but is a valid alternative if you prefer a Linux environment on
Windows. CUDA/GPU passthrough works natively inside WSL2 as of WSL2 kernel 5.10+ and
NVIDIA driver 470+.

```bash
# Inside a WSL2 Ubuntu shell — same steps as Linux above
git clone https://github.com/nodm/fb2-reader.git
cd fb2-reader
pip install uv && uv sync
```

---

## Running the Pipeline

### Quick-start examples

```bash
# Built-in speaker, Ukrainian, single output file
fb2mp3 book.fb2 --lang uk --speaker "Ana Florence" --output audiobook.mp3

# Custom voice cloning, Russian, split into one MP3 per chapter
fb2mp3 book.fb2 --lang ru --voice narrator.wav --split-chapters

# English, CPU-only (no GPU), crossfade between segments
fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --device cpu --crossfade

# Chapter-per-file output inside a custom directory
fb2mp3 book.fb2 --lang uk --speaker "Ana Florence" --split-chapters --output ./chapters/
```

On Windows PowerShell, replace `fb2mp3` with the full path if the virtual environment is
not activated, e.g. `.\.venv\Scripts\fb2mp3`.

### All CLI options

```
Usage: fb2mp3 <input.fb2> [OPTIONS]

Positional arguments:
  input                  Path to the .fb2 file to convert (required)

Required (exactly one of):
  --speaker TEXT         Name of a built-in XTTS v2 speaker
                           e.g. "Ana Florence", "Daisy Studious"
  --voice PATH           Path to a reference WAV file for voice cloning
                           (6–30 s, mono, 22050 Hz recommended, no background noise)

Required:
  --lang {en,uk,ru}      Language of the book text

Optional:
  --output PATH          Output file or directory
                           Without --split-chapters: path to the output .mp3 file
                             (default: <book_title>.mp3 in the current directory)
                           With --split-chapters: path to the output directory
                             (default: <book_title>/ in the current directory)
  --split-chapters       Write one .mp3 per chapter instead of a single combined file
  --device {cuda,cpu}    Inference device (default: cuda)
  --crossfade            Apply a 50 ms crossfade between adjacent audio segments
                           Note: crossfade is automatically disabled when --split-chapters
                           is used to preserve clean chapter boundaries
  --help                 Show this help message and exit
```

---

## Voice modes

### Mode 1 — Built-in speaker

Pass a name from the XTTS v2 built-in speaker set using `--speaker`:

```bash
fb2mp3 book.fb2 --lang en --speaker "Ana Florence"
```

No additional audio files are needed. The model ships with a set of curated voices.

### Mode 2 — Custom voice cloning

Pass a WAV recording of the desired voice using `--voice`:

```bash
fb2mp3 book.fb2 --lang en --voice my_narrator.wav
```

Requirements for the reference audio file:

| Property | Requirement |
|----------|-------------|
| Duration | 6–30 seconds |
| Format | WAV (mono preferred) |
| Sample rate | 22,050 Hz recommended |
| Background noise | None or minimal |

Voice cloning quality degrades noticeably with background noise, music, or very short clips.

---

## Output modes

### Single file (default)

All chapters are concatenated into one MP3 file.

```bash
fb2mp3 book.fb2 --lang en --speaker "Ana Florence"
# → <Book_Title>.mp3
fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --output my_audiobook.mp3
# → my_audiobook.mp3
```

### Per-chapter files (`--split-chapters`)

Each chapter is exported as a separate numbered MP3 file inside a directory.

```bash
fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --split-chapters
# → <Book_Title>/Chapter_01_<Book_Title>.mp3
# → <Book_Title>/Chapter_02_<Book_Title>.mp3
# → …

fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --split-chapters --output ./chapters/
# → chapters/Chapter_01_<Book_Title>.mp3
# → …
```

> When `--split-chapters` is used, `--output` must point to a **directory** (not a `.mp3` file).

---

## GPU usage on Windows 11

XTTS v2 uses PyTorch for inference, which supports NVIDIA CUDA on Windows natively — no
WSL2 is required.

### Step-by-step CUDA setup on Windows 11

1. **Install an NVIDIA driver ≥ 520** from [nvidia.com/drivers](https://www.nvidia.com/Download/index.aspx).

2. **Verify that CUDA is visible to the driver:**
   ```powershell
   nvidia-smi
   ```
   The output should show your GPU and a CUDA version ≥ 11.8.

3. **Install PyTorch with CUDA support.**
   The `torch` package installed via `uv sync` / `pip install -e .` pulls in the CPU build
   by default on some platforms. If `nvidia-smi` shows CUDA but PyTorch reports no GPU,
   reinstall PyTorch with the matching CUDA wheel:
   ```powershell
   # Example for CUDA 12.1 (adjust the index URL for your CUDA version)
   # See https://pytorch.org/get-started/locally/ for the correct command
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```

4. **Verify PyTorch sees the GPU:**
   ```powershell
   python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
   Expected output (example): `True NVIDIA GeForce RTX 4060`

5. **Run with GPU (default):**
   ```powershell
   fb2mp3 book.fb2 --lang en --speaker "Ana Florence"
   ```
   The `--device cuda` flag is the default. Omit it or specify it explicitly:
   ```powershell
   fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --device cuda
   ```

6. **CPU fallback** (if no NVIDIA GPU is available):
   ```powershell
   fb2mp3 book.fb2 --lang en --speaker "Ana Florence" --device cpu
   ```
   CPU-only inference is ~10–20× slower than GPU inference.

### WSL2 with GPU passthrough (alternative)

If you prefer to run inside WSL2 (Ubuntu), CUDA GPU passthrough is supported out of the
box on Windows 11 as long as:

- NVIDIA driver ≥ 470 is installed on the **Windows host** (not inside WSL2)
- WSL2 kernel ≥ 5.10 is in use (default on current Windows 11)
- **Do NOT install a separate CUDA driver inside WSL2** — use only the
  [CUDA toolkit for WSL-Ubuntu](https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu)

```bash
# Inside WSL2 — verify GPU passthrough
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

---

## Hardware requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | Any modern multi-core | Intel Core i7-14700F or equivalent |
| GPU VRAM | 6 GB | 8 GB (e.g. NVIDIA RTX 4060) |
| RAM | 16 GB | 64 GB |
| Disk space | 5 GB (model + deps) | 10 GB |
| CUDA version | 11.8 | 12.x |

> **Inference speed on RTX 4060:** approximately **5–10× real-time**
> (10 minutes of audio synthesized in ~1–2 minutes).
>
> **CPU-only:** approximately 10–20× slower than GPU.
>
> **VRAM usage:** approximately 4–6 GB at FP16 precision.

---

## Pipeline architecture

The conversion is carried out by a six-stage sequential pipeline:

```
.fb2 file
    │
    ▼
[Stage 1] FB2 Parser       — extracts text blocks and metadata from FB2 XML
    │
    ▼
[Stage 2] Text Cleaner     — Unicode normalization, whitespace collapsing, soft-hyphen removal
    │
    ▼
[Stage 3] Sentence Chunker — splits text into ≤ 250-character chunks at sentence boundaries
    │
    ▼
[Stage 4] TTS Engine       — synthesizes each chunk with XTTS v2 (GPU or CPU)
    │
    ▼
[Stage 5] Audio Processor  — volume normalization, optional 50 ms crossfade
    │
    ▼
[Stage 6] Audio Exporter   — MP3 encoding via ffmpeg, ID3 tags, single file or per-chapter
```

For detailed design documentation see [`docs/architecture.md`](docs/architecture.md) and
[`docs/requirements.md`](docs/requirements.md).

---

## Development

### Running tests

```bash
# uv
uv run pytest

# pip venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows
pytest
```

### Running tests with coverage

```bash
uv run pytest --cov=fb2mp3 --cov-report=term-missing
```

### Project layout

```
fb2-reader/
├── docs/
│   ├── requirements.md        # Functional requirements
│   └── architecture.md        # Design & implementation details
├── src/
│   └── fb2mp3/
│       ├── cli.py             # CLI entry-point (argparse)
│       ├── pipeline.py        # Pipeline orchestrator
│       ├── models.py          # Shared dataclasses
│       ├── fb2_parser.py      # Stage 1 — FB2 Parser
│       ├── text_cleaner.py    # Stage 2 — Text Cleaner
│       ├── chunker.py         # Stage 3 — Sentence Chunker
│       ├── tts_engine.py      # Stage 4 — TTS Engine (XTTS v2)
│       ├── audio_processor.py # Stage 5 — Audio Post-Processor
│       └── audio_exporter.py  # Stage 6 — Audio Exporter
├── tests/                     # pytest test suite
├── .python-version            # Python version pin (3.10)
└── pyproject.toml             # Project metadata and dependencies
```

---

## License

[MIT](LICENSE)
