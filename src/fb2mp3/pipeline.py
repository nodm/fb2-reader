"""Pipeline orchestrator.

Wires all six stages of the FB2-to-MP3 conversion pipeline together and
exposes a single :meth:`Pipeline.run` entry-point.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Runtime configuration for the pipeline."""

    input_path: str               # path to the input .fb2 file
    output_path: Optional[str]    # explicit output path; None → derive from title
    lang: str                     # "en" | "uk" | "ru"
    speaker: Optional[str]        # built-in XTTS v2 speaker name
    voice: Optional[str]          # path to reference WAV for voice cloning
    split_chapters: bool          # produce one MP3 per chapter
    device: str                   # "cuda" (default) or "cpu"
    crossfade: bool = False       # apply crossfade between adjacent audio segments


class Pipeline:
    """Orchestrate all six conversion stages."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def run(self) -> None:
        """Execute all pipeline stages in sequence."""
        config = self.config

        # Lazy imports keep startup fast and allow easy mocking in tests.
        from .audio_exporter import AudioExporter
        from .audio_processor import AudioProcessor
        from .chunker import Chunker
        from .fb2_parser import FB2Parser
        from .text_cleaner import TextCleaner
        from .tts_engine import TTSEngine

        # Stage 1 — FB2 Parser
        t0 = time.perf_counter()
        parser = FB2Parser()
        book = parser.parse(config.input_path)
        logger.info("Stage 1 complete in %.2fs", time.perf_counter() - t0)

        # Stage 2 — Text Cleaner
        t0 = time.perf_counter()
        cleaner = TextCleaner()
        book = cleaner.clean(book)
        logger.info("Stage 2 complete in %.2fs", time.perf_counter() - t0)

        # Stage 3 — Sentence Chunker
        t0 = time.perf_counter()
        chunker = Chunker(lang=config.lang)
        chunks = chunker.chunk(book)
        logger.info("Stage 3 complete in %.2fs — %d chunk(s)", time.perf_counter() - t0, len(chunks))

        if not chunks:
            logger.warning("No text chunks produced — the book may be empty after cleaning. Aborting.")
            return

        # Stage 4 — TTS Engine
        t0 = time.perf_counter()
        tts = TTSEngine(config)
        segments = tts.synthesize(chunks)
        logger.info("Stage 4 complete in %.2fs", time.perf_counter() - t0)

        # Stage 5 — Audio Post-Processor
        t0 = time.perf_counter()
        processor = AudioProcessor()
        segments = processor.process(segments, apply_crossfade=config.crossfade)
        logger.info("Stage 5 complete in %.2fs", time.perf_counter() - t0)

        # Stage 6 — Audio Exporter
        t0 = time.perf_counter()
        exporter = AudioExporter()
        exporter.export(segments, chunks, book.metadata, config)
        logger.info("Stage 6 complete in %.2fs", time.perf_counter() - t0)

        logger.info("Pipeline finished successfully.")
