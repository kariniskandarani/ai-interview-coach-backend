"""Generates a personalized mock-interview question set from a candidate profile."""

from src.llm_client import generate_structured
from src.schemas import CandidateProfile, QuestionSet

SYSTEM_INSTRUCTION = (
    "You are an experienced technical interviewer conducting a mock interview to help a "
    "candidate prepare for a real one. Ask clear, realistic, single-part questions — avoid "
    "compound questions that ask for two things at once. Tailor question difficulty to the "
    "candidate's seniority level."
)

PROMPT_TEMPLATE = """\
Generate a personalized mock interview question set for the following candidate.

## Candidate Profile
- Seniority: {seniority}
- Target role: {role_type}
- Key skills: {key_skills}
- Skill gaps (relative to the job description): {skill_gaps}
- Strengths: {strengths_summary}

## Instructions
Generate 8 interview questions in total:
- 4-5 Technical questions that probe the candidate's key skills and specifically test their \
skill gaps, calibrated to their seniority level.
- 2-3 Behavioral questions relevant to a {role_type} at the {seniority} level.
- 1 HR/culture-fit question.

Order the questions from easier/warm-up to more challenging.
"""


def _build_prompt(profile: CandidateProfile) -> str:
    return PROMPT_TEMPLATE.format(
        seniority=profile.seniority,
        role_type=profile.role_type,
        key_skills=", ".join(profile.key_skills),
        skill_gaps=", ".join(profile.skill_gaps),
        strengths_summary=profile.strengths_summary,
    )


def generate_questions(profile: CandidateProfile) -> QuestionSet:
    """Call Gemini to generate a tailored question set for this candidate profile."""
    prompt = _build_prompt(profile)
    return generate_structured(
        prompt,
        response_schema=QuestionSet,
        system_instruction=SYSTEM_INSTRUCTION,
    )
