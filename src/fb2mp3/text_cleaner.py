"""Stage 2 — Text Cleaner.

Normalises and sanitises the ``text`` field of every :class:`TextBlock` in a
:class:`ParsedBook`, then removes blocks that are empty after cleaning.
"""
from __future__ import annotations

import logging
import re
import unicodedata

from .models import ParsedBook

logger = logging.getLogger(__name__)

# Characters that should be silently removed.
_STRIP_CHARS = (
    "\u00ad"  # SOFT HYPHEN
    "\u200b"  # ZERO WIDTH SPACE
    "\ufeff"  # ZERO WIDTH NO-BREAK SPACE / BOM
    "\u200c"  # ZERO WIDTH NON-JOINER
    "\u200d"  # ZERO WIDTH JOINER
)
_STRIP_RE = re.compile(f"[{re.escape(_STRIP_CHARS)}]")

# Any sequence of whitespace characters (including newlines, tabs, etc.)
# is collapsed to a single ASCII space.
_WHITESPACE_RE = re.compile(r"\s+")


class TextCleaner:
    """Apply normalisation and sanitisation to every text block in a book."""

    def clean(self, book: ParsedBook) -> ParsedBook:
        """Clean all :class:`TextBlock` objects in *book* in-place.

        Empty blocks (after cleaning) are removed.  The same *book* object
        is returned for convenient chaining.
        """
        cleaned_blocks = []
        for block in book.blocks:
            block.text = self.clean_text(block.text)
            if block.text:
                cleaned_blocks.append(block)

        dropped = len(book.blocks) - len(cleaned_blocks)
        if dropped:
            logger.debug("Text cleaner dropped %d empty block(s)", dropped)

        book.blocks = cleaned_blocks
        return book

    def clean_text(self, text: str) -> str:
        """Apply the full cleaning pipeline to a single string.

        Steps (in order):

        1. Unicode NFC normalisation.
        2. Remove soft hyphens and zero-width characters.
        3. Collapse runs of whitespace/newlines to a single space.
        4. Strip leading/trailing whitespace.
        """
        # Step 1 — Unicode NFC normalisation
        text = unicodedata.normalize("NFC", text)
        # Step 2 — Remove soft hyphens and zero-width characters
        text = _STRIP_RE.sub("", text)
        # Step 3 — Collapse whitespace
        text = _WHITESPACE_RE.sub(" ", text)
        # Step 4 — Strip edges
        text = text.strip()
        return text
