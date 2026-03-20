"""Stage 6 — Audio Exporter.

Concatenates processed ``pydub.AudioSegment`` objects and exports them as MP3
file(s) with ID3 metadata derived from the book's :class:`BookMetadata`.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from collections import defaultdict
from typing import Dict, List, Optional

from pydub import AudioSegment

from .models import BookMetadata, Chunk

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert *text* to a filesystem-safe slug.

    Replaces spaces with underscores and removes characters that are not
    alphanumeric, underscores, or hyphens.
    """
    text = text.replace(" ", "_")
    text = re.sub(r"[^\w\-]", "", text)
    return text or "output"


class AudioExporter:
    """Concatenate and export audio segments to MP3 file(s)."""

    BITRATE: str = "192k"

    def export(
        self,
        segments: List[AudioSegment],
        chunks: List[Chunk],
        metadata: BookMetadata,
        config: "PipelineConfig",  # noqa: F821
    ) -> None:
        """Export *segments* to one or more MP3 files.

        Parameters
        ----------
        segments:
            Processed audio segments in the same order as *chunks*.
        chunks:
            Chunk metadata (used to map segments to chapters).
        metadata:
            Book metadata used for output filename and ID3 tags.
        config:
            Pipeline configuration (``output_path``, ``split_chapters``).
        """
        if not segments:
            logger.warning("No audio segments to export.")
            return

        id3_tags = self._build_id3_tags(metadata)

        if config.split_chapters:
            self._export_by_chapter(segments, chunks, metadata, config, id3_tags)
        else:
            self._export_single(segments, metadata, config, id3_tags)

    # ------------------------------------------------------------------
    # Single-file export
    # ------------------------------------------------------------------

    def _export_single(
        self,
        segments: List[AudioSegment],
        metadata: BookMetadata,
        config: "PipelineConfig",  # noqa: F821
        id3_tags: Dict[str, str],
    ) -> None:
        combined = segments[0]
        for seg in segments[1:]:
            combined = combined + seg

        path = self._output_path(config, metadata)
        self._export_segment(combined, path, id3_tags)
        logger.info("Exported single MP3: %s", path)

    # ------------------------------------------------------------------
    # Per-chapter export
    # ------------------------------------------------------------------

    def _export_by_chapter(
        self,
        segments: List[AudioSegment],
        chunks: List[Chunk],
        metadata: BookMetadata,
        config: "PipelineConfig",  # noqa: F821
        id3_tags: Dict[str, str],
    ) -> None:
        # Determine the base directory for output files.
        if config.output_path:
            base_dir = config.output_path
        else:
            base_dir = _slugify(metadata.title)
        os.makedirs(base_dir, exist_ok=True)

        # Group (segment, chunk) pairs by chapter index.
        chapter_groups: dict[int, list[tuple[AudioSegment, Chunk]]] = defaultdict(list)
        if len(segments) != len(chunks):
            raise ValueError(
                "AudioExporter._export_by_chapter received mismatched lengths: "
                f"{len(segments)=}, {len(chunks)=}"
            )
        for seg, chunk in zip(segments, chunks):
            chapter_groups[chunk.chapter_index].append((seg, chunk))

        for chapter_index in sorted(chapter_groups.keys()):
            group = chapter_groups[chapter_index]
            chapter_title = group[0][1].chapter_title

            # Concatenate segments for this chapter.
            chapter_audio = group[0][0]
            for seg, _ in group[1:]:
                chapter_audio = chapter_audio + seg

            path = self._chapter_path(base_dir, chapter_index, chapter_title)

            chapter_tags = dict(id3_tags)
            if chapter_title:
                chapter_tags["album"] = chapter_title

            self._export_segment(chapter_audio, path, chapter_tags)
            logger.info("Exported chapter MP3: %s", path)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _output_path(
        self,
        config: "PipelineConfig",  # noqa: F821
        metadata: BookMetadata,
    ) -> str:
        if config.output_path:
            return config.output_path
        return f"{_slugify(metadata.title)}.mp3"

    def _chapter_path(
        self, base_dir: str, chapter_index: int, title: Optional[str]
    ) -> str:
        slug = _slugify(title) if title else "chapter"
        filename = f"Chapter_{chapter_index + 1:02d}_{slug}.mp3"
        return os.path.join(base_dir, filename)

    # ------------------------------------------------------------------
    # Export helper
    # ------------------------------------------------------------------

    def _export_segment(
        self, segment: AudioSegment, path: str, tags: Dict[str, str]
    ) -> None:
        if shutil.which("ffmpeg") is None:
            raise FileNotFoundError(
                "ffmpeg not found. Please install ffmpeg and ensure it is on PATH."
            )
        try:
            segment.export(path, format="mp3", bitrate=self.BITRATE, tags=tags)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Export failed: {exc}"
            ) from exc

    def _build_id3_tags(self, metadata: BookMetadata) -> Dict[str, str]:
        return {
            "title": metadata.title,
            "artist": metadata.author,
            "language": metadata.language,
        }
