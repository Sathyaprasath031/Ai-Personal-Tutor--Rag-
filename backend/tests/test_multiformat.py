"""Unit and integration tests for multi-format documents (DOCX, PPTX, OCR fallback)."""

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from app.ingestion.parser import parse_file, parse_docx, parse_pptx, _ocr_page, Block
from app.ingestion.chunker import chunk_document


def test_parse_docx_with_headings():
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    doc = Document()
    doc.add_heading("Database Management Systems", level=1)
    doc.add_paragraph("A database is an organized collection of structured information or data, typically stored electronically in a computer system and controlled by a DBMS.")
    doc.add_heading("ACID Properties", level=2)
    doc.add_paragraph("ACID stands for Atomicity, Consistency, Isolation, and Durability, which are four key properties that guarantee reliable transaction processing in database systems.")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    doc.save(tmp_path)

    try:
        parsed = parse_file(tmp_path)
        assert parsed.page_count == 1
        assert len(parsed.blocks) == 4

        # Verify headings detection
        assert parsed.blocks[0].is_heading is True
        assert parsed.blocks[0].text == "Database Management Systems"

        assert parsed.blocks[1].is_heading is False
        assert "organized collection" in parsed.blocks[1].text

        assert parsed.blocks[2].is_heading is True
        assert parsed.blocks[2].text == "ACID Properties"

        assert parsed.blocks[3].is_heading is False
        assert "Atomicity, Consistency" in parsed.blocks[3].text

        # Test chunking
        chunks = chunk_document(parsed)
        assert len(chunks) == 2
        assert chunks[0].section_path == "Database Management Systems"
        assert chunks[1].section_path == "ACID Properties"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_parse_pptx_slides_and_titles():
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError:
        pytest.skip("python-pptx not installed")

    prs = Presentation()

    # Slide 1: Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_slide_layout)
    title = slide1.shapes.title
    subtitle = slide1.placeholders[1]
    title.text = "Computer Networks: Transport Layer"
    subtitle.text = "Understanding TCP and UDP protocols across modern internet architecture and end-to-end reliable data delivery across packet networks."

    # Slide 2: Content slide
    bullet_slide_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_slide_layout)
    slide2.shapes.title.text = "Transmission Control Protocol (TCP)"
    body_shape = slide2.placeholders[1]
    tf = body_shape.text_frame
    tf.text = "TCP provides reliable, ordered, and error-checked delivery of a stream of octets between applications running on hosts communicating via an IP network."

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = tmp.name
    prs.save(tmp_path)

    try:
        parsed = parse_file(tmp_path)
        assert parsed.page_count == 2
        assert len(parsed.blocks) >= 3

        # Verify slide 1 title is detected as heading
        slide1_blocks = [b for b in parsed.blocks if b.page == 1]
        assert any(b.is_heading and "Transport Layer" in b.text for b in slide1_blocks)

        # Verify slide 2 title is detected as heading
        slide2_blocks = [b for b in parsed.blocks if b.page == 2]
        assert any(b.is_heading and "Transmission Control Protocol" in b.text for b in slide2_blocks)

        # Verify chunking preserves slide page numbers
        chunks = chunk_document(parsed)
        assert len(chunks) >= 1
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_scanned_pdf_ocr_fallback():
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    # Create a 1-page PDF with no extractable text (< 30 chars), triggering OCR fallback
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Hi", fontsize=10)  # Only 2 chars -> triggers len(text) < 30

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    doc.save(tmp_path)
    doc.close()

    try:
        # Mock pytesseract.image_to_string
        with patch("app.ingestion.parser._ocr_page") as mock_ocr:
            mock_ocr.return_value = "Scanned receipt text: Acceleration of gravity is 9.8 m/s^2."

            parsed = parse_file(tmp_path)
            # Should have fallen back to OCR
            mock_ocr.assert_called_once()
            assert parsed.page_count == 1
            assert len(parsed.blocks) == 1
            assert "Acceleration of gravity is 9.8" in parsed.blocks[0].text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
