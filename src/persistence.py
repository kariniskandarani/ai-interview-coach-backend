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


def save_session(profile: CandidateProfile, transcript: list[TranscriptEntry]) -> str:
    """Save a (possibly in-progress) interview session and return its id."""
    client = _get_client()
    try:
        response = (
            client.table(TABLE_NAME)
            .insert(
                {
                    "role_type": profile.role_type,
                    "profile": profile.model_dump(),
                    "transcript": _transcript_to_json(transcript),
                }
            )
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Failed to save interview session: {exc}") from exc

    return response.data[0]["id"]


def list_sessions() -> list[dict]:
    """Return past interview sessions (id, created_at, role_type), most recent first."""
    client = _get_client()
    try:
        response = (
            client.table(TABLE_NAME)
            .select("id, created_at, role_type")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise PersistenceError(f"Failed to list interview sessions: {exc}") from exc

    return response.data
