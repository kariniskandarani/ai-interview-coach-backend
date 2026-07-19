"""Manual, one-off check that profiler.py produces sensible output against the real
Gemini API. Not part of the pytest suite on purpose — makes a real network call.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_profiler.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm_client import LLMError
from src.profiler import build_candidate_profile
from scripts.sample_data import SAMPLE_CV, SAMPLE_JD


def main():
    try:
        profile = build_candidate_profile(cv_text=SAMPLE_CV, job_description=SAMPLE_JD)
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print("SUCCESS — got a validated CandidateProfile back:")
    print(f"  seniority: {profile.seniority}")
    print(f"  role_type: {profile.role_type}")
    print(f"  key_skills: {profile.key_skills}")
    print(f"  skill_gaps: {profile.skill_gaps}")
    print(f"  strengths_summary: {profile.strengths_summary}")


if __name__ == "__main__":
    main()
