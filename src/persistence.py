"""Thin wrapper around Supabase: saves and loads interview session records."""

import os

from dotenv import load_dotenv
from supabase import Client, create_client

from src.interview_engine import TranscriptEntry
from src.schemas import CandidateProfile

load_dotenv()

TABLE_NAME = "interview_sessions"


class PersistenceError(Exception):
    """Raised when saving or loading interview session data fails."""


def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise PersistenceError(
            "SUPABASE_URL / SUPABASE_SECRET_KEY not set. Copy .env.example to .env and "
            "add them."
        )
    return create_client(url, key)


def _transcript_to_json(transcript: list[TranscriptEntry]) -> list[dict]:
    return [
        {
            "question_text": entry.question_text,
            "category": entry.category,
            "answer_text": entry.answer_text,
            "evaluation": entry.evaluation.model_dump(),
        }
        for entry in transcript
    ]


def save_session(profile: CandidateProfile, transcript: list[TranscriptEntry], user_id: str) -> str:
    """Save a (possibly in-progress) interview session for a logged-in user and return
    its id. Only ever called for authenticated requests -- guest ("Try Me") sessions
    are never saved at all, so user_id is required here, not optional."""
    client = _get_client()
    try:
        response = (
            client.table(TABLE_NAME)
            .insert(
                {
                    "role_type": profile.role_type,
                    "profile": profile.model_dump(),
                    "transcript": _transcript_to_json(transcript),
                    "user_id": user_id,
                }
            )
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Failed to save interview session: {exc}") from exc

    return response.data[0]["id"]


def list_sessions(user_id: str) -> list[dict]:
    """Return a specific user's past interview sessions (id, created_at, role_type),
    most recent first. Requires a user_id -- there is no "list everyone's sessions"
    mode; history is always scoped to the logged-in user."""
    client = _get_client()
    try:
        response = (
            client.table(TABLE_NAME)
            .select("id, created_at, role_type")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Failed to list interview sessions: {exc}") from exc

    return response.data


def get_saved_session(session_id: str, user_id: str) -> dict | None:
    """Return one saved session (id, created_at, role_type, transcript) if it exists AND
    belongs to user_id; otherwise None. Ownership is enforced in the query itself, so
    another user's session id is indistinguishable from a nonexistent one."""
    client = _get_client()
    try:
        response = (
            client.table(TABLE_NAME)
            .select("id, created_at, role_type, transcript")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Failed to load interview session: {exc}") from exc

    return response.data[0] if response.data else None
