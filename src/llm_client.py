"""Thin wrapper around the Gemini API. Every AI call in the app goes through here."""

import os
import time
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = 2

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


def _is_daily_quota_error(exc: Exception) -> bool:
    """True for the free tier's requests-per-day quota specifically -- this
    cannot clear within seconds/minutes no matter how long we back off, so
    retrying it is pure wasted time and should fail immediately instead."""
    return "PerDay" in str(exc)


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return "429" in message or "RESOURCE_EXHAUSTED" in message


def generate_structured(
    prompt: str,
    response_schema: type[T],
    system_instruction: str | None = None,
) -> T:
    """Call Gemini and return a response validated against a Pydantic schema.

    Retries with exponential backoff on rate-limit (429) errors, EXCEPT
    daily-quota exhaustion specifically, which cannot clear on any retry
    timescale we'd want to block a request for -- that fails immediately
    with a clear message instead of wasting time retrying something that
    will keep failing until the daily window resets.
    """
    client = _get_client()

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
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
            break
        except Exception as exc:
            if _is_daily_quota_error(exc):
                raise LLMError(
                    "Gemini's free-tier daily quota for this model is exhausted. "
                    "This won't clear by retrying -- try again after the daily "
                    "reset, switch models, or enable billing."
                ) from exc
            if _is_rate_limit_error(exc) and attempt < MAX_RATE_LIMIT_RETRIES:
                time.sleep(RATE_LIMIT_BACKOFF_SECONDS * (2**attempt))
                continue
            raise LLMError(f"Gemini API call failed: {exc}") from exc

    if response.parsed is None:
        raise LLMError("Gemini returned a response that didn't match the expected schema.")

    return response.parsed
