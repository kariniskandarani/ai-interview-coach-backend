"""Drives the mock-interview Q&A loop: presents questions, collects answers, evaluates
them, and decides whether to ask a follow-up before moving on to the next question."""

from dataclasses import dataclass

from src.evaluator import evaluate_answer
from src.schemas import CandidateProfile, Evaluation, QuestionSet


class InterviewEngineError(Exception):
    """Raised when the interview session is used incorrectly, e.g. answering after it's over."""


@dataclass
class TranscriptEntry:
    question_text: str
    category: str
    answer_text: str
    evaluation: Evaluation


class InterviewSession:
    """Holds the state of one in-progress mock interview. No UI dependency — the
    Streamlit page owns one instance of this in session_state and calls into it."""

    MAX_FOLLOW_UPS_PER_QUESTION = 1

    def __init__(self, profile: CandidateProfile, question_set: QuestionSet):
        self._profile = profile
        self._questions = list(question_set.questions)
        self._index = 0
        self._followups_asked_for_current = 0

        self.transcript: list[TranscriptEntry] = []
        self.current_question_text: str | None = None
        self.current_category: str | None = None
        self.finished = False

        self._load_current_question()

    def _load_current_question(self) -> None:
        if self._index >= len(self._questions):
            self.finished = True
            self.current_question_text = None
            self.current_category = None
            return

        question = self._questions[self._index]
        self.current_question_text = question.text
        self.current_category = question.category
        self._followups_asked_for_current = 0

    def submit_answer(self, answer_text: str) -> Evaluation:
        """Evaluate the answer to the current question, record it, and advance the
        interview state (to a follow-up, the next question, or finished)."""
        if self.finished or self.current_question_text is None:
            raise InterviewEngineError("No active question — the interview has finished.")

        evaluation = evaluate_answer(
            question_text=self.current_question_text,
            category=self.current_category,
            answer_text=answer_text,
            profile=self._profile,
        )

        self.transcript.append(
            TranscriptEntry(
                question_text=self.current_question_text,
                category=self.current_category,
                answer_text=answer_text,
                evaluation=evaluation,
            )
        )

        wants_followup = evaluation.follow_up_needed and evaluation.follow_up_question
        under_followup_cap = self._followups_asked_for_current < self.MAX_FOLLOW_UPS_PER_QUESTION

        if wants_followup and under_followup_cap:
            self.current_question_text = evaluation.follow_up_question
            self._followups_asked_for_current += 1
        else:
            self._index += 1
            self._load_current_question()

        return evaluation
