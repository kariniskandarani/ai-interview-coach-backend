"""FastAPI wrapper around the existing src/ business logic, so a separately-hosted
frontend (e.g. built with Replit/Lovable) can call the same tested AI pipeline over HTTP
instead of it being reimplemented."""

import uuid

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    AnswerRequest,
    PastSessionSummary,
    SavedSessionResponse,
    SessionStateResponse,
    TranscriptEntryOut,
    UploadResponse,
)
from src.auth import AuthError, get_user_id_from_token
from src.document_processor import (
    DocumentProcessingError,
    clean_job_description,
    extract_text_from_pdf,
)
from src.interview_engine import InterviewEngineError, InterviewSession
from src import llm_client
from src.llm_client import LLMError
from src.persistence import PersistenceError, get_saved_session, list_sessions, save_session
from src.profiler import build_candidate_profile
from src.question_generator import generate_questions
from src.report_builder import build_report
from src.schemas import CandidateProfile, InterviewReport

app = FastAPI(title="AI Job Interview Coach API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of active interview sessions. Restarting the API loses in-progress
# interviews -- acceptable for a hackathon demo, same tradeoff as everywhere else in this
# project. Completed sessions are persisted to Supabase via save_session(), same as the
# Streamlit version.
_active_sessions: dict[str, InterviewSession] = {}
_profiles: dict[str, CandidateProfile] = {}
# None for a guest ("Try Me") session -- those are never saved to history at all.
_session_user_ids: dict[str, str | None] = {}


def _get_user_id(authorization: str | None) -> str | None:
    try:
        return get_user_id_from_token(authorization)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _session_state_response(
    session_id: str, session: InterviewSession, saved_session_id: str | None = None
) -> SessionStateResponse:
    return SessionStateResponse(
        session_id=session_id,
        finished=session.finished,
        current_question_number=session.current_question_number,
        total_questions=session.total_questions,
        current_question_text=session.current_question_text,
        current_category=session.current_category,
        transcript=[
            TranscriptEntryOut(
                question_text=e.question_text,
                category=e.category,
                answer_text=e.answer_text,
                evaluation=e.evaluation,
            )
            for e in session.transcript
        ],
        saved_session_id=saved_session_id,
    )


@app.get("/")
def health():
    return {"status": "ok", "llm_calls_since_start": llm_client.call_count}


@app.post("/api/upload", response_model=UploadResponse)
def upload(
    cv: UploadFile = File(...),
    job_description: str = Form(...),
    authorization: str | None = Header(default=None),
):
    # Optional: a logged-in user gets their finished session saved to history; a
    # guest ("Try Me", no Authorization header) does not. An invalid/expired token
    # (as opposed to no token) still raises 401 -- that's a real auth error to
    # surface, not silently treated as a guest.
    user_id = _get_user_id(authorization)

    try:
        cv_text = extract_text_from_pdf(cv.file)
        jd_text = clean_job_description(job_description)
        profile = build_candidate_profile(cv_text=cv_text, job_description=jd_text)
        question_set = generate_questions(profile)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session_id = str(uuid.uuid4())
    _active_sessions[session_id] = InterviewSession(profile, question_set)
    _profiles[session_id] = profile
    _session_user_ids[session_id] = user_id

    return UploadResponse(session_id=session_id, profile=profile, questions=question_set.questions)


@app.get("/api/sessions/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str):
    session = _active_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _session_state_response(session_id, session)


@app.post("/api/sessions/{session_id}/answer", response_model=SessionStateResponse)
def submit_answer(session_id: str, body: AnswerRequest):
    session = _active_sessions.get(session_id)
    profile = _profiles.get(session_id)
    if session is None or profile is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        session.submit_answer(body.answer)
    except InterviewEngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    saved_session_id = None
    user_id = _session_user_ids.get(session_id)
    if session.finished and user_id is not None:
        try:
            saved_session_id = save_session(profile, session.transcript, user_id)
        except PersistenceError:
            saved_session_id = None  # non-fatal -- user still sees their results

    return _session_state_response(session_id, session, saved_session_id)


@app.get("/api/sessions/{session_id}/report", response_model=InterviewReport)
def get_report(session_id: str):
    session = _active_sessions.get(session_id)
    profile = _profiles.get(session_id)
    if session is None or profile is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.finished:
        raise HTTPException(status_code=400, detail="Interview isn't finished yet.")

    try:
        return build_report(profile, session.transcript)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/sessions", response_model=list[PastSessionSummary])
def get_past_sessions(authorization: str | None = Header(default=None)):
    user_id = _get_user_id(authorization)
    if user_id is None:
        raise HTTPException(
            status_code=401, detail="Log in to view your interview history."
        )

    try:
        rows = list_sessions(user_id)
    except PersistenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        PastSessionSummary(id=r["id"], created_at=r["created_at"], role_type=r["role_type"])
        for r in rows
    ]


@app.get("/api/history/{session_id}", response_model=SavedSessionResponse)
def get_past_session(session_id: str, authorization: str | None = Header(default=None)):
    user_id = _get_user_id(authorization)
    if user_id is None:
        raise HTTPException(
            status_code=401, detail="Log in to view your interview history."
        )

    try:
        row = get_saved_session(session_id, user_id)
    except PersistenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return SavedSessionResponse(
        id=row["id"],
        created_at=row["created_at"],
        role_type=row["role_type"],
        transcript=row["transcript"],
    )
