# Build Log — AI Job Interview Coach

Chronological build notes: the reasoning, design decisions, and code explanations behind each
piece as it's built. See [README.md](README.md) for the project pitch and setup instructions,
[ARCHITECTURE.md](ARCHITECTURE.md) for the full system design, and
[LEARNING_NOTES.md](LEARNING_NOTES.md) for concept explanations.

---

## Version 1 — Document Processor (Day 1)

Python 3.11.9 is available — good, that's plenty modern for everything we need (pdfplumber,
pydantic v2, etc.).

### Concept: what `document_processor.py` actually does

Every downstream step (profiling, question generation, evaluation) needs plain text, but what
we actually receive from the user is a PDF file (binary, with fonts/layout/formatting baked
in) and a raw JD string (which might have stray whitespace, bullet characters, copy-paste
artifacts). This module's only job: turn "messy real-world input" into "clean text ready for a
prompt." Nothing AI-related happens here — it's pure Python string/file handling, which is
exactly why it's a good place to start (lowest risk, easiest to test, no API key needed yet).

### Design

Two small pure-ish functions, no classes needed (a class would be over-engineering for two
stateless operations):

- `extract_text_from_pdf(file) -> str` — opens the PDF with pdfplumber, pulls text from every
  page, joins it, cleans it.
- `clean_job_description(text) -> str` — same cleanup applied to the pasted JD text.
- A shared `clean_text()` helper (collapse repeated whitespace/blank lines) used by both.

### Explaining the code

**`document_processor.py`:**
- `extract_text_from_pdf(file)` — opens whatever PDF-like object it's given (this will be
  Streamlit's `st.file_uploader` result later, but the function doesn't know or care about
  Streamlit — that's the decoupling from the architecture doc paying off already), pulls
  `.extract_text()` from every page, joins with newlines, cleans it, and raises
  `DocumentProcessingError` if what's left is suspiciously short (the scanned-PDF case).
- `clean_job_description(text)` — same idea for the pasted JD, with a lower length threshold
  since a JD paste is plain text already (no PDF noise to strip).
- `clean_text(text)` — the shared regex cleanup: `[ \t]+` → single space (collapses runs of
  spaces/tabs from PDF layout artifacts), `\n{3,}` → double newline (caps blank-line runs at
  one blank line instead of five), then trims outer whitespace.
- `DocumentProcessingError` — a one-line custom exception. The point of defining our own
  instead of letting pdfplumber's internal exceptions leak out is that the Streamlit UI layer
  can later do `except DocumentProcessingError as e: st.error(str(e))` and know it's catching
  exactly our validated, user-facing error messages — not accidentally swallowing an unrelated
  bug.

**`test_document_processor.py`:** the `make_pdf_bytes` helper builds a real, tiny PDF in
memory with `fpdf2` (test-only dependency, never imported by app code) so
`test_extract_text_from_pdf_reads_real_content` runs the actual pdfplumber parsing path
against real PDF bytes — not a mock. That's deliberate: mocking pdfplumber here would only
prove our mock behaves how we assume, not that the real library does. The other tests check
the two validation paths (empty PDF, non-PDF garbage) raise our custom error, and the
string-cleanup tests are just direct input/output checks.

### `llm_client.py`

**Concept — what it does:** right now nothing in the app talks to Gemini directly except this
one module. Every future piece (`profiler.py`, `question_generator.py`, `evaluator.py`,
`report_builder.py`) will call through it rather than importing the Gemini SDK themselves.
Centralizing this gives us one place to: read the API key, handle API errors consistently,
and — the important part — force every response into a validated shape using the Pydantic
schemas we discussed, instead of each caller separately trying to parse raw text.

**Design:** one public function: `generate_structured(prompt, response_schema,
system_instruction=None) -> <instance of response_schema>`.

- It takes a prompt string and a Pydantic model *class* (not an instance) describing the shape
  we want back.
- The Gemini SDK supports `response_schema` directly in its config — pass it a Pydantic class,
  and the API is constrained to return JSON matching it. The SDK then hands back
  `response.parsed`, which is already an instance of that class (not a string you have to
  `json.loads()` yourself).
- `system_instruction` is optional — this is where persona ("Tough Technical Lead" vs
  "Friendly HR") will get injected later, without touching this module at all.

**Where validation happens (same boundary reasoning as `document_processor.py`):** the Gemini
API is an external system — network calls fail, keys can be missing/invalid, and in rare cases
the model's output might not satisfy the schema. So: missing API key → clear `LLMError` before
ever making a network call; the API call itself wrapped so any failure becomes one consistent
`LLMError`; and if `response.parsed` comes back `None` (schema mismatch on the API's end),
that's also an `LLMError` rather than a silent `None` propagating three modules downstream.

**Implementation strategy:**

- Reading the key: `python-dotenv` loads `.env` into environment variables, then we read
  `GEMINI_API_KEY` from `os.environ`. This is why `.env.example` exists — it documents the
  variable name without committing the real secret (and `.env` is already in `.gitignore`).
- Testing: the real API can't be hit in the automated test suite without a key, and even with
  a key, live network calls don't belong in a fast `pytest` suite you run constantly. So: one
  offline unit test (no key set → raises `LLMError`, no network involved), plus a separate
  small manual smoke-test script you run once by hand to confirm the whole wire-up actually
  talks to Gemini successfully.

**Explaining the code:**

- `generate_structured` — the one function everything else calls. `type[T]` where
  `T = TypeVar("T", bound=BaseModel)` is what lets the type checker know "whatever Pydantic
  class you pass in as `response_schema`, that's exactly the type you get back" — so callers
  get real autocomplete on `.skills`, `.gaps`, etc. instead of a generic `dict`.
- `_get_client()` is prefixed with `_` (Python convention for "internal, not part of this
  module's public API") — nothing outside `llm_client.py` should construct a client directly;
  they should go through `generate_structured`.
- `load_dotenv()` runs once at import time, reading `.env` into `os.environ` so
  `_get_client()` can just do a normal environment lookup.
- The smoke-test script lives in `scripts/`, separate from `tests/`, specifically because it
  makes a real paid-adjacent network call — it shouldn't run every time you type `pytest`,
  only when you deliberately want to check the real API wiring.

**Verification:** ran the smoke test against the real API. First attempt failed with a `404`
— `gemini-2.5-flash` had been retired for new API keys. Confirmed the current model via
Google's docs and switched `MODEL_NAME` to `gemini-3.5-flash`; second run succeeded, returning
a fully-populated, schema-validated `Greeting` object. Good example of why the smoke test
exists separately from the offline unit test: the offline test only proves "the code handles a
missing key correctly," it can't catch "the model name is stale" — only a real call against
the live API surfaces that.

### `schemas.py` and `profiler.py`

**Concept — what they do:** `profiler.py` is the first real "AI" step in the pipeline. Input:
cleaned CV text + cleaned JD text from `document_processor.py`. Output: a structured
`CandidateProfile` (seniority, target role type, relevant skills, gaps vs. the JD, a strengths
summary) that `question_generator.py` will consume next.

**Design decisions:**

- `CandidateProfile` lives in a new shared `schemas.py`, not inside `profiler.py`. Not
  premature abstraction — the architecture already calls for four LLM steps each producing
  their own schema, and some (`question_generator.py`) will need to take a `CandidateProfile`
  as *input*, which would create awkward imports if the schema lived inside `profiler.py`.
  `schemas.py` = "the shapes," `llm_client.py` = "the mechanism," `profiler.py` = "this
  specific use of the mechanism."
- Every field on `CandidateProfile` has a `description=`. This isn't just documentation —
  Gemini's structured-output mode sends the schema, descriptions included, to the model as
  part of the request. The description text is genuinely part of the prompt.
- `seniority` is a `Literal["Entry-level", "Junior", "Mid-level", "Senior", "Lead/Principal"]`
  instead of a free `str`, because later code (question difficulty, UI) will likely branch on
  it — a free-text field could come back as "Senior-ish" and break that logic. Constraining
  the schema is cheaper than validating free text after the fact.
- The profiler's `SYSTEM_INSTRUCTION` is a fixed, neutral "expert recruiter" persona — *not*
  the user-facing interviewer persona (Friendly HR / Tough Technical Lead) planned as an
  innovation feature. Profiling should stay objective regardless of which interviewer persona
  gets picked later; only question-generation and evaluation should vary by persona.

**Implementation strategy:** same split as `llm_client.py` — `_build_prompt()` is a pure
function (template + string substitution), tested offline with no network call.
`build_candidate_profile()` itself needs the real API, verified via
`scripts/smoke_test_profiler.py` using a small realistic CV/JD pair.

**Verification:** live run against a sample "mid-level backend dev" CV targeting a "Senior
Backend Engineer" JD correctly assessed seniority as Mid-level (not Senior — an honest
mismatch against the JD's ask), correctly identified real gaps (Kubernetes, gRPC, distributed
systems, leadership/mentoring), and wrote an accurate, non-flattering strengths summary. Good
sign that the system instruction is doing its job.

### `question_generator.py`

**Concept — what it does:** takes the `CandidateProfile` from `profiler.py` and produces an
ordered set of interview questions — technical, behavioral, and HR — specifically calibrated
to that candidate's seniority and, most importantly, their `skill_gaps`. This becomes the
script `interview_engine.py` will walk through next.

**Design decisions:**

- Added `Question` (category, question text, `target_area`) and `QuestionSet` (an ordered
  `list[Question]`) to `schemas.py`. The wrapper model is required, not just tidy:
  `generate_structured()` is typed as `response_schema: type[T]` bound to `BaseModel`, and a
  bare `list[Question]` isn't a `BaseModel` — it can't be passed directly. This also
  demonstrates a **nested schema** (a model containing a list of another model), which
  Gemini's structured output handles natively.
- No `persona` parameter yet. Persona-driven question tone (Friendly HR vs. Tough Technical
  Lead) is a Day-3 should-have, not today's must-have — adding the parameter now would be
  speculative flexibility. When personas are built, it'll be a one-line addition (swap
  `SYSTEM_INSTRUCTION` for a persona-specific string), so there's no real cost to waiting.
- The question count and category mix (4-5 Technical / 2-3 Behavioral / 1 HR, ordered
  easy→hard) is spelled out explicitly in the prompt rather than left to the model — same
  lesson as the `Literal` seniority field: constrain what's controllable, for consistency
  across runs.

**Implementation strategy:** same split as before — `_build_prompt()` is a pure function
(formats profile fields, joining `key_skills`/`skill_gaps` lists into readable text), tested
offline. For live verification, refactored the smoke tests to share `scripts/sample_data.py`
(the sample CV/JD), and `scripts/smoke_test_question_generator.py` chains the real pipeline —
build a profile, then generate questions from it — rather than testing this module in
isolation.

**Verification:** live run produced exactly the intended mix (5 Technical, 2 Behavioral, 1 HR
= 8 questions), and each question specifically targeted a real gap from the candidate's
profile (gRPC vs. REST architecture, Kubernetes-based connection pooling, distributed rate
limiting, mentoring, leading design discussions) rather than generic questions — confirms the
personalization is actually working end to end, not just structurally valid.
