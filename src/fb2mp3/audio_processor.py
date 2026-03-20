"""Stage 5 — Audio Post-Processor.

Normalises the volume of each ``pydub.AudioSegment`` and optionally applies a
short crossfade between adjacent segments to reduce abrupt transitions.
"""
from __future__ import annotations

import logging
from typing import List

from pydub import AudioSegment
from pydub import effects as pydub_effects

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Normalise and optionally crossfade a list of audio segments."""

    CROSSFADE_MS: int = 50  # milliseconds of crossfade between adjacent segments

    def process(
        self,
        segments: List[AudioSegment],
        apply_crossfade: bool = False,
    ) -> List[AudioSegment]:
        """Normalise *segments* and optionally merge them with crossfade.

        Parameters
        ----------
        segments:
            Ordered list of audio segments produced by Stage 4.
        apply_crossfade:
            When ``True``, adjacent segments are merged using a
            :attr:`CROSSFADE_MS`-millisecond crossfade. The returned list
            will therefore be shorter than the input list.

        Returns
        -------
        List[AudioSegment]
            Processed segments (normalised, crossfaded if requested).
        """
        if not segments:
            return segments

        # Step 1 — normalise each segment individually.
        normalised = [self._normalize(seg) for seg in segments]
        logger.debug("Normalised %d segment(s)", len(normalised))

        if not apply_crossfade:
            return normalised

        # Step 2 — merge pairs with crossfade.
        merged: List[AudioSegment] = []
        accumulator = normalised[0]
        for seg in normalised[1:]:
            accumulator = accumulator.append(seg, crossfade=self.CROSSFADE_MS)
        merged.append(accumulator)
        logger.debug("Applied %d ms crossfade; merged into %d segment(s)", self.CROSSFADE_MS, len(merged))
        return merged

    def _normalize(self, segment: AudioSegment) -> AudioSegment:
        """Return a volume-normalised copy of *segment*."""
        return pydub_effects.normalize(segment)
