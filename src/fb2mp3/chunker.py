"""Stage 3 — Sentence Chunker.

Splits :class:`TextBlock` objects into :class:`Chunk` objects whose ``text``
length does not exceed :attr:`Chunker.MAX_CHARS` (250 characters), splitting
at sentence boundaries wherever possible.
"""
from __future__ import annotations

import logging
from typing import List

import nltk

from .models import Chunk, ParsedBook, TextBlock

logger = logging.getLogger(__name__)

# Map pipeline language codes to NLTK language names.
_LANG_MAP: dict[str, str] = {
    "en": "english",
    "uk": "ukrainian",
    "ru": "russian",
}


class Chunker:
    """Split a :class:`ParsedBook` into TTS-ready :class:`Chunk` objects."""

    MAX_CHARS: int = 250

    def __init__(self, lang: str) -> None:
        # Download NLTK tokenizer data on first instantiation (quiet = no stdout noise).
        nltk.download("punkt_tab", quiet=True)
        nltk_lang = _LANG_MAP.get(lang, "english")
        self._nltk_lang = nltk_lang
        logger.debug("Chunker initialised with NLTK language '%s'", nltk_lang)

    def chunk(self, book: ParsedBook) -> List[Chunk]:
        """Return an ordered list of :class:`Chunk` objects for *book*."""
        chunks: List[Chunk] = []
        for block in book.blocks:
            new_chunks = self._chunk_block(block, len(chunks))
            chunks.extend(new_chunks)
        logger.info("Chunker produced %d chunk(s) from %d block(s)", len(chunks), len(book.blocks))
        return chunks

    def _chunk_block(self, block: TextBlock, start_index: int) -> List[Chunk]:
        """Split a single :class:`TextBlock` into one or more :class:`Chunk` objects."""
        try:
            sentences = nltk.sent_tokenize(block.text, language=self._nltk_lang)
        except LookupError:
            logger.warning(
                "NLTK punkt_tab tokenizer not available for language '%s'; "
                "falling back to 'english'.",
                self._nltk_lang,
            )
            sentences = nltk.sent_tokenize(block.text, language="english")

        result: List[Chunk] = []
        buffer = ""
        chunk_index = start_index

        def _flush(text: str) -> None:
            nonlocal chunk_index
            text = text.strip()
            if text:
                result.append(
                    Chunk(
                        chapter_index=block.chapter_index,
                        chapter_title=block.chapter_title,
                        index=chunk_index,
                        text=text,
                    )
                )
                chunk_index += 1

        for sentence in sentences:
            # If a single sentence exceeds MAX_CHARS, split it hard at the
            # last whitespace before the limit.
            if len(sentence) > self.MAX_CHARS:
                # Flush any existing buffer first.
                if buffer:
                    _flush(buffer)
                    buffer = ""
                for fragment in self._split_long_sentence(sentence):
                    _flush(fragment)
                continue

            # Would adding this sentence push the buffer past the limit?
            candidate = (buffer + " " + sentence).strip() if buffer else sentence
            if len(candidate) <= self.MAX_CHARS:
                buffer = candidate
            else:
                # Flush the current buffer and start a new one with this sentence.
                _flush(buffer)
                buffer = sentence

        # Flush any remaining text.
        if buffer:
            _flush(buffer)

        return result

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """Break *sentence* (which exceeds MAX_CHARS) at whitespace boundaries."""
        fragments: List[str] = []
        while len(sentence) > self.MAX_CHARS:
            # Find the last space within the limit.
            cut = sentence.rfind(" ", 0, self.MAX_CHARS)
            if cut == -1:
                # No whitespace found — hard-cut at the limit.
                cut = self.MAX_CHARS
            fragments.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            fragments.append(sentence)
        return fragments
