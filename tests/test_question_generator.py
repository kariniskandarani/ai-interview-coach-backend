from src.question_generator import _build_prompt
from src.schemas import CandidateProfile


def test_build_prompt_includes_profile_fields():
    profile = CandidateProfile(
        seniority="Mid-level",
        role_type="Backend Engineer",
        key_skills=["Python", "Flask"],
        skill_gaps=["Kubernetes", "gRPC"],
        strengths_summary="Solid backend fundamentals.",
    )

    prompt = _build_prompt(profile)

    assert "Mid-level" in prompt
    assert "Backend Engineer" in prompt
    assert "Python, Flask" in prompt
    assert "Kubernetes, gRPC" in prompt
    assert "Solid backend fundamentals." in prompt
