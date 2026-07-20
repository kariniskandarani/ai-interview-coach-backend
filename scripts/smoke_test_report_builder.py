"""Manual, one-off check of the full pipeline through report generation against the
real OpenRouter API. Not part of the pytest suite -- real network calls. Uses only 2
questions to keep this light on quota.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_report_builder.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interview_engine import InterviewSession
from src.llm_client import LLMError
from src.profiler import build_candidate_profile
from src.question_generator import generate_questions
from src.report_builder import build_report
from src.schemas import QuestionSet
from scripts.sample_data import SAMPLE_CV, SAMPLE_JD

STRONG_ANSWER = (
    "I noticed the query count spiking in Django Debug Toolbar during a code review, then "
    "used select_related for the foreign key and prefetch_related for the reverse relation "
    "to eagerly load related objects in a single extra query instead of N."
)
WEAK_ANSWER = "Uh, I'd probably just look into it and fix it somehow."


def main():
    try:
        profile = build_candidate_profile(cv_text=SAMPLE_CV, job_description=SAMPLE_JD)
        full_question_set = generate_questions(profile)
        two_questions = QuestionSet(questions=full_question_set.questions[:2])
        session = InterviewSession(profile, two_questions)

        answers = [STRONG_ANSWER, WEAK_ANSWER]
        i = 0
        while not session.finished:
            print(f"Q: {session.current_question_text}")
            answer = answers[min(i, len(answers) - 1)]
            print(f"A: {answer}\n")
            session.submit_answer(answer)
            i += 1

        report = build_report(profile, session.transcript)
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print("SUCCESS -- got a validated InterviewReport back:")
    print(f"  readiness_score: {report.readiness_score}/10")
    print(f"  overall_summary: {report.overall_summary}")
    print(f"  strengths: {report.strengths}")
    print(f"  weaknesses: {report.weaknesses}")
    print(f"  study_plan: {report.study_plan}")


if __name__ == "__main__":
    main()
