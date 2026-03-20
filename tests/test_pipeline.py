"""Tests for fb2mp3.pipeline (orchestrator)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fb2mp3.models import BookMetadata, Chunk, ParsedBook, TextBlock
from fb2mp3.pipeline import Pipeline, PipelineConfig


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> PipelineConfig:
    """Return a minimal PipelineConfig suitable for unit tests."""
    defaults = dict(
        input_path="book.fb2",
        output_path=None,
        lang="en",
        speaker="Ana Florence",
        voice=None,
        split_chapters=False,
        device="cpu",
        crossfade=False,
    )
    defaults.update(overrides)
    return PipelineConfig(**defaults)


def _make_parsed_book(num_blocks: int = 2) -> ParsedBook:
    return ParsedBook(
        metadata=BookMetadata(title="Test Book", author="Test Author", language="en"),
        blocks=[
            TextBlock(chapter_index=0, chapter_title="Chapter 1", text=f"Block {i}.")
            for i in range(num_blocks)
        ],
    )


def _make_chunks(n: int = 2) -> list[Chunk]:
    return [
        Chunk(chapter_index=0, chapter_title="Chapter 1", index=i, text=f"Chunk {i}.")
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Helper: patch all six pipeline stage classes at once
# ---------------------------------------------------------------------------


def _patch_stages(
    parsed_book=None,
    chunks=None,
    segments=None,
):
    """Return a context-manager dict that patches all six stage classes."""
    if parsed_book is None:
        parsed_book = _make_parsed_book()
    if chunks is None:
        chunks = _make_chunks()
    if segments is None:
        from pydub import AudioSegment

        segments = [AudioSegment.silent(duration=100) for _ in chunks]

    mock_parser = MagicMock()
    mock_parser.return_value.parse.return_value = parsed_book

    mock_cleaner = MagicMock()
    mock_cleaner.return_value.clean.return_value = parsed_book

    mock_chunker = MagicMock()
    mock_chunker.return_value.chunk.return_value = chunks

    mock_tts = MagicMock()
    mock_tts.return_value.synthesize.return_value = segments

    mock_processor = MagicMock()
    mock_processor.return_value.process.return_value = segments

    mock_exporter = MagicMock()

    patches = {
        "FB2Parser": patch("fb2mp3.fb2_parser.FB2Parser", mock_parser),
        "TextCleaner": patch("fb2mp3.text_cleaner.TextCleaner", mock_cleaner),
        "Chunker": patch("fb2mp3.chunker.Chunker", mock_chunker),
        "TTSEngine": patch("fb2mp3.tts_engine.TTSEngine", mock_tts),
        "AudioProcessor": patch("fb2mp3.audio_processor.AudioProcessor", mock_processor),
        "AudioExporter": patch("fb2mp3.audio_exporter.AudioExporter", mock_exporter),
    }

    return patches, {
        "parser": mock_parser,
        "cleaner": mock_cleaner,
        "chunker": mock_chunker,
        "tts": mock_tts,
        "processor": mock_processor,
        "exporter": mock_exporter,
    }


# ---------------------------------------------------------------------------
# Tests — PipelineConfig defaults
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    def test_crossfade_defaults_to_false(self):
        config = _make_config()
        assert config.crossfade is False

    def test_crossfade_can_be_set_true(self):
        config = _make_config(crossfade=True)
        assert config.crossfade is True

    def test_required_fields_stored(self):
        config = _make_config(input_path="my.fb2", lang="uk", device="cuda")
        assert config.input_path == "my.fb2"
        assert config.lang == "uk"
        assert config.device == "cuda"


# ---------------------------------------------------------------------------
# Tests — Pipeline.run() stage ordering and wiring
# ---------------------------------------------------------------------------


class TestPipelineRun:
    def test_all_six_stages_are_called(self):
        patches, mocks = _patch_stages()
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["parser"].return_value.parse.assert_called_once_with(config.input_path)
        mocks["cleaner"].return_value.clean.assert_called_once()
        mocks["chunker"].return_value.chunk.assert_called_once()
        mocks["tts"].return_value.synthesize.assert_called_once()
        mocks["processor"].return_value.process.assert_called_once()
        mocks["exporter"].return_value.export.assert_called_once()

    def test_chunker_receives_correct_lang(self):
        patches, mocks = _patch_stages()
        config = _make_config(lang="uk")

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["chunker"].assert_called_once_with(lang="uk")

    def test_tts_engine_receives_config(self):
        patches, mocks = _patch_stages()
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["tts"].assert_called_once_with(config)

    def test_crossfade_false_passed_to_processor(self):
        patches, mocks = _patch_stages()
        config = _make_config(crossfade=False)

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["processor"].return_value.process.assert_called_once()
        _, kwargs = mocks["processor"].return_value.process.call_args
        assert kwargs.get("apply_crossfade") is False

    def test_crossfade_true_passed_to_processor(self):
        patches, mocks = _patch_stages()
        config = _make_config(crossfade=True)

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["processor"].return_value.process.assert_called_once()
        _, kwargs = mocks["processor"].return_value.process.call_args
        assert kwargs.get("apply_crossfade") is True

    def test_crossfade_disabled_when_split_chapters_enabled(self):
        """crossfade must be forced off when split_chapters is True to avoid length mismatch."""
        patches, mocks = _patch_stages()
        config = _make_config(crossfade=True, split_chapters=True)

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["processor"].return_value.process.assert_called_once()
        _, kwargs = mocks["processor"].return_value.process.call_args
        assert kwargs.get("apply_crossfade") is False

    def test_exporter_receives_metadata_and_config(self):
        parsed_book = _make_parsed_book()
        chunks = _make_chunks()
        patches, mocks = _patch_stages(parsed_book=parsed_book, chunks=chunks)
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        export_call = mocks["exporter"].return_value.export.call_args
        assert export_call is not None
        # export(segments, chunks, metadata, config)
        _segments, _chunks, metadata, passed_config = export_call.args
        assert metadata == parsed_book.metadata
        assert passed_config is config


# ---------------------------------------------------------------------------
# Tests — empty-chunks guard
# ---------------------------------------------------------------------------


class TestPipelineEmptyChunks:
    def test_tts_not_called_when_no_chunks(self):
        patches, mocks = _patch_stages(chunks=[])
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["tts"].return_value.synthesize.assert_not_called()

    def test_exporter_not_called_when_no_chunks(self):
        patches, mocks = _patch_stages(chunks=[])
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            Pipeline(config).run()

        mocks["exporter"].return_value.export.assert_not_called()

    def test_run_returns_without_error_when_no_chunks(self):
        patches, mocks = _patch_stages(chunks=[])
        config = _make_config()

        with (
            patches["FB2Parser"],
            patches["TextCleaner"],
            patches["Chunker"],
            patches["TTSEngine"],
            patches["AudioProcessor"],
            patches["AudioExporter"],
        ):
            # Should not raise.
            Pipeline(config).run()
