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

---

## Version 3 — Evaluator & Interview Engine (Day 2)

### `evaluator.py`

**Concept — what it does:** scores a single answer to a single question (1-10), gives
clarity/relevance feedback, checks STAR structure if the question is Behavioral, and decides
whether a follow-up question is warranted — writing one in the same call if so.

**Design decisions:**

- Follow-up generation happens *inside* this one call (`Evaluation.follow_up_needed` +
  `follow_up_question`), not as a separate 5th LLM call type — keeps the app at the 4 call
  types the architecture doc planned (profile, questions, evaluate, report).
- First real use of genuine `Optional` fields (`star_feedback: str | None`,
  `follow_up_question: str | None`), as opposed to the `Literal` used for `seniority`. Chosen
  here because `star_feedback` truly doesn't apply to Technical/HR questions — forcing a
  non-null placeholder there would be worse than a real null. This was unverified against the
  live API until this session's smoke test (see below).

### `interview_engine.py`

**Concept — what it does:** the state machine driving the Q&A loop. `InterviewSession` holds
the current question, calls `evaluate_answer()` when the user submits an answer, records the
result in a transcript, and decides whether to ask a follow-up or move to the next scripted
question.

**Design decisions:**

- Plain Python class, zero Streamlit dependency — same reasoning as every other module. The
  Streamlit page will own one `InterviewSession` instance in `session_state` and call
  `submit_answer()` on it.
- Follow-ups are capped at `MAX_FOLLOW_UPS_PER_QUESTION = 1`. Without a cap, a strict evaluator
  could in theory chain follow-ups indefinitely — a hard cap keeps interview length predictable
  for a live demo.

**A new testing decision:** `evaluate_answer` is **mocked** in `interview_engine`'s tests
(`monkeypatch.setattr("src.interview_engine.evaluate_answer", ...)`), unlike `pdfplumber`
earlier, which was deliberately tested against a real PDF. The difference: here the thing
under test is *our own control-flow logic* (does the state machine advance/follow-up/cap/finish
correctly?), not the LLM's behavior — mocking isolates that logic from a slow, non-deterministic
external dependency. The LLM integration itself is still verified separately, live, via the
smoke test.

**Verification:** `scripts/smoke_test_interview_engine.py` chains the full pipeline (profile →
questions → interview session) against the real API, deliberately answering the first question
vaguely to check the follow-up path actually triggers. Results confirmed all three open
questions at once: (1) nullable fields work correctly against the live API —
`star_feedback=None` came back cleanly for Technical questions; (2) the follow-up loop
triggers and is correctly capped — transcript ended with exactly 4 entries (2 questions × up
to 1 follow-up each) instead of looping forever; (3) the evaluator genuinely checks relevance
rather than rewarding confident-sounding text — a hardcoded "strong answer" about a Redis rate
limiter scored 1-2/10 when reused against unrelated questions (N+1 queries, mocking S3 in
pytest), correctly penalized as off-topic. That was a flaw in the smoke test's canned answer,
not in `evaluator.py` — arguably good evidence the scoring isn't just rubber-stamping.

---

## Version 4 — Persistence (Day 2, mid-build pivot)

### `persistence.py`

**Concept — what it does:** saves and loads interview session records (candidate profile +
full transcript) so a user's history survives beyond one browser session.

**Why Supabase instead of the originally-planned SQLite:** SQLite was the original
architecture decision (zero-config, ships with Python). It had a real flaw that only became
relevant once we thought through actual deployment: Streamlit Community Cloud's free
containers are ephemeral, so a local SQLite file isn't reliably persistent across
restarts/redeploys — exactly the failure mode this feature exists to prevent. Supabase's
hosted Postgres survives container restarts because the database lives outside the app's
container entirely. Full reasoning: [LEARNING_NOTES.md](LEARNING_NOTES.md). Cost of the
switch: a Supabase project/account, the `supabase-py` SDK, and a live network dependency for
every save — acceptable since persistence is a should-have already scheduled, not a
last-minute addition.

**Design decisions:**

- **One table, `jsonb` columns, not a normalized schema** (`sql/001_create_interview_sessions.sql`).
  A session's transcript is always read/written as one unit and never queried row-by-row, so
  normalizing it into linked tables would add join complexity for zero practical benefit at
  this scale — same "don't build structure the problem doesn't need" reasoning as everywhere
  else in this project.
- **Uses the `service_role`/secret key, not the `anon`/publishable key.** Because Streamlit
  runs entirely server-side, the secret key never reaches a browser, so it's safe to use here
  — and it bypasses Row Level Security entirely, letting us skip writing RLS policies for a
  single-user demo app.
- Mirrors `llm_client.py`'s shape on purpose: a `_get_client()` that validates required env
  vars and raises a clear `PersistenceError` before doing any network work, functions that
  wrap the actual client calls in try/except to normalize failures into that same error type.

**Implementation strategy:** `_transcript_to_json()` is a pure function (converts our
dataclass/Pydantic objects into plain dicts for storage) and is the only thing tested offline.
`_get_client()` raising `PersistenceError` without credentials is also tested offline, same
pattern as `llm_client.py`. The real save/list calls are only verified via
`scripts/smoke_test_persistence.py`.

**Verification:** live run against the real Supabase project succeeded on the first try —
saved a fake session, got back a real `uuid`, and `list_sessions()` correctly returned it with
`created_at` and `role_type` populated.

---

## Version 5 — Streamlit frontend, then a pivot to FastAPI + Replit (Day 2)

### Streamlit frontend (`frontend/`)

Built a working multipage Streamlit app: `app.py` (navigation, gated so the Interview page
only appears once `session_state` has an active `InterviewSession`), `pages/upload.py` (CV
upload + JD textarea, triggers profiling and question generation), `pages/interview.py`
(chat UI rendered directly from `InterviewSession.transcript`, plus `persistence.save_session`
wired in on completion). Added a custom `.streamlit/config.toml` theme (indigo accent) so
the very first working version didn't look like default Streamlit.

Verified with Playwright driving a real headless Chromium against the running app (no
`chromium-cli` available in this environment, so used the Python `playwright` package
directly per the run-skill's fallback pattern): uploaded a real generated CV PDF, filled the
JD, clicked Analyze, and confirmed navigation to the Interview page with zero console errors.
One real gotcha hit and fixed: Playwright's `fill()` on a `text_area` sets the DOM value but
doesn't trigger Streamlit's commit-on-blur behavior, so the Analyze button stayed disabled
until a `Tab` keypress (blur) was added to the driver script — a Streamlit-specific version of
the "controlled input" gotcha the run-skill's docs warn about for React apps generally.

### Pivot: FastAPI (`api/`) for a Replit-built submission frontend

Mid-build, reconsidered the frontend choice again (see the architecture doc's revised
decision under "Frontend / Backend"). Net effect: the Streamlit frontend is kept in the repo,
tested and working, as a fallback — not deleted — but the actual hackathon submission
frontend will be generated by Replit's AI builder, calling business logic through a new thin
`api/` layer instead of Streamlit widgets calling it directly.

**Why this was cheap to add:** every module in `src/` was already decoupled from Streamlit
from Day 1 onward specifically so this kind of swap wouldn't require touching business logic
— `api/main.py` imports the exact same `build_candidate_profile`, `generate_questions`,
`InterviewSession`, `save_session` functions the Streamlit pages use, just exposes them over
HTTP instead of calling them from widget callbacks.

**Design decisions:**

- **`api/schemas.py` wraps `src/schemas.py` models rather than redefining them** — the API's
  JSON responses embed the actual `CandidateProfile`/`Question`/`Evaluation` Pydantic models
  FastAPI already knows how to serialize, so the API contract can never silently drift from
  what the tested pipeline actually produces.
- **In-memory `_active_sessions`/`_profiles` dicts, not a DB-backed session store.** Same
  "don't build for a scale this doesn't have" reasoning as the rest of the project — restarting
  the API loses in-progress interviews, which is an acceptable, known limitation for a
  hackathon demo. Completed interviews are still durably saved via the existing
  `persistence.save_session()`, unaffected by this tradeoff.
- **Four endpoints:** `POST /api/upload` (CV + JD in, profile + questions + session_id out),
  `GET /api/sessions/{id}` (poll current state), `POST /api/sessions/{id}/answer` (submit an
  answer, get back updated state — auto-saves to Supabase when the interview finishes), and
  `GET /api/sessions` (past session history, exposing `persistence.list_sessions()`).
- **CORS wide open (`allow_origins=["*"]`).** The frontend will be hosted on a different
  origin (Replit's domain) than the API, and there's no auth/cookies to protect, so this is a
  reasonable simplification rather than a security gap for this project's scope.

**Testing:** `tests/test_api.py` uses FastAPI's `TestClient` and mocks the pipeline functions
(`build_candidate_profile`, `generate_questions`, `evaluate_answer`, `save_session`,
`list_sessions`) at the `api.main` boundary — same reasoning as mocking `evaluate_answer` in
`interview_engine`'s tests: these tests verify the API's routing, status codes, and
request/response shaping, not the LLM's behavior (already covered elsewhere).

**Verification:** ran the API for real with `uvicorn`, hit `/api/upload` with `curl` and a
real generated CV PDF + real JD text — got back a correctly-shaped, fully personalized
response (accurate seniority/gaps, well-targeted questions) via real Gemini calls, not mocks.
Then hit `/api/sessions/{id}/answer` with a deliberately shallow answer — evaluation correctly
scored it 6/10 and generated a specific, on-topic follow-up question, matching the quality
already seen through the Streamlit path. Confirms the HTTP layer adds zero behavior drift from
the tested pipeline underneath it.

### Streamlit frontend removed

Once Render (backend) + Replit-generated Next.js/React (frontend, hosted on Cloudflare
Workers) were confirmed as the actual deployment plan, the Streamlit frontend
(`frontend/app.py`, `frontend/pages/`, `.streamlit/config.toml`, `src/session_keys.py`) was
deleted from the repo rather than kept as a fallback — it was never committed to git, so
nothing is lost from history, and keeping a second, unused frontend around would just be
confusing dead weight. `streamlit` was also dropped from `requirements.txt`. The write-up
above (Version 5) stays as the record of what was built and verified before the pivot; this
note is just so the "kept as fallback" line in that section doesn't read as still true.

---

## Version 6 — Deployed, and a real rate-limit hit (Day 2)

Backend deployed to Render (`ai-interview-coach-backend`, pushed to GitHub first, then
connected via Render's dashboard — build command `pip install -r requirements.txt`, start
command `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, `.python-version` pinned to 3.11
to match local dev). Verified live: health check, `/docs`, a real `/api/upload` call, and
`/api/sessions` reading real Supabase data — all working in production, not just locally.

Frontend generated via Replit from `replit_frontend_prompt.md`, with the real Render URL
filled in as the base URL. First real end-to-end usage through the generated frontend hit a
genuine `429` rate-limit error from Gemini.

**Root cause:** free-tier `gemini-3.5-flash` allows 10 requests/minute (and 1,500/day — not
the constraint here). A single interview turn can be 1-2 calls (upload = profile + questions
back-to-back; an answer with a follow-up = 2 evaluate calls), so clicking through several
questions quickly in the same minute realistically exceeds 10 RPM — this wasn't a bug, just an
unhandled real failure mode of the free tier.

**Fix:** `generate_structured()` in `llm_client.py` now retries specifically on rate-limit
errors (detected by checking the exception message for `"429"`/`"RESOURCE_EXHAUSTED"` — the
SDK doesn't raise a distinctly-typed exception for this, same as the earlier stale-model 404),
with exponential backoff (2s, 4s, 8s) up to 3 retries, before finally raising `LLMError`.
Non-rate-limit errors (bad key, schema mismatch, genuine outages) still fail immediately —
retrying those wouldn't help and would just add latency to a real failure.

**Testing:** mocks the Gemini client's `generate_content` call directly (a small `_FakeClient`/
`_FakeModels` pair returning a queued sequence of exceptions/successes) and stubs `time.sleep`
to a no-op — this is testing our retry control-flow, not Gemini's actual behavior, so mocking
is correct here, same reasoning as `interview_engine`'s mocked `evaluate_answer`. Three cases:
retries-then-succeeds, exhausts-retries-then-raises, and doesn't-retry-non-rate-limit-errors.
All fast (no real sleeping) since `time.sleep` is stubbed.

**Verification:** 31/31 offline tests passing, including the three new retry tests.

### Two more fixes before the demo video: blocking event loop, and daily-quota-aware retry

**`api/main.py` -- removed `async` from all five endpoints.** Every endpoint was declared
`async def` but internally called fully synchronous, blocking code (everything in `src/` --
none of it uses `await`). Per FastAPI's own docs, blocking code inside `async def` runs
directly on the single event loop thread and blocks it entirely -- no other request (not even
an OPTIONS preflight or a health check) can be served until it finishes. This was directly
observed in production: Render logs showed successful 200s interleaved with 502 Bad Gateway
on `/api/sessions/{id}/answer`, worsened by the new retry-backoff sleeping (added above) which
extended how long a single request could block the loop. Fix: plain `def` instead of
`async def` -- FastAPI then runs the function in a thread pool automatically, so blocking work
no longer freezes the whole server. Confirmed via FastAPI's own async docs page before
changing anything, and by checking the codebase: nothing outside `llm_client.py` uses `await`,
so this was a pure mislabeling, not a partial-async situation needing a bigger rework.

**`llm_client.py` -- the retry logic wasn't suited to what a real quota-exceeded error
actually looks like.** Live testing produced a real `429` with
`quotaId: 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'`, `quotaValue: '20'` --
confirmed via Google AI Studio's own rate-limit dashboard (5 RPM / 20 RPD per model on this
account, `gemini-3.5-flash` already over at 26/20). Two problems with the existing retry:
(1) the backoff maxes out at 14s total, but per-minute exhaustion needs up to ~50-60s to
clear (Google's own error said "retry in 50.5s") -- not enough to reliably help; (2) per-day
exhaustion cannot clear on *any* retry timescale short of waiting for the daily reset --
retrying it is pure wasted blocking time that fails anyway, every time. Fix: added
`_is_daily_quota_error()` (checks for `"PerDay"` in the exception message) and skip retrying
entirely for that case, failing immediately with a clear message instead. Also switched
`MODEL_NAME` to `gemini-2.5-flash`, since the dashboard showed that model's quota was still
essentially untouched (1/20) -- an immediate, free, zero-code-risk way to keep testing today
while the daily quota for `3.5-flash` resets.

**Verification:** 32/32 offline tests passing, including a new test asserting daily-quota
errors fail immediately without calling `time.sleep` at all.

---

## Version 7 — Provider swap: Gemini to OpenRouter, plus call logging (Day 2/3)

Even after switching to `gemini-2.5-flash` in Version 6, the underlying problem remained: 5
requests/minute and 20 requests/day per model on Gemini's free tier is fundamentally too low
for reliable testing and a live demo, regardless of which specific Gemini model is used (same
limits apply per-model). Decided to switch providers rather than keep working around a ceiling
that low.

### `llm_client.py` — full rewrite

**Provider:** OpenRouter, using `nvidia/nemotron-3-super-120b-a12b:free`. Chosen over
OpenRouter's other free models specifically because it was called out for **"stricter
structured output control"** in research — the single property this app depends on most, since
every call must return JSON matching a Pydantic schema, every time. Rejected `openrouter/free`
(the auto-router that picks a random free model per call) despite its convenience, because
picking a *different* underlying model between the profile call, question call, and each
evaluation within one interview risks inconsistent tone/quality mid-session.

**What changed, concretely:**
- Client: `openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)` instead of
  `genai.Client()` — OpenRouter is fully OpenAI-API-compatible, no new/unusual SDK needed.
- Schema: built manually via `response_schema.model_json_schema()` and passed as
  `response_format={"type": "json_schema", "json_schema": {...}}`, instead of handing the
  Pydantic class directly to the SDK (Gemini's `response_schema=` did the conversion for us).
- Response: `response.choices[0].message.content` is a **JSON string** we validate ourselves
  via `response_schema.model_validate_json(...)`, instead of Gemini's `.parsed` giving us an
  already-validated instance for free.
- System instruction: becomes a `{"role": "system", ...}` message in the `messages` list,
  instead of a dedicated SDK parameter.
- Rate-limit detection got **cleaner**, not messier: the `openai` package raises a proper
  typed `openai.RateLimitError`, so the retry logic no longer needs to string-match `"429"` in
  a generic exception the way the Gemini SDK forced us to.
- Dropped the Gemini-specific `_is_daily_quota_error()` daily-vs-per-minute distinction from
  Version 6 — OpenRouter's error format doesn't expose an equivalent `quotaId` to distinguish
  them, so retry logic is simpler now (retry any `RateLimitError` with backoff, same as before
  minus the special-cased daily check). Noted as a known simplification, not a regression --
  OpenRouter's daily ceiling (50-1,000/day) is high enough that this matters far less than it
  did on Gemini's 20/day.

**Confirmed the exact scope of the blast radius before starting, not just assumed it:** grepped
the whole codebase for anything outside `llm_client.py` touching Gemini-specific internals
(`genai`, `.parsed`, `_get_client`) — found nothing. Every other module only ever imports
`generate_structured` and `LLMError`, so the swap stayed contained to one file, confirming the
Day-1 decision to keep this behind a thin wrapper was worth it.

**Testing:** completely rewrote the mocks in `tests/test_llm_client.py` to match the `openai`
client's shape (`client.chat.completions.create(...)`, `openai.RateLimitError` constructed via
a real minimal `httpx.Response` rather than string content) instead of the Gemini SDK's shape.
Added two new tests beyond what existed before: empty response content, and schema-validation
failure on malformed JSON — neither was really testable the same way under Gemini, since
`.parsed` being `None` was the only failure signal available there.

**Verification:** live-tested against the real OpenRouter API at every level of the pipeline,
not just a toy schema — `smoke_test_llm.py` (basic `Greeting`), `smoke_test_profiler.py`
(`CandidateProfile`, real personalized output), and `smoke_test_interview_engine.py`
(`Evaluation`, including the nullable `star_feedback` field, which is the real test of
strict-mode JSON schema compatibility). All passed cleanly on the first attempt, including the
nullable-field case — no schema adjustments needed. Follow-up logic, the 1-follow-up cap, and
answer-relevance judgment all matched the quality already seen under Gemini.

### Call logging and counter, for real visibility into usage

Added structured logging to every real call in `generate_structured()` (schema name, attempt
number, running total) plus a module-level `call_count`, exposed via `GET /` as
`llm_calls_since_start`. Motivation: after being burned by Gemini's quota surprises, theoretical
math ("this should cost N calls") wasn't trustworthy enough on its own — this gives a real,
observable number from actual server logs/the health endpoint instead.

**Verification:** confirmed live on the deployed Render instance — `GET /` returned
`{"status": "ok", "llm_calls_since_start": 0}` immediately after a fresh deploy, confirming the
counter initializes correctly and the endpoint change is live.

---

## Version 8 — `report_builder.py`, the final piece of the core pipeline

The last of the four planned LLM call types (profile, questions, evaluate, report) — closes
out the "innovation feature" from the architecture doc: CV–JD fit + a personalized study plan.

### Design decisions

- **`readiness_score` is computed in Python, not asked of the LLM.** Every `Evaluation` in the
  transcript already has a validated 1-10 score. Averaging them is exact; asking the LLM to
  also invent a holistic score risked it being inconsistent with the per-answer scores it
  already gave. Same "let deterministic code do arithmetic, let the LLM do qualitative
  synthesis" principle used everywhere else in this project. Split into two schemas:
  `ReportNarrative` (what the LLM generates — summary, strengths, weaknesses, study plan) and
  `InterviewReport` (the full public shape, combining the computed score with the LLM's
  narrative) in `schemas.py`.
- **`GET /api/sessions/{id}/report` is a separate, opt-in endpoint — not automatic when the
  interview finishes.** After a whole session's worth of quota pain, I didn't want every
  completed interview to silently cost one more LLM call by default. The frontend can show its
  own lightweight summary from transcript data it already has, and only hit this endpoint if
  the user actually wants the deeper AI-written report.
- **Scoped to in-memory, currently-finished sessions only.** Generating a report for a *past*
  session loaded from Supabase history isn't supported — that would need reconstructing report
  generation from stored data, a bigger feature not being built speculatively right now.

### Implementation

`_build_transcript_text()` formats the full Q&A + scores into readable prompt text;
`_compute_readiness_score()` is the pure averaging function; `_build_prompt()` combines both
with the profile's skill gaps. All three are pure functions, tested offline with no network
call, same pattern as every other module.

`api/main.py`: new `GET /api/sessions/{session_id}/report` — 404 if the session doesn't exist,
400 if it exists but isn't finished yet, 502 if the LLM call fails, 200 with the full
`InterviewReport` otherwise.

**Testing:** `tests/test_report_builder.py` covers score averaging/rounding and prompt
formatting offline. `tests/test_api.py` adds three cases for the new endpoint (not found,
not-finished-yet, success — with `build_report` mocked, same reasoning as every other
API-layer test: verifying routing/status codes, not LLM behavior).

**Verification:** `scripts/smoke_test_report_builder.py` runs the full live pipeline — profile,
questions, a 2-question interview (one strong answer, three vague ones across the follow-ups
triggered), then the report — against the real OpenRouter API. Result: `readiness_score`
computed as 2/10, correctly reflecting the mostly-vague answers; the summary, strengths, and
weaknesses were specific and honest (not generic); and the study plan tied together both the
in-interview weaknesses *and* the original profile's skill gaps (Kubernetes, gRPC, AWS,
distributed systems) — the exact behavior the innovation feature was designed for.

### Frontend follow-up

The original `replit_frontend_prompt.md` explicitly told Replit's Agent *not* to build a
report feature, since the endpoint didn't exist yet at the time. Wrote a new
`replit_report_feature_prompt.md` for this specific addition, rather than editing the
already-used original prompt (which wouldn't retroactively change what was already built).

---

## Version 9 — Authentication (Supabase Auth)

Reversed the Day-1 "no auth" decision once "past interview history" became a real feature:
without knowing whose session was whose, `GET /api/sessions` had no way to scope results, so
every user would see everyone's history mixed together.

### Why Supabase Auth, not custom auth

The app already runs on Supabase for persistence -- Supabase Auth is part of the same
platform, free, and gives real email/password authentication without building password
hashing, session tokens, or reset flows. Auth itself doesn't route through the FastAPI backend
at all -- the frontend talks to Supabase directly via `@supabase/supabase-js`; the backend's
only job is verifying a token Supabase already issued.

### `src/auth.py` (new)

**Verifies tokens against Supabase's own Auth server (`client.auth.get_user(token)`), not by
decoding the JWT locally.** Checked Supabase's own docs before implementing rather than
assuming: their current guidance is that HS256 shared-secret local verification has "significant
security vulnerabilities" if done casually, and recommends either JWKS-based asymmetric
verification or calling their Auth server directly. Chose the latter -- simpler to get
correct, reuses the `supabase-py` dependency already in the project (no new package, no new
env var, since it uses the same `SUPABASE_URL`/`SUPABASE_SECRET_KEY` already configured for
persistence), at the cost of one extra network call per authenticated request.

`get_user_id_from_token(authorization_header)`: returns `None` for no header at all (an
anonymous/"Try Me" request -- not an error), raises `AuthError` for a header that's present
but malformed or rejected by Supabase (a real problem worth surfacing, not silently treated as
anonymous).

### Scope boundary: "Try Me" guests get no history, period

No login = no persistence is the whole design. Guest interviews are simply never saved --
`api/main.py` only calls `save_session()` when a `user_id` was captured at upload time. This
was a deliberate simplification over the alternative (letting a guest interview later be
"claimed" by an account after signing up), which would need session-migration logic not worth
building for a hackathon-scale app.

### `api/main.py` changes

- `POST /api/upload` now accepts an optional `Authorization` header; resolves it to a
  `user_id` (or `None` for guests) and remembers it per-session in a new
  `_session_user_ids` dict, alongside the existing `_active_sessions`/`_profiles`.
- `POST /api/sessions/{id}/answer` only calls `save_session()` on completion if that session
  has a `user_id` -- guest sessions finish normally but are never persisted.
- `GET /api/sessions` now **requires** a valid `Authorization` header -- `401` without one,
  since "whose history" is meaningless without a logged-in user.
- `GET /api/sessions/{id}`, `/answer`, and `/report` remain unauthenticated by design -- a
  `session_id` is an unguessable UUID that functions like a capability token for that one
  session. Noted explicitly as a real, known scope boundary (not independently
  access-controlled beyond the UUID itself), not an oversight.

### `persistence.py` changes

`save_session()` now requires `user_id` (only ever called when one exists, per the scope
boundary above). `list_sessions()` now requires `user_id` and filters with `.eq("user_id",
user_id)` -- there's no "list everyone's sessions" mode anymore.

### `sql/002_add_user_id.sql` (new)

Adds a nullable `user_id uuid references auth.users(id)` column + an index to
`interview_sessions`. Nullable specifically to avoid needing to backfill the handful of rows
saved before auth existed, not because new rows are ever expected to lack one.

### Testing

`tests/test_auth.py`: offline, mocks `_get_auth_client()` the same way `persistence.py`'s
client gets mocked elsewhere -- valid token, rejected token, malformed header, no header,
missing credentials. `tests/test_api.py`: new cases for 401-without-auth on
`/api/sessions`, 401 on an invalid token at upload, and confirming a header-less upload still
succeeds as a guest. Updated `_create_session()` test helper to optionally simulate an
authenticated request.

### Verification -- live, in two stages

1. `scripts/smoke_test_auth.py`: created a real test user via Supabase's admin API, signed in
   to get a real access token, confirmed `get_user_id_from_token()` correctly resolves it to
   the right user id, correctly returns `None` for no header, and correctly raises `AuthError`
   for a garbage token (real error: `"invalid JWT: unable to parse or verify signature..."`).
2. `scripts/smoke_test_auth_persistence.py`: full pipeline -- signed in as the real test user,
   ran a live interview, saved it via `save_session(profile, transcript, user_id)`, confirmed
   `list_sessions(user_id)` returns it, and explicitly confirmed a **different** (fake)
   `user_id` sees zero rows and does *not* see the saved session -- real evidence against
   cross-user leakage, not just "it didn't error."

Both passed cleanly. 48/48 offline tests passing throughout.

### Frontend follow-up

`replit_auth_prompt.md` (new): login/signup UI, the "Try Me" guest path, and exactly which two
endpoints need the `Authorization` header attached (`/api/upload` and `/api/sessions`) and
which don't. Includes the real Supabase project URL and the publishable (safe-for-frontend)
API key.
