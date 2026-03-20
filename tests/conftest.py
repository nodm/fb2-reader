"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import os

import pytest

from fb2mp3.models import BookMetadata, Chunk, ParsedBook, TextBlock

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_FB2 = os.path.join(FIXTURES_DIR, "sample.fb2")


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_metadata() -> BookMetadata:
    return BookMetadata(title="Sample Book", author="Jane Doe", language="en")


@pytest.fixture()
def sample_blocks() -> list[TextBlock]:
    return [
        TextBlock(chapter_index=0, chapter_title="Chapter One", text="Hello world."),
        TextBlock(chapter_index=0, chapter_title="Chapter One", text="Second sentence."),
        TextBlock(chapter_index=1, chapter_title="Chapter Two", text="Another chapter."),
    ]


@pytest.fixture()
def sample_book(sample_metadata, sample_blocks) -> ParsedBook:
    return ParsedBook(metadata=sample_metadata, blocks=list(sample_blocks))


@pytest.fixture()
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(chapter_index=0, chapter_title="Chapter One", index=0, text="Hello world."),
        Chunk(chapter_index=0, chapter_title="Chapter One", index=1, text="Second sentence."),
        Chunk(chapter_index=1, chapter_title="Chapter Two", index=2, text="Another chapter."),
    ]
