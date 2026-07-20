"""Manual, one-off check of the full auth + persistence flow: sign in as a real
Supabase user, run a short real interview, save it scoped to that user, and confirm
list_sessions only returns that user's sessions. Not part of the pytest suite --
real network calls. Requires sql/002_add_user_id.sql to have been run already.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_auth_persistence.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from supabase import create_client

from src.auth import get_user_id_from_token
from src.interview_engine import InterviewSession
from src.llm_client import LLMError
from src.persistence import save_session, list_sessions
from src.profiler import build_candidate_profile
from src.question_generator import generate_questions
from src.schemas import QuestionSet
from scripts.sample_data import SAMPLE_CV, SAMPLE_JD

load_dotenv()

TEST_EMAIL = "smoke-test-auth@example.com"
TEST_PASSWORD = "smoke-test-password-123!"


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    admin_client = create_client(url, key)

    sign_in = admin_client.auth.sign_in_with_password(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    access_token = sign_in.session.access_token
    user_id = get_user_id_from_token(f"Bearer {access_token}")
    print(f"Authenticated as user_id={user_id}")

    try:
        profile = build_candidate_profile(cv_text=SAMPLE_CV, job_description=SAMPLE_JD)
        full_questions = generate_questions(profile)
        session = InterviewSession(profile, QuestionSet(questions=full_questions.questions[:1]))

        answer = "I used select_related and prefetch_related to fix an N+1 query issue."
        session.submit_answer(answer)
        print("Ran a 1-question interview.")

        saved_id = save_session(profile, session.transcript, user_id)
        print(f"Saved session: {saved_id}")

        rows = list_sessions(user_id)
        found = any(r["id"] == saved_id for r in rows)
        print(f"list_sessions(user_id) returned {len(rows)} row(s), includes new save: {found}")
        assert found, "The session we just saved didn't show up in list_sessions for this user!"

        other_rows = list_sessions("00000000-0000-0000-0000-000000000000")
        leaked = any(r["id"] == saved_id for r in other_rows)
        print(f"A different (fake) user_id sees {len(other_rows)} row(s), leaked our session: {leaked}")
        assert not leaked, "A different user_id could see our session -- scoping is broken!"
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return

    print("\nSUCCESS -- save/list correctly scoped to the authenticated user.")


if __name__ == "__main__":
    main()
