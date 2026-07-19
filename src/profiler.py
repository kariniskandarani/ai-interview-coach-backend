"""Analyzes a candidate's CV against a target job description."""

from src.llm_client import generate_structured
from src.schemas import CandidateProfile

SYSTEM_INSTRUCTION = (
    "You are an expert technical recruiter and career coach. You analyze CVs against "
    "job descriptions with precision and honesty, not flattery — your job is to prepare "
    "a candidate for a real interview, not to make them feel good."
)

PROMPT_TEMPLATE = """\
Analyze the candidate's CV against the target job description below. Identify their \
seniority level, the specific role type, their key relevant skills, any gaps between \
their CV and the job's requirements, and a brief summary of their strengths for this role.

## CV
{cv_text}

## Job Description
{job_description}
"""


def _build_prompt(cv_text: str, job_description: str) -> str:
    return PROMPT_TEMPLATE.format(cv_text=cv_text, job_description=job_description)


def build_candidate_profile(cv_text: str, job_description: str) -> CandidateProfile:
    """Call Gemini to analyze the CV/JD pair and return a structured CandidateProfile."""
    prompt = _build_prompt(cv_text, job_description)
    return generate_structured(
        prompt,
        response_schema=CandidateProfile,
        system_instruction=SYSTEM_INSTRUCTION,
    )
