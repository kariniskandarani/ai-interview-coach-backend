import io

import pytest
from fpdf import FPDF, XPos, YPos

from src.document_processor import (
    DocumentProcessingError,
    clean_job_description,
    clean_text,
    extract_text_from_pdf,
)


def make_pdf_bytes(text: str) -> io.BytesIO:
    """Build a minimal real PDF in memory so tests exercise the actual pdfplumber path."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.splitlines():
        pdf.cell(0, 10, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    buffer = io.BytesIO(pdf.output())
    buffer.seek(0)
    return buffer


def test_clean_text_collapses_whitespace_and_blank_lines():
    messy = "Line one\t\t here\n\n\n\nLine two   with   spaces\n\n\n"
    assert clean_text(messy) == "Line one here\n\nLine two with spaces"


def test_clean_job_description_rejects_empty_text():
    with pytest.raises(DocumentProcessingError):
        clean_job_description("   too short   ")


def test_clean_job_description_returns_cleaned_text():
    result = clean_job_description("  Senior Engineer role.\n\n\nRequires Python.  ")
    assert result == "Senior Engineer role.\n\nRequires Python."


def test_extract_text_from_pdf_reads_real_content():
    pdf_bytes = make_pdf_bytes("Jane Doe\nSoftware Engineer\n5 years experience in Python")
    text = extract_text_from_pdf(pdf_bytes)
    assert "Jane Doe" in text
    assert "Software Engineer" in text


def test_extract_text_from_pdf_rejects_empty_pdf():
    pdf = FPDF()
    pdf.add_page()
    buffer = io.BytesIO(pdf.output())
    buffer.seek(0)

    with pytest.raises(DocumentProcessingError):
        extract_text_from_pdf(buffer)


def test_extract_text_from_pdf_rejects_garbage_input():
    garbage = io.BytesIO(b"this is not a pdf file")
    with pytest.raises(DocumentProcessingError):
        extract_text_from_pdf(garbage)
