from src.interview_engine import TranscriptEntry
from src.report_builder import _build_prompt, _compute_readiness_score
from src.schemas import CandidateProfile, Evaluation

PROFILE = CandidateProfile(
    seniority="Mid-level",
    role_type="Backend Engineer",
    key_skills=["Python"],
    skill_gaps=["Kubernetes", "gRPC"],
    strengths_summary="Solid fundamentals.",
)


def _entry(score: int, question_text="Q", answer_text="A", category="Technical"):
    return TranscriptEntry(
        question_text=question_text,
        category=category,
        answer_text=answer_text,
        evaluation=Evaluation(
            score=score,
            star_feedback=None,
            clarity_feedback="Clear enough.",
            relevance_feedback="On topic.",
            follow_up_needed=False,
            follow_up_question=None,
        ),
    )


def test_compute_readiness_score_averages_and_rounds():
    transcript = [_entry(8), _entry(5), _entry(6)]
    assert _compute_readiness_score(transcript) == 6  # 19/3 = 6.33 -> rounds to 6


def test_compute_readiness_score_single_entry():
    assert _compute_readiness_score([_entry(7)]) == 7


def test_build_prompt_includes_profile_and_transcript():
    transcript = [
        _entry(8, question_text="Tell me about X", answer_text="I did Y"),
        _entry(4, question_text="Explain Z", answer_text="Not sure"),
    ]

    prompt = _build_prompt(PROFILE, transcript)

    assert "Mid-level" in prompt
    assert "Backend Engineer" in prompt
    assert "Kubernetes, gRPC" in prompt
    assert "Tell me about X" in prompt
    assert "I did Y" in prompt
    assert "Explain Z" in prompt
    assert "Not sure" in prompt
    assert "8/10" in prompt
    assert "4/10" in prompt
