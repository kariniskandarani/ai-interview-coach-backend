"""Manual, one-off check that llm_client.py can actually reach OpenRouter and get a
structured response back. Not part of the pytest suite on purpose — this makes a
real network call and needs a real OPENROUTER_API_KEY.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_llm.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel

from src.llm_client import LLMError, generate_structured


class Greeting(BaseModel):
    message: str
    enthusiasm_level: int


def main():
    try:
        result = generate_structured(
            prompt="Write a one-sentence enthusiastic greeting for someone starting "
            "a Python project, and rate your own enthusiasm from 1-10.",
            response_schema=Greeting,
        )
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print("SUCCESS — got a validated Greeting object back:")
    print(f"  message: {result.message}")
    print(f"  enthusiasm_level: {result.enthusiasm_level}")


if __name__ == "__main__":
    main()
