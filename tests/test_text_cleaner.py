"""Tests for fb2mp3.text_cleaner (Stage 2)."""
from __future__ import annotations

import pytest

from fb2mp3.models import ParsedBook, TextBlock, BookMetadata
from fb2mp3.text_cleaner import TextCleaner


# ---------------------------------------------------------------------------
# clean_text unit tests
# ---------------------------------------------------------------------------


class TestCleanTextUnicode:
    def test_nfc_normalisation(self):
        # NFD form of "é" (e + combining accent) → should become NFC "é"
        nfd = "e\u0301"  # NFD
        result = TextCleaner().clean_text(nfd)
        assert result == "\xe9"  # NFC

    def test_removes_soft_hyphens(self):
        assert TextCleaner().clean_text("word\u00adbreak") == "wordbreak"

    def test_removes_zero_width_space(self):
        assert TextCleaner().clean_text("zero\u200bwidth") == "zerowidth"

    def test_removes_bom(self):
        assert TextCleaner().clean_text("\ufefftext") == "text"

    def test_removes_zero_width_non_joiner(self):
        assert TextCleaner().clean_text("a\u200cb") == "ab"

    def test_removes_zero_width_joiner(self):
        assert TextCleaner().clean_text("a\u200db") == "ab"


class TestCleanTextWhitespace:
    def test_collapses_multiple_spaces(self):
        assert TextCleaner().clean_text("hello   world") == "hello world"

    def test_collapses_newlines(self):
        assert TextCleaner().clean_text("hello\nworld") == "hello world"

    def test_collapses_mixed_whitespace(self):
        assert TextCleaner().clean_text("a\t\n  b") == "a b"

    def test_strips_leading_trailing(self):
        assert TextCleaner().clean_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert TextCleaner().clean_text("") == ""

    def test_whitespace_only(self):
        assert TextCleaner().clean_text("   ") == ""


class TestCleanTextPreservesNormal:
    def test_normal_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert TextCleaner().clean_text(text) == text

    def test_cyrillic_text(self):
        text = "Привіт світ"
        assert TextCleaner().clean_text(text) == text


# ---------------------------------------------------------------------------
# clean (ParsedBook) integration tests
# ---------------------------------------------------------------------------


class TestCleanBook:
    def _make_book(self, texts: list[str]) -> ParsedBook:
        blocks = [
            TextBlock(chapter_index=0, chapter_title=None, text=t) for t in texts
        ]
        return ParsedBook(
            metadata=BookMetadata(title="T", author="A", language="en"),
            blocks=blocks,
        )

    def test_cleans_all_blocks(self):
        book = self._make_book(["  hello  ", "world\u00ad!"])
        result = TextCleaner().clean(book)
        assert result.blocks[0].text == "hello"
        assert result.blocks[1].text == "world!"

    def test_removes_empty_blocks_after_cleaning(self):
        book = self._make_book(["  ", "\u200b", "valid text"])
        result = TextCleaner().clean(book)
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "valid text"

    def test_returns_same_book_object(self):
        book = self._make_book(["hello"])
        result = TextCleaner().clean(book)
        assert result is book

    def test_mutates_block_text_in_place(self):
        book = self._make_book(["  hello  "])
        TextCleaner().clean(book)
        assert book.blocks[0].text == "hello"
