"""Tests for fb2mp3.audio_exporter (Stage 6)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, call, patch

import pytest
from pydub import AudioSegment

from fb2mp3.audio_exporter import AudioExporter, _slugify
from fb2mp3.models import BookMetadata, Chunk
from fb2mp3.pipeline import PipelineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _silent(duration_ms: int = 200) -> AudioSegment:
    return AudioSegment.silent(duration=duration_ms, frame_rate=22050)


def _make_config(
    output_path: str = None,
    split_chapters: bool = False,
) -> PipelineConfig:
    return PipelineConfig(
        input_path="book.fb2",
        output_path=output_path,
        lang="en",
        speaker="Ana Florence",
        voice=None,
        split_chapters=split_chapters,
        device="cpu",
    )


def _make_metadata(title: str = "My Book", author: str = "Jane Doe") -> BookMetadata:
    return BookMetadata(title=title, author=author, language="en")


def _make_chunks(chapter_indices: list[int]) -> list[Chunk]:
    return [
        Chunk(
            chapter_index=ci,
            chapter_title=f"Chapter {ci + 1}",
            index=i,
            text="text",
        )
        for i, ci in enumerate(chapter_indices)
    ]


# ---------------------------------------------------------------------------
# Tests — slug helper
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_spaces_replaced_with_underscores(self):
        assert _slugify("Hello World") == "Hello_World"

    def test_special_chars_removed(self):
        assert _slugify("Hello, World!") == "Hello_World"

    def test_empty_string_returns_output(self):
        assert _slugify("") == "output"

    def test_hyphen_preserved(self):
        assert _slugify("Hello-World") == "Hello-World"


# ---------------------------------------------------------------------------
# Tests — ID3 tag building
# ---------------------------------------------------------------------------


class TestBuildId3Tags:
    def test_returns_expected_keys(self):
        meta = _make_metadata()
        tags = AudioExporter()._build_id3_tags(meta)
        assert tags["title"] == "My Book"
        assert tags["artist"] == "Jane Doe"
        assert tags["language"] == "en"


# ---------------------------------------------------------------------------
# Tests — output path derivation
# ---------------------------------------------------------------------------


class TestOutputPath:
    def test_uses_config_output_path_if_set(self):
        config = _make_config(output_path="/tmp/custom.mp3")
        meta = _make_metadata()
        path = AudioExporter()._output_path(config, meta)
        assert path == "/tmp/custom.mp3"

    def test_derives_from_title_if_no_output_path(self):
        config = _make_config()
        meta = _make_metadata(title="My Great Book")
        path = AudioExporter()._output_path(config, meta)
        assert path == "My_Great_Book.mp3"


# ---------------------------------------------------------------------------
# Tests — chapter path derivation
# ---------------------------------------------------------------------------


class TestChapterPath:
    def test_chapter_path_format(self):
        path = AudioExporter()._chapter_path("/out", 0, "Introduction")
        assert path == os.path.join("/out", "Chapter_01_Introduction.mp3")

    def test_chapter_path_zero_padding(self):
        path = AudioExporter()._chapter_path("/out", 0, "Prologue")
        assert path == os.path.join("/out", "Chapter_01_Prologue.mp3")

    def test_chapter_path_no_title(self):
        path = AudioExporter()._chapter_path("/out", 0, None)
        assert path == os.path.join("/out", "Chapter_01_chapter.mp3")


# ---------------------------------------------------------------------------
# Tests — single-file export
# ---------------------------------------------------------------------------


class TestSingleFileExport:
    @patch.object(AudioSegment, "export")
    def test_export_called_once(self, mock_export):
        exporter = AudioExporter()
        segs = [_silent(), _silent()]
        chunks = _make_chunks([0, 0])
        config = _make_config(output_path="/tmp/book.mp3")
        meta = _make_metadata()

        exporter.export(segs, chunks, meta, config)

        mock_export.assert_called_once()
        args, kwargs = mock_export.call_args
        assert args[0] == "/tmp/book.mp3"
        assert kwargs.get("format") == "mp3"

    @patch.object(AudioSegment, "export")
    def test_id3_tags_passed_to_export(self, mock_export):
        exporter = AudioExporter()
        segs = [_silent()]
        chunks = _make_chunks([0])
        config = _make_config(output_path="/tmp/book.mp3")
        meta = _make_metadata(title="Great Book", author="Author Name")

        exporter.export(segs, chunks, meta, config)

        _, kwargs = mock_export.call_args
        assert kwargs["tags"]["title"] == "Great Book"
        assert kwargs["tags"]["artist"] == "Author Name"

    def test_empty_segments_does_not_call_export(self):
        exporter = AudioExporter()
        config = _make_config()
        meta = _make_metadata()
        # Should not raise, just log a warning.
        exporter.export([], [], meta, config)


# ---------------------------------------------------------------------------
# Tests — per-chapter export
# ---------------------------------------------------------------------------


class TestPerChapterExport:
    @patch.object(AudioSegment, "export")
    def test_export_called_once_per_chapter(self, mock_export, tmp_path):
        exporter = AudioExporter()
        segs = [_silent(), _silent(), _silent()]
        chunks = _make_chunks([0, 0, 1])  # 2 chapters
        config = _make_config(
            output_path=str(tmp_path / "chapters"),
            split_chapters=True,
        )
        meta = _make_metadata()

        exporter.export(segs, chunks, meta, config)

        # One export per chapter (2 chapters).
        assert mock_export.call_count == 2

    @patch.object(AudioSegment, "export")
    def test_chapter_title_in_album_tag(self, mock_export, tmp_path):
        exporter = AudioExporter()
        segs = [_silent()]
        chunks = [Chunk(chapter_index=0, chapter_title="Prologue", index=0, text="t")]
        config = _make_config(
            output_path=str(tmp_path / "ch"),
            split_chapters=True,
        )
        meta = _make_metadata()

        exporter.export(segs, chunks, meta, config)

        _, kwargs = mock_export.call_args
        assert kwargs["tags"].get("album") == "Prologue"
