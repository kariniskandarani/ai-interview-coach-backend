import pytest

from src.persistence import PersistenceError, _get_client, _transcript_to_json
from src.interview_engine import TranscriptEntry
from src.schemas import Evaluation


def test_get_client_raises_without_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    with pytest.raises(PersistenceError):
        _get_client()


def test_transcript_to_json_serializes_entries():
    entry = TranscriptEntry(
        question_text="Tell me about a challenge you faced.",
        category="Behavioral",
        answer_text="I once had to debug a production outage under pressure.",
        evaluation=Evaluation(
            score=8,
            star_feedback="Good use of STAR structure.",
            clarity_feedback="Clear and concise.",
            relevance_feedback="Directly answered the question.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )

    result = _transcript_to_json([entry])

    assert result == [
        {
            "question_text": "Tell me about a challenge you faced.",
            "category": "Behavioral",
            "answer_text": "I once had to debug a production outage under pressure.",
            "evaluation": {
                "score": 8,
                "star_feedback": "Good use of STAR structure.",
                "clarity_feedback": "Clear and concise.",
                "relevance_feedback": "Directly answered the question.",
                "follow_up_needed": False,
                "follow_up_question": None,
            },
        }
    ]
