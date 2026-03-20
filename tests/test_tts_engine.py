"""Tests for fb2mp3.tts_engine (Stage 4).

The actual XTTS v2 model is never loaded in these tests; the ``TTS`` class is
always replaced by a :class:`unittest.mock.MagicMock`.
"""
from __future__ import annotations

import os
import wave
from unittest.mock import MagicMock, patch

import pytest
from pydub import AudioSegment

from fb2mp3.models import Chunk
from fb2mp3.pipeline import PipelineConfig
from fb2mp3.tts_engine import TTSEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(speaker: str = "Ana Florence", voice: str = None) -> PipelineConfig:
    return PipelineConfig(
        input_path="book.fb2",
        output_path=None,
        lang="en",
        speaker=speaker,
        voice=voice,
        split_chapters=False,
        device="cpu",
    )


def _make_chunk(text: str = "Hello world.", index: int = 0) -> Chunk:
    return Chunk(chapter_index=0, chapter_title="Ch 1", index=index, text=text)


def _write_silent_wav(path: str, duration_ms: int = 500) -> None:
    """Write a minimal silent WAV file to *path* so pydub can load it."""
    sample_rate = 22050
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("fb2mp3.tts_engine.TTS")
class TestTTSEngineInit:
    def test_tts_instantiated_with_model_name(self, mock_tts_cls):
        config = _make_config()
        TTSEngine(config)
        mock_tts_cls.assert_called_once_with(TTSEngine.MODEL_NAME)

    def test_to_called_with_device(self, mock_tts_cls):
        config = _make_config()
        TTSEngine(config)
        mock_tts_cls.return_value.to.assert_called_once_with("cpu")


@patch("fb2mp3.tts_engine.TTS")
class TestTTSEngineSynthesize:
    def test_synthesize_calls_tts_to_file_for_each_chunk(self, mock_tts_cls, tmp_path):
        config = _make_config(speaker="Ana Florence")
        engine = TTSEngine(config)

        chunks = [_make_chunk("Hello.", 0), _make_chunk("World.", 1)]

        # Make tts_to_file write a real silent WAV so AudioSegment.from_wav works.
        def fake_tts_to_file(**kwargs):
            _write_silent_wav(kwargs["file_path"])

        mock_tts_instance = mock_tts_cls.return_value.to.return_value
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        segments = engine.synthesize(chunks)

        assert mock_tts_instance.tts_to_file.call_count == 2
        assert len(segments) == 2
        assert all(isinstance(s, AudioSegment) for s in segments)

    def test_synthesize_passes_speaker_when_set(self, mock_tts_cls, tmp_path):
        config = _make_config(speaker="Ana Florence")
        engine = TTSEngine(config)

        def fake_tts_to_file(**kwargs):
            _write_silent_wav(kwargs["file_path"])

        mock_tts_instance = mock_tts_cls.return_value.to.return_value
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        engine.synthesize([_make_chunk()])

        call_kwargs = mock_tts_instance.tts_to_file.call_args.kwargs
        assert call_kwargs.get("speaker") == "Ana Florence"
        assert "speaker_wav" not in call_kwargs

    def test_synthesize_passes_speaker_wav_when_voice_set(self, mock_tts_cls, tmp_path):
        voice_path = str(tmp_path / "voice.wav")
        _write_silent_wav(voice_path)
        config = _make_config(speaker=None, voice=voice_path)
        engine = TTSEngine(config)

        def fake_tts_to_file(**kwargs):
            _write_silent_wav(kwargs["file_path"])

        mock_tts_instance = mock_tts_cls.return_value.to.return_value
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        engine.synthesize([_make_chunk()])

        call_kwargs = mock_tts_instance.tts_to_file.call_args.kwargs
        assert call_kwargs.get("speaker_wav") == voice_path
        assert "speaker" not in call_kwargs

    def test_temp_file_deleted_after_synthesis(self, mock_tts_cls, tmp_path):
        """Temporary WAV files should be cleaned up after loading."""
        config = _make_config(speaker="Ana Florence")
        engine = TTSEngine(config)

        created_tmp = []

        def fake_tts_to_file(**kwargs):
            path = kwargs["file_path"]
            _write_silent_wav(path)
            created_tmp.append(path)

        mock_tts_instance = mock_tts_cls.return_value.to.return_value
        mock_tts_instance.tts_to_file.side_effect = fake_tts_to_file

        engine.synthesize([_make_chunk()])

        for p in created_tmp:
            assert not os.path.exists(p), f"Temp file not deleted: {p}"

    def test_synthesize_empty_chunks_returns_empty(self, mock_tts_cls):
        config = _make_config(speaker="Ana Florence")
        engine = TTSEngine(config)
        assert engine.synthesize([]) == []
