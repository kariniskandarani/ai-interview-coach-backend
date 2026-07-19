import pytest

from src.interview_engine import InterviewEngineError, InterviewSession
from src.schemas import CandidateProfile, Evaluation, Question, QuestionSet

PROFILE = CandidateProfile(
    seniority="Mid-level",
    role_type="Backend Engineer",
    key_skills=["Python"],
    skill_gaps=["Kubernetes"],
    strengths_summary="Solid fundamentals.",
)

TWO_QUESTIONS = QuestionSet(
    questions=[
        Question(category="Technical", text="Question 1", target_area="Python"),
        Question(category="Behavioral", text="Question 2", target_area="Teamwork"),
    ]
)


def _evaluation(follow_up_needed=False, follow_up_question=None, score=7):
    return Evaluation(
        score=score,
        star_feedback=None,
        clarity_feedback="Clear enough.",
        relevance_feedback="On topic.",
        follow_up_needed=follow_up_needed,
        follow_up_question=follow_up_question,
    )


def test_starts_on_first_question():
    session = InterviewSession(PROFILE, TWO_QUESTIONS)
    assert session.current_question_text == "Question 1"
    assert session.current_category == "Technical"
    assert not session.finished


def test_progress_properties(monkeypatch):
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: _evaluation(follow_up_needed=False),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)
    assert session.total_questions == 2
    assert session.current_question_number == 1

    session.submit_answer("Answer 1")
    assert session.current_question_number == 2

    session.submit_answer("Answer 2")
    assert session.finished
    assert session.current_question_number == 2


def test_advances_to_next_question_when_no_followup_needed(monkeypatch):
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: _evaluation(follow_up_needed=False),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)

    session.submit_answer("A solid answer.")

    assert session.current_question_text == "Question 2"
    assert len(session.transcript) == 1


def test_asks_followup_then_advances(monkeypatch):
    responses = [
        _evaluation(follow_up_needed=True, follow_up_question="Can you elaborate?"),
        _evaluation(follow_up_needed=False),
    ]
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: responses.pop(0),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)

    session.submit_answer("A vague answer.")
    assert session.current_question_text == "Can you elaborate?"
    assert session.current_category == "Technical"

    session.submit_answer("A better, more detailed answer.")
    assert session.current_question_text == "Question 2"
    assert len(session.transcript) == 2


def test_followup_cap_prevents_infinite_loop(monkeypatch):
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: _evaluation(follow_up_needed=True, follow_up_question="Again?"),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)

    session.submit_answer("Still vague.")
    assert session.current_question_text == "Again?"

    session.submit_answer("Still vague again.")
    assert session.current_question_text == "Question 2"


def test_finishes_after_last_question(monkeypatch):
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: _evaluation(follow_up_needed=False),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)

    session.submit_answer("Answer 1")
    session.submit_answer("Answer 2")

    assert session.finished
    assert session.current_question_text is None
    assert len(session.transcript) == 2


def test_submit_answer_raises_after_finished(monkeypatch):
    monkeypatch.setattr(
        "src.interview_engine.evaluate_answer",
        lambda **kwargs: _evaluation(follow_up_needed=False),
    )
    session = InterviewSession(PROFILE, TWO_QUESTIONS)
    session.submit_answer("Answer 1")
    session.submit_answer("Answer 2")

    with pytest.raises(InterviewEngineError):
        session.submit_answer("Too late.")
