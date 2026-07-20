"""Thin wrapper around OpenRouter (OpenAI-compatible). Every AI call in the app goes
through here."""

import logging
import os
import time
from typing import TypeVar

import openai
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("llm_client")

MODEL_NAME = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = 2

T = TypeVar("T", bound=BaseModel)

# In-memory call counter. Resets on process restart -- same tradeoff as the
# rest of this app's in-memory state; this is for at-a-glance visibility
# during testing/demos, not a durable usage record.
call_count = 0


class LLMError(Exception):
    """Raised when an LLM call fails or returns something we can't use."""


def _get_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


def generate_structured(
    prompt: str,
    response_schema: type[T],
    system_instruction: str | None = None,
) -> T:
    """Call the LLM and return a response validated against a Pydantic schema.

    Retries with exponential backoff on rate-limit errors -- openai.RateLimitError
    is a proper typed exception here, unlike the Gemini SDK, which only gave us a
    generic exception we had to string-match. Other failures (bad key, schema
    mismatch) fail immediately instead.
    """
    global call_count
    client = _get_client()
    schema_name = response_schema.__name__

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": response_schema.model_json_schema(),
        },
    }

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        call_count += 1
        logger.info(
            "LLM call #%d: schema=%s attempt=%d", call_count, schema_name, attempt + 1
        )
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                response_format=response_format,
            )
            break
        except openai.RateLimitError as exc:
            if attempt < MAX_RATE_LIMIT_RETRIES:
                logger.warning("LLM call #%d: rate limited, retrying", call_count)
                time.sleep(RATE_LIMIT_BACKOFF_SECONDS * (2**attempt))
                continue
            logger.error("LLM call #%d: rate limit retries exhausted", call_count)
            raise LLMError(f"LLM API call failed after retries: {exc}") from exc
        except Exception as exc:
            logger.error("LLM call #%d: failed: %s", call_count, exc)
            raise LLMError(f"LLM API call failed: {exc}") from exc

    content = response.choices[0].message.content
    if not content:
        raise LLMError("LLM returned an empty response.")

    try:
        return response_schema.model_validate_json(content)
    except Exception as exc:
        raise LLMError(f"LLM response didn't match the expected schema: {exc}") from exc
