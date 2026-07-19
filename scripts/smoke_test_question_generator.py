"""Manual, one-off check of the profiler -> question_generator pipeline against the
real Gemini API. Not part of the pytest suite on purpose — makes real network calls.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_question_generator.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm_client import LLMError
from src.profiler import build_candidate_profile
from src.question_generator import generate_questions
from scripts.sample_data import SAMPLE_CV, SAMPLE_JD


def main():
    try:
        profile = build_candidate_profile(cv_text=SAMPLE_CV, job_description=SAMPLE_JD)
        question_set = generate_questions(profile)
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print(f"SUCCESS — got {len(question_set.questions)} questions for a "
          f"{profile.seniority} {profile.role_type}:\n")
    for i, q in enumerate(question_set.questions, start=1):
        print(f"{i}. [{q.category}] {q.text}")
        print(f"   (target: {q.target_area})\n")


if __name__ == "__main__":
    main()
