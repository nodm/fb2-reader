"""Shared data models for the FB2-to-MP3 pipeline."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BookMetadata:
    """Metadata extracted from an FB2 file's <description> block."""

    title: str
    author: str
    language: str  # e.g. "en", "uk", "ru"


@dataclass
class TextBlock:
    """A single addressable unit of text within the book."""

    chapter_index: int            # 0-based chapter number
    chapter_title: Optional[str]  # human-readable chapter heading
    text: str                     # cleaned prose text


@dataclass
class ParsedBook:
    """Output of Stage 1 (FB2 Parser)."""

    metadata: BookMetadata
    blocks: List[TextBlock]  # ordered list of all text blocks


@dataclass
class Chunk:
    """A single TTS-ready text fragment produced by Stage 3."""

    chapter_index: int
    chapter_title: Optional[str]
    index: int   # global position across all chapters
    text: str    # <= 250 characters
