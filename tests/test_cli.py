"""Tests for fb2mp3.cli (entry-point argument parsing and validation)."""
from __future__ import annotations

import pytest

from fb2mp3.cli import build_parser, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_args(tmp_path) -> list[str]:
    """Return a minimal valid argument list with a real .fb2 file."""
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        "<body><section><p>hi</p></section></body>"
        "</FictionBook>",
        encoding="utf-8",
    )
    return [str(fb2), "--lang", "en", "--speaker", "Ana Florence"]


# ---------------------------------------------------------------------------
# Tests — --output / --split-chapters interaction
# ---------------------------------------------------------------------------


class TestSplitChaptersOutputValidation:
    def test_output_mp3_with_split_chapters_raises(self, tmp_path):
        """Passing a .mp3 filename as --output with --split-chapters should error."""
        args = _base_args(tmp_path) + ["--output", "audiobook.mp3", "--split-chapters"]
        with pytest.raises(SystemExit):
            main(args)

    def test_output_directory_with_split_chapters_accepted(self, tmp_path, monkeypatch):
        """A non-.mp3 path for --output with --split-chapters should be accepted."""
        # We don't want to actually run the pipeline, so monkeypatch Pipeline.run.
        from fb2mp3 import pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod.Pipeline, "run", lambda self: None)
        args = _base_args(tmp_path) + [
            "--output",
            str(tmp_path / "chapters"),
            "--split-chapters",
        ]
        # Should not raise.
        main(args)

    def test_output_mp3_without_split_chapters_accepted(self, tmp_path, monkeypatch):
        """A .mp3 filename for --output without --split-chapters is valid."""
        from fb2mp3 import pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod.Pipeline, "run", lambda self: None)
        args = _base_args(tmp_path) + ["--output", "audiobook.mp3"]
        # Should not raise.
        main(args)
