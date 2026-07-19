"""Manual, one-off check that persistence.py can actually save to and read from
Supabase. Not part of the pytest suite on purpose — real network call, and requires
sql/001_create_interview_sessions.sql to have been run in the Supabase dashboard first.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_persistence.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interview_engine import TranscriptEntry
from src.persistence import PersistenceError, list_sessions, save_session
from src.schemas import CandidateProfile, Evaluation

FAKE_PROFILE = CandidateProfile(
    seniority="Mid-level",
    role_type="Backend Engineer",
    key_skills=["Python"],
    skill_gaps=["Kubernetes"],
    strengths_summary="Solid fundamentals.",
)

FAKE_TRANSCRIPT = [
    TranscriptEntry(
        question_text="Tell me about a challenge you faced.",
        category="Behavioral",
        answer_text="I once debugged a production outage under pressure.",
        evaluation=Evaluation(
            score=8,
            star_feedback="Good use of STAR structure.",
            clarity_feedback="Clear and concise.",
            relevance_feedback="Directly answered the question.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )
]


def main():
    try:
        session_id = save_session(FAKE_PROFILE, FAKE_TRANSCRIPT)
        print(f"SUCCESS — saved session: {session_id}")

        sessions = list_sessions()
        print(f"SUCCESS — listed {len(sessions)} session(s), most recent first:")
        for s in sessions[:3]:
            print(f"  {s['id']} | {s['created_at']} | {s['role_type']}")
    except PersistenceError as exc:
        print(f"FAILED: {exc}")


if __name__ == "__main__":
    main()
