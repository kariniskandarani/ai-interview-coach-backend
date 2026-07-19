"""Manual, one-off check of the full profiler -> question_generator -> interview_engine
pipeline against the real Gemini API, including a deliberately vague first answer to
confirm the follow-up loop actually triggers. Not part of the pytest suite — real
network calls.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_interview_engine.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interview_engine import InterviewSession
from src.llm_client import LLMError
from src.profiler import build_candidate_profile
from src.question_generator import generate_questions
from src.schemas import QuestionSet
from scripts.sample_data import SAMPLE_CV, SAMPLE_JD

VAGUE_ANSWER = "Uh, I'd probably just look into it and fix it somehow."
STRONG_ANSWER = (
    "In my current role I built and load-tested a rate limiter for our public API using a "
    "token bucket algorithm backed by Redis, which cut abuse-driven downtime to zero."
)


def main():
    try:
        profile = build_candidate_profile(cv_text=SAMPLE_CV, job_description=SAMPLE_JD)
        full_question_set = generate_questions(profile)
        first_two = QuestionSet(questions=full_question_set.questions[:2])
        session = InterviewSession(profile, first_two)

        # Answer the first question vaguely on purpose, to check the follow-up loop triggers.
        print(f"Q1: {session.current_question_text}")
        print(f"A1 (deliberately vague): {VAGUE_ANSWER}\n")
        evaluation = session.submit_answer(VAGUE_ANSWER)
        print(f"   score={evaluation.score} follow_up_needed={evaluation.follow_up_needed}")
        print(f"   star_feedback={evaluation.star_feedback!r}")
        print(f"   clarity_feedback={evaluation.clarity_feedback}\n")

        # Answer everything else (the follow-up, if any, and the remaining question) well.
        while not session.finished:
            print(f"Q: {session.current_question_text}")
            print(f"A (strong): {STRONG_ANSWER}\n")
            evaluation = session.submit_answer(STRONG_ANSWER)
            print(f"   score={evaluation.score} follow_up_needed={evaluation.follow_up_needed}")
            print(f"   star_feedback={evaluation.star_feedback!r}\n")
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print(f"SUCCESS — interview finished. Transcript has {len(session.transcript)} entries.")


if __name__ == "__main__":
    main()
