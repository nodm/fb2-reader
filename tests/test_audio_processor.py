"""Tests for fb2mp3.audio_processor (Stage 5)."""
from __future__ import annotations

import array
import math

import pytest
from pydub import AudioSegment

from fb2mp3.audio_processor import AudioProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _silent(duration_ms: int = 500) -> AudioSegment:
    """Return a truly silent AudioSegment."""
    return AudioSegment.silent(duration=duration_ms, frame_rate=22050)


def _tone(
    frequency: float = 440.0,
    duration_ms: int = 500,
    amplitude: float = 0.5,
    sample_rate: int = 22050,
) -> AudioSegment:
    """Return an AudioSegment containing a pure sine-wave tone."""
    num_samples = int(sample_rate * duration_ms / 1000)
    samples = [
        int(amplitude * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        for i in range(num_samples)
    ]
    raw = array.array("h", samples).tobytes()
    return AudioSegment(raw, frame_rate=sample_rate, sample_width=2, channels=1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAudioProcessorNormalization:
    def test_returns_same_number_of_segments(self):
        segs = [_tone() for _ in range(3)]
        result = AudioProcessor().process(segs)
        assert len(result) == 3

    def test_returns_audio_segments(self):
        segs = [_tone()]
        result = AudioProcessor().process(segs)
        assert all(isinstance(s, AudioSegment) for s in result)

    def test_empty_input_returns_empty(self):
        assert AudioProcessor().process([]) == []

    def test_normalised_segments_have_consistent_loudness(self):
        # Segments with very different initial volumes should converge after normalisation.
        quiet = _tone(amplitude=0.05)   # ~quieter
        loud = _tone(amplitude=0.9)     # ~louder
        result = AudioProcessor().process([quiet, loud])
        # Both should now have dBFS close to 0 (normalization targets peak = 0 dBFS).
        for seg in result:
            assert seg.dBFS > -6.0, f"Segment still too quiet after normalisation: {seg.dBFS}"


class TestAudioProcessorCrossfade:
    def test_crossfade_merges_segments(self):
        segs = [_tone(duration_ms=1000) for _ in range(4)]
        result = AudioProcessor().process(segs, apply_crossfade=True)
        # All segments should be merged into one.
        assert len(result) == 1

    def test_crossfade_output_is_audio_segment(self):
        segs = [_tone(duration_ms=500), _tone(duration_ms=500)]
        result = AudioProcessor().process(segs, apply_crossfade=True)
        assert isinstance(result[0], AudioSegment)

    def test_no_crossfade_preserves_count(self):
        segs = [_tone() for _ in range(5)]
        result = AudioProcessor().process(segs, apply_crossfade=False)
        assert len(result) == 5

    def test_crossfade_merged_duration_is_shorter_than_sum(self):
        # 4 segments of 500ms each; crossfade reduces total duration.
        segs = [_tone(duration_ms=500) for _ in range(4)]
        raw_total = sum(len(s) for s in segs)
        result = AudioProcessor().process(segs, apply_crossfade=True)
        merged_duration = len(result[0])
        assert merged_duration < raw_total

    def test_single_segment_crossfade(self):
        segs = [_tone(duration_ms=500)]
        result = AudioProcessor().process(segs, apply_crossfade=True)
        assert len(result) == 1
