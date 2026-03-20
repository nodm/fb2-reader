"""Tests for fb2mp3.fb2_parser (Stage 1)."""
from __future__ import annotations

import textwrap

import pytest

from fb2mp3.fb2_parser import FB2Parser
from fb2mp3.models import ParsedBook

import os

SAMPLE_FB2 = os.path.join(os.path.dirname(__file__), "fixtures", "sample.fb2")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fb2(body_xml: str, meta_xml: str = "") -> str:
    """Return a minimal FB2 XML string."""
    if not meta_xml:
        meta_xml = textwrap.dedent("""\
            <title-info>
              <book-title>Test Book</book-title>
              <author><first-name>John</first-name><last-name>Smith</last-name></author>
              <lang>en</lang>
            </title-info>
        """)
    # NOTE: the XML declaration MUST be on the very first line with no leading whitespace.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n'
        "  <description>\n"
        f"    {meta_xml.strip()}\n"
        "  </description>\n"
        "  <body>\n"
        f"    {body_xml.strip()}\n"
        "  </body>\n"
        "</FictionBook>\n"
    )


def _write_fb2(tmp_path, content: str) -> str:
    path = tmp_path / "book.fb2"
    path.write_text(content, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFB2ParserMetadata:
    def test_parses_title(self, tmp_path):
        fb2 = _make_fb2("<section><p>Hello</p></section>")
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        assert book.metadata.title == "Test Book"

    def test_parses_author(self, tmp_path):
        fb2 = _make_fb2("<section><p>Hello</p></section>")
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        assert book.metadata.author == "John Smith"

    def test_parses_language(self, tmp_path):
        fb2 = _make_fb2("<section><p>Hello</p></section>")
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        assert book.metadata.language == "en"

    def test_missing_metadata_defaults(self, tmp_path):
        """If metadata is absent, sensible defaults are used."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n'
            "  <description></description>\n"
            "  <body><section><p>Hi</p></section></body>\n"
            "</FictionBook>\n"
        )
        path = _write_fb2(tmp_path, xml)
        book = FB2Parser().parse(path)
        assert book.metadata.title == "Unknown Title"
        assert book.metadata.author == "Unknown Author"
        assert book.metadata.language == "en"


class TestFB2ParserBlocks:
    def test_extracts_paragraphs(self, tmp_path):
        fb2 = _make_fb2("<section><p>First</p><p>Second</p></section>")
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        texts = [b.text for b in book.blocks]
        assert "First" in texts
        assert "Second" in texts

    def test_chapter_title_from_section_title(self, tmp_path):
        fb2 = _make_fb2(
            "<section><title><p>My Chapter</p></title><p>Body text.</p></section>"
        )
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        # The paragraph's block should carry the chapter title.
        para_blocks = [b for b in book.blocks if b.text == "Body text."]
        assert para_blocks, "Expected a block with 'Body text.'"
        assert para_blocks[0].chapter_title == "My Chapter"

    def test_multiple_sections_increment_chapter_index(self, tmp_path):
        fb2 = _make_fb2(
            "<section><p>A</p></section><section><p>B</p></section>"
        )
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        indices = [b.chapter_index for b in book.blocks]
        assert 0 in indices
        assert 1 in indices

    def test_returns_parsed_book_type(self, tmp_path):
        fb2 = _make_fb2("<section><p>Hi</p></section>")
        path = _write_fb2(tmp_path, fb2)
        result = FB2Parser().parse(path)
        assert isinstance(result, ParsedBook)

    def test_subtitle_extracted_as_block(self, tmp_path):
        fb2 = _make_fb2("<section><subtitle>My subtitle</subtitle></section>")
        path = _write_fb2(tmp_path, fb2)
        book = FB2Parser().parse(path)
        texts = [b.text for b in book.blocks]
        assert "My subtitle" in texts


class TestFB2ParserFixtureFile:
    def test_parse_sample_fb2(self):
        book = FB2Parser().parse(SAMPLE_FB2)
        assert book.metadata.title == "Sample Book"
        assert book.metadata.author == "Jane Doe"
        assert book.metadata.language == "en"
        assert len(book.blocks) >= 3

    def test_chapter_titles_present(self):
        book = FB2Parser().parse(SAMPLE_FB2)
        titles = {b.chapter_title for b in book.blocks}
        assert "Chapter One" in titles
        assert "Chapter Two" in titles


class TestFB2ParserErrors:
    def test_raises_value_error_on_invalid_xml(self, tmp_path):
        path = tmp_path / "bad.fb2"
        path.write_text("THIS IS NOT XML", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed"):
            FB2Parser().parse(str(path))

    def test_raises_value_error_on_wrong_root_element(self, tmp_path):
        """Valid XML but not a FictionBook 2 document should raise ValueError."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<html><body><p>Not an FB2 file</p></body></html>\n"
        )
        path = tmp_path / "not_fb2.xml"
        path.write_text(xml, encoding="utf-8")
        with pytest.raises(ValueError, match="FictionBook 2"):
            FB2Parser().parse(str(path))

    def test_raises_value_error_on_wrong_namespace(self, tmp_path):
        """Valid XML with a FictionBook root but wrong namespace should raise ValueError."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FictionBook xmlns="http://example.com/wrong-namespace">\n'
            "  <body><section><p>text</p></section></body>\n"
            "</FictionBook>\n"
        )
        path = tmp_path / "wrong_ns.fb2"
        path.write_text(xml, encoding="utf-8")
        with pytest.raises(ValueError, match="FictionBook 2"):
            FB2Parser().parse(str(path))

    def test_notes_body_skipped(self, tmp_path):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n'
            "  <description>\n"
            "    <title-info>\n"
            "      <book-title>T</book-title><lang>en</lang>\n"
            "    </title-info>\n"
            "  </description>\n"
            "  <body>\n"
            "    <section><p>Main content</p></section>\n"
            "  </body>\n"
            '  <body name="notes">\n'
            "    <section><p>Should be ignored</p></section>\n"
            "  </body>\n"
            "</FictionBook>\n"
        )
        path = _write_fb2(tmp_path, xml)
        book = FB2Parser().parse(path)
        texts = [b.text for b in book.blocks]
        assert "Main content" in texts
        assert "Should be ignored" not in texts
