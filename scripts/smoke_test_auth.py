"""Manual, one-off check that src/auth.py can verify a real Supabase-issued token.
Not part of the pytest suite -- real network calls, and creates/reuses a test user
in the real Supabase project.

Run with:
    .venv\\Scripts\\python scripts\\smoke_test_auth.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os

from dotenv import load_dotenv
from supabase import create_client

from src.auth import AuthError, get_user_id_from_token

load_dotenv()

TEST_EMAIL = "smoke-test-auth@example.com"
TEST_PASSWORD = "smoke-test-password-123!"


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SECRET_KEY"]
    admin_client = create_client(url, key)

    # Create the test user if it doesn't already exist (idempotent-ish for repeat runs).
    try:
        admin_client.auth.admin.create_user(
            {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
        )
        print(f"Created test user {TEST_EMAIL}")
    except Exception as exc:
        print(f"(create_user skipped, probably already exists: {exc})")

    sign_in = admin_client.auth.sign_in_with_password(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    access_token = sign_in.session.access_token
    expected_user_id = sign_in.user.id
    print(f"Signed in as {TEST_EMAIL}, expected user_id={expected_user_id}")

    # No header at all -- should be treated as anonymous, not an error.
    result = get_user_id_from_token(None)
    print(f"No header -> {result!r} (should be None)")
    assert result is None

    # Real, valid token -- should resolve to the correct user id.
    result = get_user_id_from_token(f"Bearer {access_token}")
    print(f"Valid token -> {result!r}")
    assert result == expected_user_id, "user_id from token didn't match the signed-in user!"

    # Garbage token -- should raise AuthError, not silently return None or crash.
    try:
        get_user_id_from_token("Bearer this-is-not-a-real-token")
        print("FAILED: garbage token did not raise AuthError")
    except AuthError as exc:
        print(f"Garbage token correctly raised AuthError: {exc}")

    print("\nSUCCESS -- src/auth.py verified against real Supabase Auth.")


if __name__ == "__main__":
    main()
