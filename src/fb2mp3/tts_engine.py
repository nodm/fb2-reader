"""Stage 4 — TTS Engine (XTTS v2).

Wraps the Coqui TTS ``XTTS v2`` model and synthesises each :class:`Chunk`
into a ``pydub.AudioSegment``.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import List

from pydub import AudioSegment

from .models import Chunk

logger = logging.getLogger(__name__)

try:
    from TTS.api import TTS  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover – only absent in test environments without coqui-tts
    TTS = None  # type: ignore[assignment,misc]


class TTSEngine:
    """Load the XTTS v2 model once and synthesise :class:`Chunk` objects."""

    MODEL_NAME: str = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, config: "PipelineConfig") -> None:  # noqa: F821
        self.lang = config.lang
        self.speaker = config.speaker   # None when voice cloning is used
        self.voice = config.voice       # None when built-in speaker is used
        self.device = config.device     # "cuda" or "cpu"

        if TTS is None:  # pragma: no cover
            raise ImportError(
                "coqui-tts is not installed. Install it with: pip install coqui-tts"
            )

        logger.info("Loading TTS model '%s' on device '%s'", self.MODEL_NAME, self.device)
        self.tts = TTS(self.MODEL_NAME).to(self.device)
        logger.info("TTS model loaded.")

    def synthesize(self, chunks: List[Chunk]) -> List[AudioSegment]:
        """Synthesise every chunk and return the corresponding audio segments."""
        segments: List[AudioSegment] = []
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            logger.info("Synthesising chunk %d / %d …", i + 1, total)
            segment = self._synthesize_one(chunk)
            segments.append(segment)
        return segments

    def _synthesize_one(self, chunk: Chunk) -> AudioSegment:
        """Synthesise a single chunk and return it as an :class:`AudioSegment`."""
        # Use a named temporary file so pydub can read it after TTS writes it.
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            kwargs: dict = {
                "text": chunk.text,
                "language": self.lang,
                "file_path": tmp_path,
            }
            if self.voice:
                kwargs["speaker_wav"] = self.voice
            else:
                kwargs["speaker"] = self.speaker

            self.tts.tts_to_file(**kwargs)
            segment = AudioSegment.from_wav(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return segment
