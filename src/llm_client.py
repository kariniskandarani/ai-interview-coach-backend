"""Thin wrapper around the Gemini API. Every AI call in the app goes through here."""

import os
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

MODEL_NAME = "gemini-3.5-flash"

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when a Gemini call fails or returns something we can't use."""


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def generate_structured(
    prompt: str,
    response_schema: type[T],
    system_instruction: str | None = None,
) -> T:
    """Call Gemini and return a response validated against a Pydantic schema."""
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                system_instruction=system_instruction,
            ),
        )
    except Exception as exc:
        raise LLMError(f"Gemini API call failed: {exc}") from exc

    if response.parsed is None:
        raise LLMError("Gemini returned a response that didn't match the expected schema.")

    return response.parsed
