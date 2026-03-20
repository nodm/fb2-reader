"""Stage 1 — FB2 Parser.

Parses a .fb2 (FictionBook 2) XML file and returns a :class:`ParsedBook`
containing structured metadata and an ordered list of :class:`TextBlock`
objects.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from lxml import etree

from .models import BookMetadata, ParsedBook, TextBlock

logger = logging.getLogger(__name__)

# The canonical FB2 XML namespace.
FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"
NS = {"fb": FB2_NS}


def _tag(local: str) -> str:
    """Return the Clark-notation qualified name for a FB2 element."""
    return f"{{{FB2_NS}}}{local}"


class FB2Parser:
    """Parse an FB2 file into a :class:`ParsedBook`."""

    def parse(self, path: str) -> ParsedBook:
        """Parse *path* and return a :class:`ParsedBook`.

        Raises
        ------
        ValueError
            If the file cannot be parsed as valid XML or does not look like
            a FictionBook 2 document.
        """
        try:
            tree = etree.parse(path)  # noqa: S320 – local files only
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Malformed FB2/XML file '{path}': {exc}") from exc

        root = tree.getroot()
        if root.tag != _tag("FictionBook"):
            raise ValueError(
                f"'{path}' does not appear to be a FictionBook 2 document "
                f"(root tag: {root.tag!r})"
            )
        logger.info("Parsing FB2 file: %s", path)

        metadata = self._extract_metadata(root)
        blocks = self._extract_blocks(root)

        logger.info(
            "Parsed '%s' — %d text blocks extracted", metadata.title, len(blocks)
        )
        return ParsedBook(metadata=metadata, blocks=blocks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_metadata(self, root: etree._Element) -> BookMetadata:
        """Extract :class:`BookMetadata` from the FB2 ``<description>`` block."""
        title = self._first_text(root, ".//fb:description/fb:title-info/fb:book-title")
        lang = self._first_text(root, ".//fb:description/fb:title-info/fb:lang")

        # Build author string from first-name / middle-name / last-name.
        author_el = root.find(
            ".//fb:description/fb:title-info/fb:author", namespaces=NS
        )
        author = self._format_author(author_el)

        return BookMetadata(
            title=title or "Unknown Title",
            author=author or "Unknown Author",
            language=lang or "en",
        )

    def _format_author(self, author_el: Optional[etree._Element]) -> str:
        if author_el is None:
            return ""
        parts = []
        for tag in ("first-name", "middle-name", "last-name"):
            el = author_el.find(f"fb:{tag}", namespaces=NS)
            if el is not None and el.text:
                parts.append(el.text.strip())
        return " ".join(parts)

    def _extract_blocks(self, root: etree._Element) -> List[TextBlock]:
        """Walk ``<body>`` → ``<section>`` elements and collect text blocks."""
        blocks: List[TextBlock] = []
        chapter_index = 0

        # Process each top-level body (there is usually only one).
        for body in root.findall("fb:body", namespaces=NS):
            # Skip footnote / notes bodies.
            body_name = body.get("name", "")
            if body_name in ("notes", "footnotes", "comments"):
                continue

            for section in body.findall("fb:section", namespaces=NS):
                self._process_section(section, chapter_index, None, blocks)
                chapter_index += 1

        return blocks

    def _process_section(
        self,
        section: etree._Element,
        chapter_index: int,
        parent_title: Optional[str],
        blocks: List[TextBlock],
    ) -> None:
        """Recursively process a ``<section>`` element."""
        # Skip sections marked as notes / footnotes.
        section_type = section.get("type", "")
        if section_type in ("notes", "footnotes"):
            return

        # Extract the chapter title from the section's <title> child (if any).
        chapter_title = parent_title
        title_el = section.find("fb:title", namespaces=NS)
        if title_el is not None:
            title_text = self._text_from_element(title_el).strip()
            if title_text:
                chapter_title = title_text

        for child in section:
            local = etree.QName(child.tag).localname if child.tag != etree.Comment else None
            if local is None:
                continue

            if local == "title":
                # Already processed above.
                continue
            elif local in ("p", "subtitle"):
                text = self._text_from_element(child).strip()
                if text:
                    blocks.append(
                        TextBlock(
                            chapter_index=chapter_index,
                            chapter_title=chapter_title,
                            text=text,
                        )
                    )
            elif local == "section":
                # Nested section — flatten into the parent chapter's chapter_index.
                # Sub-sections share the parent chapter index; only top-level body
                # sections increment the counter.
                self._process_section(child, chapter_index, chapter_title, blocks)

    def _text_from_element(self, el: etree._Element) -> str:
        """Return all text content within *el*, including tail text of children."""
        parts = []
        if el.text:
            parts.append(el.text)
        for child in el:
            # Recurse to handle inline elements like <emphasis>, <strong>, etc.
            parts.append(self._text_from_element(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    def _first_text(self, root: etree._Element, xpath: str) -> Optional[str]:
        """Return the text of the first element matching *xpath*, or ``None``."""
        el = root.find(xpath, namespaces=NS)
        if el is not None and el.text:
            return el.text.strip()
        return None
