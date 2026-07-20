from fastapi.testclient import TestClient

from api.main import app
from src.llm_client import LLMError
from src.document_processor import DocumentProcessingError
from src.schemas import CandidateProfile, Evaluation, Question, QuestionSet

client = TestClient(app)

PROFILE = CandidateProfile(
    seniority="Mid-level",
    role_type="Backend Engineer",
    key_skills=["Python"],
    skill_gaps=["Kubernetes"],
    strengths_summary="Solid fundamentals.",
)

QUESTIONS = QuestionSet(
    questions=[
        Question(category="Technical", text="Question 1", target_area="Python"),
        Question(category="Behavioral", text="Question 2", target_area="Teamwork"),
    ]
)


def _upload_file():
    return {"cv": ("cv.pdf", b"fake pdf bytes", "application/pdf")}


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm_calls_since_start" in body


def test_upload_success(monkeypatch):
    monkeypatch.setattr("api.main.extract_text_from_pdf", lambda file: "cv text")
    monkeypatch.setattr("api.main.clean_job_description", lambda text: text)
    monkeypatch.setattr("api.main.build_candidate_profile", lambda **kwargs: PROFILE)
    monkeypatch.setattr("api.main.generate_questions", lambda profile: QUESTIONS)

    response = client.post(
        "/api/upload", files=_upload_file(), data={"job_description": "some JD"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["role_type"] == "Backend Engineer"
    assert len(body["questions"]) == 2
    assert "session_id" in body


def test_upload_document_processing_error(monkeypatch):
    def raise_doc_error(file):
        raise DocumentProcessingError("bad pdf")

    monkeypatch.setattr("api.main.extract_text_from_pdf", raise_doc_error)

    response = client.post(
        "/api/upload", files=_upload_file(), data={"job_description": "some JD"}
    )

    assert response.status_code == 400
    assert "bad pdf" in response.json()["detail"]


def test_upload_llm_error(monkeypatch):
    monkeypatch.setattr("api.main.extract_text_from_pdf", lambda file: "cv text")
    monkeypatch.setattr("api.main.clean_job_description", lambda text: text)

    def raise_llm_error(**kwargs):
        raise LLMError("api down")

    monkeypatch.setattr("api.main.build_candidate_profile", raise_llm_error)

    response = client.post(
        "/api/upload", files=_upload_file(), data={"job_description": "some JD"}
    )

    assert response.status_code == 502
    assert "api down" in response.json()["detail"]


def _create_session(monkeypatch) -> str:
    monkeypatch.setattr("api.main.extract_text_from_pdf", lambda file: "cv text")
    monkeypatch.setattr("api.main.clean_job_description", lambda text: text)
    monkeypatch.setattr("api.main.build_candidate_profile", lambda **kwargs: PROFILE)
    monkeypatch.setattr("api.main.generate_questions", lambda profile: QUESTIONS)

    response = client.post(
        "/api/upload", files=_upload_file(), data={"job_description": "some JD"}
    )
    return response.json()["session_id"]


def test_get_session_not_found():
    response = client.get("/api/sessions/does-not-exist")
    assert response.status_code == 404


def test_submit_answer_not_found():
    response = client.post("/api/sessions/does-not-exist/answer", json={"answer": "hi"})
    assert response.status_code == 404


def test_submit_answer_advances_session(monkeypatch):
    session_id = _create_session(monkeypatch)

    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: Evaluation(
            score=8,
            star_feedback=None,
            clarity_feedback="Clear.",
            relevance_feedback="Relevant.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )

    response = client.post(f"/api/sessions/{session_id}/answer", json={"answer": "my answer"})

    assert response.status_code == 200
    body = response.json()
    assert body["current_question_number"] == 2
    assert len(body["transcript"]) == 1
    assert body["finished"] is False


def test_submit_answer_after_finished_returns_400(monkeypatch):
    session_id = _create_session(monkeypatch)
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: Evaluation(
            score=8,
            star_feedback=None,
            clarity_feedback="Clear.",
            relevance_feedback="Relevant.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )
    monkeypatch.setattr("api.main.save_session", lambda profile, transcript: "saved-id")

    client.post(f"/api/sessions/{session_id}/answer", json={"answer": "answer 1"})
    finish_response = client.post(
        f"/api/sessions/{session_id}/answer", json={"answer": "answer 2"}
    )
    assert finish_response.json()["finished"] is True
    assert finish_response.json()["saved_session_id"] == "saved-id"

    past_finish_response = client.post(
        f"/api/sessions/{session_id}/answer", json={"answer": "answer 3"}
    )
    assert past_finish_response.status_code == 400


def test_get_report_not_found():
    response = client.get("/api/sessions/does-not-exist/report")
    assert response.status_code == 404


def test_get_report_before_finished_returns_400(monkeypatch):
    session_id = _create_session(monkeypatch)
    response = client.get(f"/api/sessions/{session_id}/report")
    assert response.status_code == 400


def test_get_report_success(monkeypatch):
    session_id = _create_session(monkeypatch)
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: Evaluation(
            score=8,
            star_feedback=None,
            clarity_feedback="Clear.",
            relevance_feedback="Relevant.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )
    monkeypatch.setattr("api.main.save_session", lambda profile, transcript: "saved-id")
    client.post(f"/api/sessions/{session_id}/answer", json={"answer": "answer 1"})
    client.post(f"/api/sessions/{session_id}/answer", json={"answer": "answer 2"})

    from src.schemas import InterviewReport

    monkeypatch.setattr(
        "api.main.build_report",
        lambda profile, transcript: InterviewReport(
            readiness_score=8,
            overall_summary="Solid performance overall.",
            strengths=["Clear communication"],
            weaknesses=["Could go deeper on distributed systems"],
            study_plan=["Review Kubernetes basics"],
        ),
    )

    response = client.get(f"/api/sessions/{session_id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["readiness_score"] == 8
    assert body["strengths"] == ["Clear communication"]


def test_get_past_sessions(monkeypatch):
    monkeypatch.setattr(
        "api.main.list_sessions",
        lambda: [{"id": "abc", "created_at": "2026-07-19T00:00:00", "role_type": "Backend Engineer"}],
    )

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "abc", "created_at": "2026-07-19T00:00:00", "role_type": "Backend Engineer"}
    ]
