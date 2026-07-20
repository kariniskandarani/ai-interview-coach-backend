"""Synthesizes a full interview transcript into a final readiness report."""

from src.interview_engine import TranscriptEntry
from src.llm_client import generate_structured
from src.schemas import CandidateProfile, InterviewReport, ReportNarrative

SYSTEM_INSTRUCTION = (
    "You are an experienced interview coach writing a final readiness report for a "
    "candidate after a completed mock interview. Be honest and specific -- vague praise "
    "or vague criticism doesn't help the candidate improve. Reference specific answers, "
    "not generic statements."
)

PROMPT_TEMPLATE = """\
Write a final interview-readiness report for this candidate, based on their full mock \
interview transcript below.

## Candidate Profile
Seniority: {seniority}
Target role: {role_type}
Skill gaps (relative to the job description): {skill_gaps}

## Interview Transcript
{transcript_text}

## Instructions
Write a 2-3 sentence honest overall summary of how they performed. List 2-4 specific \
strengths demonstrated during the interview. List 2-4 specific weaknesses or gaps shown in \
their answers. Then write a study plan: 3-5 concrete, actionable things they should study or \
practice before the real interview, informed by both their answer weaknesses and their \
profile's skill gaps.
"""


def _build_transcript_text(transcript: list[TranscriptEntry]) -> str:
    entries = []
    for i, entry in enumerate(transcript, start=1):
        entries.append(
            f"Q{i} ({entry.category}): {entry.question_text}\n"
            f"A{i}: {entry.answer_text}\n"
            f"Score: {entry.evaluation.score}/10 -- {entry.evaluation.clarity_feedback}"
        )
    return "\n\n".join(entries)


def _compute_readiness_score(transcript: list[TranscriptEntry]) -> int:
    scores = [entry.evaluation.score for entry in transcript]
    return round(sum(scores) / len(scores))


def _build_prompt(profile: CandidateProfile, transcript: list[TranscriptEntry]) -> str:
    return PROMPT_TEMPLATE.format(
        seniority=profile.seniority,
        role_type=profile.role_type,
        skill_gaps=", ".join(profile.skill_gaps),
        transcript_text=_build_transcript_text(transcript),
    )


def build_report(profile: CandidateProfile, transcript: list[TranscriptEntry]) -> InterviewReport:
    """Call the LLM to synthesize the transcript into a final report, combined with a
    readiness score computed deterministically from the transcript's actual scores."""
    prompt = _build_prompt(profile, transcript)
    narrative = generate_structured(
        prompt,
        response_schema=ReportNarrative,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    return InterviewReport(
        readiness_score=_compute_readiness_score(transcript),
        overall_summary=narrative.overall_summary,
        strengths=narrative.strengths,
        weaknesses=narrative.weaknesses,
        study_plan=narrative.study_plan,
    )
