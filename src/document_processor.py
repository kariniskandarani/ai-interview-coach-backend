"""Turns raw user input (an uploaded CV PDF, a pasted job description) into clean text."""

import re

import pdfplumber


class DocumentProcessingError(Exception):
    """Raised when a document can't be turned into usable text."""


def extract_text_from_pdf(file) -> str:
    """Extract and clean text from an uploaded PDF file-like object."""
    try:
        with pdfplumber.open(file) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:
        raise DocumentProcessingError(f"Could not read PDF: {exc}") from exc

    text = clean_text("\n".join(pages_text))

    if len(text) < 50:
        raise DocumentProcessingError(
            "No readable text found in this PDF. It may be a scanned image "
            "without a text layer — try exporting the CV as a text-based PDF."
        )

    return text


def clean_job_description(text: str) -> str:
    """Clean a pasted job description and validate it isn't empty."""
    text = clean_text(text)

    if len(text) < 20:
        raise DocumentProcessingError(
            "Job description looks empty — paste the full listing."
        )

    return text


def clean_text(text: str) -> str:
    """Collapse repeated whitespace and blank lines from extracted/pasted text."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
