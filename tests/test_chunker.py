"""Tests for fb2mp3.chunker (Stage 3)."""
from __future__ import annotations

import pytest

from fb2mp3.chunker import Chunker
from fb2mp3.models import BookMetadata, ParsedBook, TextBlock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(*texts: str, lang: str = "en") -> ParsedBook:
    blocks = [
        TextBlock(chapter_index=i, chapter_title=f"Ch {i}", text=t)
        for i, t in enumerate(texts)
    ]
    return ParsedBook(
        metadata=BookMetadata(title="T", author="A", language=lang),
        blocks=blocks,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChunkerBasic:
    def test_short_text_single_chunk(self):
        book = _make_book("Hello world.")
        chunks = Chunker("en").chunk(book)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."

    def test_chunk_index_is_global(self):
        book = _make_book("First.", "Second.", "Third.")
        chunks = Chunker("en").chunk(book)
        indices = [c.index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_carries_chapter_metadata(self):
        book = _make_book("Hello world.")
        chunks = Chunker("en").chunk(book)
        assert chunks[0].chapter_index == 0
        assert chunks[0].chapter_title == "Ch 0"

    def test_empty_book_produces_no_chunks(self):
        book = ParsedBook(
            metadata=BookMetadata(title="T", author="A", language="en"),
            blocks=[],
        )
        assert Chunker("en").chunk(book) == []


class TestChunkerLength:
    def test_all_chunks_within_max_chars(self):
        long_text = " ".join(["word"] * 500)  # well over 250 chars
        book = _make_book(long_text)
        chunks = Chunker("en").chunk(book)
        for chunk in chunks:
            assert len(chunk.text) <= Chunker.MAX_CHARS, (
                f"Chunk exceeds MAX_CHARS: {chunk.text!r}"
            )

    def test_long_sentence_is_split(self):
        # 300 chars of continuous text with no sentence boundary
        long_sentence = "A" * 300
        book = _make_book(long_sentence)
        chunks = Chunker("en").chunk(book)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk.text) <= Chunker.MAX_CHARS

    def test_greedy_accumulation(self):
        # Two short sentences that together fit within MAX_CHARS.
        s1 = "Short sentence one."
        s2 = "Short sentence two."
        assert len(s1) + 1 + len(s2) <= Chunker.MAX_CHARS
        book = _make_book(f"{s1} {s2}")
        chunks = Chunker("en").chunk(book)
        # Both sentences should end up in the same chunk.
        assert len(chunks) == 1

    def test_sentences_that_exceed_limit_go_to_new_chunk(self):
        # Build text whose sentences together exceed 250 chars.
        sentence = "x" * 130 + "."
        text = f"{sentence} {sentence}"  # 130+1+130+1 = 263, each sentence 131 chars
        book = _make_book(text)
        chunks = Chunker("en").chunk(book)
        # Each sentence should be in its own chunk.
        assert len(chunks) >= 2


class TestChunkerLanguages:
    @pytest.mark.parametrize("lang", ["en", "uk", "ru"])
    def test_supported_languages(self, lang):
        book = _make_book("Sentence one. Sentence two.", lang=lang)
        chunks = Chunker(lang).chunk(book)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk.text) <= Chunker.MAX_CHARS

    def test_unknown_language_defaults_gracefully(self):
        # An unsupported lang code should fall back to "english" without raising.
        book = _make_book("Hello world.")
        chunks = Chunker("xx").chunk(book)  # "xx" is not in the lang map
        assert len(chunks) == 1
