from src.evaluator import _build_prompt
from src.schemas import CandidateProfile


def test_build_prompt_includes_question_and_answer():
    profile = CandidateProfile(
        seniority="Mid-level",
        role_type="Backend Engineer",
        key_skills=["Python"],
        skill_gaps=["Kubernetes"],
        strengths_summary="Solid fundamentals.",
    )

    prompt = _build_prompt(
        question_text="How would you optimize a slow query?",
        category="Technical",
        answer_text="I'd check the query plan first.",
        profile=profile,
    )

    assert "How would you optimize a slow query?" in prompt
    assert "I'd check the query plan first." in prompt
    assert "Technical" in prompt
    assert "Mid-level" in prompt
