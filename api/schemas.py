"""API-specific request/response models. These wrap the existing src/schemas.py models
rather than redefining them, so the API surface never drifts from the tested pipeline."""

from pydantic import BaseModel

from src.schemas import CandidateProfile, Evaluation, Question


class UploadResponse(BaseModel):
    session_id: str
    profile: CandidateProfile
    questions: list[Question]


class TranscriptEntryOut(BaseModel):
    question_text: str
    category: str
    answer_text: str
    evaluation: Evaluation


class SessionStateResponse(BaseModel):
    session_id: str
    finished: bool
    current_question_number: int
    total_questions: int
    current_question_text: str | None
    current_category: str | None
    transcript: list[TranscriptEntryOut]
    saved_session_id: str | None = None


class AnswerRequest(BaseModel):
    answer: str


class PastSessionSummary(BaseModel):
    id: str
    created_at: str
    role_type: str
