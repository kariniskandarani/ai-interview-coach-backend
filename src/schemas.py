"""Pydantic schemas describing the shape of every structured LLM response in the app."""

from typing import Literal

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    seniority: Literal["Entry-level", "Junior", "Mid-level", "Senior", "Lead/Principal"] = Field(
        description="The candidate's seniority level, inferred from years of experience and "
        "the scope of responsibility shown in the CV."
    )
    role_type: str = Field(
        description="The specific role/discipline the candidate is being interviewed for, "
        "e.g. 'Backend Engineer' or 'Product Manager', based on the job description."
    )
    key_skills: list[str] = Field(
        description="Skills and technologies the candidate demonstrably has, based on the CV, "
        "that are relevant to the target role."
    )
    skill_gaps: list[str] = Field(
        description="Skills or requirements listed in the job description that are missing "
        "or only weakly evidenced in the candidate's CV."
    )
    strengths_summary: str = Field(
        description="A 2-3 sentence summary of the candidate's strongest qualifications for "
        "this specific role."
    )


class Question(BaseModel):
    category: Literal["Technical", "Behavioral", "HR"] = Field(
        description="The category this interview question belongs to."
    )
    text: str = Field(description="The actual interview question to ask the candidate.")
    target_area: str = Field(
        description="The specific skill, gap, or topic from the candidate's profile that "
        "this question is designed to probe."
    )


class QuestionSet(BaseModel):
    questions: list[Question] = Field(
        description="An ordered list of interview questions, sequenced from easier/warm-up "
        "questions to more challenging ones."
    )
