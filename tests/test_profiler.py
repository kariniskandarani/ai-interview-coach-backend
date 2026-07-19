from src.profiler import _build_prompt


def test_build_prompt_includes_cv_and_job_description():
    prompt = _build_prompt(cv_text="Jane Doe, 5 years Python", job_description="Needs Django")

    assert "Jane Doe, 5 years Python" in prompt
    assert "Needs Django" in prompt
