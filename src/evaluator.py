"""Evaluates a candidate's answer to a single interview question."""

from src.llm_client import generate_structured
from src.schemas import CandidateProfile, Evaluation

SYSTEM_INSTRUCTION = (
    "You are an experienced, fair interview coach evaluating a candidate's answer during a "
    "mock interview. Be honest and specific — vague praise doesn't help the candidate "
    "improve. Give concrete, actionable feedback."
)

PROMPT_TEMPLATE = """\
Evaluate the candidate's answer to the following interview question.

## Candidate Profile
Seniority: {seniority}
Target role: {role_type}

## Question ({category})
{question_text}

## Candidate's Answer
{answer_text}

## Instructions
Score the answer from 1-10. Give feedback on clarity and relevance. If this is a Behavioral \
question, also assess whether it follows the STAR structure (Situation, Task, Action, \
Result) and note what's missing, if anything — otherwise leave that feedback null. Decide \
whether a follow-up question would meaningfully improve the interview (e.g. the answer was \
vague, incomplete, or avoided the actual question) — if so, write one natural follow-up \
question.
"""


def _build_prompt(
    question_text: str, category: str, answer_text: str, profile: CandidateProfile
) -> str:
    return PROMPT_TEMPLATE.format(
        seniority=profile.seniority,
        role_type=profile.role_type,
        category=category,
        question_text=question_text,
        answer_text=answer_text,
    )


def evaluate_answer(
    question_text: str, category: str, answer_text: str, profile: CandidateProfile
) -> Evaluation:
    """Call Gemini to score and give feedback on a candidate's answer."""
    prompt = _build_prompt(question_text, category, answer_text, profile)
    return generate_structured(
        prompt,
        response_schema=Evaluation,
        system_instruction=SYSTEM_INSTRUCTION,
    )
