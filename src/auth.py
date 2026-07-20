"""Identifies the logged-in user (if any) from a Supabase Auth token. Verifies against
Supabase's own Auth server rather than decoding the JWT locally -- Supabase's documented
recommendation, and it avoids needing to know this project's specific signing algorithm."""

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


class AuthError(Exception):
    """Raised when a provided auth token is present but invalid."""


def _get_auth_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise AuthError("SUPABASE_URL / SUPABASE_SECRET_KEY not set on the server.")
    return create_client(url, key)


def get_user_id_from_token(authorization_header: str | None) -> str | None:
    """Extract and verify the user id from a 'Bearer <token>' Authorization header.

    Returns None if no header was provided at all -- an anonymous/"Try Me" request,
    not an error. Raises AuthError if a token WAS provided but is invalid/expired --
    that's a real problem worth surfacing, not silently treating as anonymous.
    """
    if not authorization_header:
        return None

    if not authorization_header.startswith("Bearer "):
        raise AuthError("Authorization header must be in the form 'Bearer <token>'.")

    token = authorization_header.removeprefix("Bearer ")
    client = _get_auth_client()

    try:
        response = client.auth.get_user(token)
    except Exception as exc:
        raise AuthError(f"Invalid or expired token: {exc}") from exc

    if response is None or response.user is None:
        raise AuthError("Invalid or expired token.")

    return response.user.id
