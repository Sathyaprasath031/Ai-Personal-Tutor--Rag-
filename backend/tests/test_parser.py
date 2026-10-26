"""Unit tests for the multi-format document parser."""

import os
import tempfile
import pytest
from app.ingestion.parser import parse_file, parse_text, Block


def test_parse_text_file():
    content = """# Chapter 1: Newton's Laws

Newton's first law of motion states that an object at rest stays at rest.

# Chapter 2: Momentum

Momentum is defined as the product of mass and velocity.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        temp_path = f.name

    try:
        parsed = parse_file(temp_path)
        assert parsed.page_count == 1
        assert len(parsed.blocks) == 4

        # Check headings and contents
        assert parsed.blocks[0].is_heading is True
        assert parsed.blocks[0].text == "Chapter 1: Newton's Laws"

        assert parsed.blocks[1].is_heading is False
        assert "Newton's first law" in parsed.blocks[1].text

        assert parsed.blocks[2].is_heading is True
        assert parsed.blocks[2].text == "Chapter 2: Momentum"

        assert parsed.blocks[3].is_heading is False
        assert "Momentum is defined" in parsed.blocks[3].text
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_unsupported_file_extension():
    with tempfile.NamedTemporaryFile("w", suffix=".xyz", delete=False) as f:
        f.write("Some text")
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            parse_file(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_parse_pdf_file():
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed yet")

    # Create a small in-memory/temp PDF using fitz
    doc = fitz.open()
    page = doc.new_page()
    # Insert heading with large font size 18
    page.insert_text((50, 72), "Thermodynamics Overview", fontsize=18)
    # Insert body with regular font size 11
    page.insert_text((50, 100), "The first law of thermodynamics is an adaptation of the law of conservation of energy.", fontsize=11)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_path = f.name
    doc.save(temp_path)
    doc.close()

    try:
        parsed = parse_file(temp_path)
        assert parsed.page_count == 1
        assert len(parsed.blocks) >= 2
        # Verify text was extracted
        full_text = " ".join(b.text for b in parsed.blocks)
        assert "Thermodynamics Overview" in full_text
        assert "conservation of energy" in full_text
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
