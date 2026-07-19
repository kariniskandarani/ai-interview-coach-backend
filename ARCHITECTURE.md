# AI Job Interview Coach — Architecture & Hackathon Plan

Designed for a 4-day AI hackathon (started 2026-07-17). This document covers every major
technical decision, why it was chosen over the alternatives, the full system architecture,
the MVP breakdown, and the day-by-day implementation roadmap. No code has been written yet —
this is the architecture phase, agreed before implementation begins.

---

## 1. The core architectural question: do we need RAG?

It's tempting to assume any "AI app" needs a vector database and embeddings. Worth pushing
back on that before going further, because **this is one of the most common beginner mistakes
in AI app-building: reaching for RAG because it's the "proper" AI architecture, not because
the problem needs it.**

**What RAG (Retrieval-Augmented Generation) actually is:** a technique for when you have *more
text than fits in the model's context window* (e.g., a 500-page knowledge base), so you chunk
it, embed it into vectors, store those in a vector DB, and retrieve only the relevant chunks
per query.

**Why we don't need it here:** a CV is ~1-2 pages (~500-1000 words). A job description is
similar. Even a full conversation history of 10 interview questions and answers is a few
thousand words. Modern LLMs have context windows of 128K–1M+ tokens. **The entire CV + JD +
conversation history fits in one prompt with room to spare.** This is called "context
stuffing" and for documents this size, it's strictly better than RAG: no chunking logic, no
embedding costs, no vector DB to host, no retrieval-relevance bugs, and the model sees *all*
the CV context every time instead of only whatever a similarity search happened to retrieve.

**Verdict: no vector DB in the MVP.** One place later (a curated question bank) could
theoretically use lightweight retrieval — but even there, simple keyword filtering beats a
vector DB for a hackathon.

This alone removes three of the "must decide" technologies (vector DB, embedding model,
chunking strategy) and several days of complexity. That's a win, not a gap.

---

## 2. Technology stack — decisions with alternatives

### LLM Provider

| Option | Cost | Notes |
|---|---|---|
| **Google Gemini (3.5 Flash)** ✅ | **Free tier** (genuinely free API key, generous rate limits) | Strong reasoning, native structured/JSON output, huge context window, fast |
| Groq (Llama 3.3 70B) | Free tier | Extremely fast token generation (great live-demo feel), slightly less reliable structured output |
| OpenAI GPT-4o-mini | Paid (no reliable free tier anymore) | Excellent quality, but violates the "free" constraint |
| Local via Ollama | Free, no API limits | Needs decent GPU, slower, risky for a live demo if it lags/crashes |

**Decision: Google Gemini API (`gemini-3.5-flash`)** as primary. It's free, has a large context
window (supports the "no RAG needed" approach), and has reliable structured output (used
heavily via Pydantic schemas so responses come back as validated JSON, not text that has to be
regex-parsed — regex-parsing LLM output is a classic beginner trap that breaks
unpredictably).

The LLM calls stay behind a thin wrapper so swapping to Groq later (e.g., for faster demo
responses) is a one-file change, not a rewrite.

### Orchestration: LangChain/LlamaIndex vs. raw SDK calls

**Decision: raw Gemini SDK calls + a thin custom prompt/schema layer. No LangChain.**

Why: LangChain exists to standardize interchangeable chains across many LLM providers and
retrieval backends. This project has ~5 well-defined LLM calls (analyze CV+JD, generate
questions, evaluate answer, decide follow-up, synthesize report) and one provider. LangChain
would add an abstraction layer, a steeper learning curve, and — critically — it would make it
harder to explain the code to judges, since half the logic would live inside LangChain's
internals rather than in code that was actually written and understood. Raw calls + Pydantic
response models are more code to write, but every line is fully owned and defensible.

### Frontend / Backend

| Option | Verdict |
|---|---|
| **Streamlit** ✅ | Pure Python, built-in file upload, chat UI (`st.chat_message`), session state, native charting for the report dashboard, multi-page apps, one-click free deployment |
| Chainlit | Purpose-built for chat UIs, nicer default chat experience, but weaker for the non-chat "report dashboard" screen needed here |
| React + FastAPI | Most "production-looking," but real risk of not finishing in 4 days with limited frontend experience, plus maintaining two codebases and a CORS/API contract |
| Gradio | Great for single-widget ML demos, awkward for a multi-step flow (upload → interview → report) |

**Original decision: Streamlit**, single app, no separate backend service. Business logic
(document parsing, LLM calls, evaluation, scoring) lives in plain Python modules, fully
decoupled from UI code — Streamlit just calls into them. This got clean/maintainable
architecture *and* avoided the operational overhead of running two servers, and a working
Streamlit frontend (`frontend/`) was built and verified live against the real API.

**Revised mid-hackathon: the final submission frontend is instead built by an AI app builder
(Replit), calling the same business logic through a thin `api/` FastAPI layer.** This reverses
the earlier plan to defer a custom frontend until after the hackathon (see the entry in
[Deferred for later](#7-deferred-for-later-explicitly-not-now)). The decoupling that made
"Streamlit only" clean/fast also made this pivot cheap: because business logic never depended
on Streamlit, wrapping it in FastAPI (`api/main.py`) was additive, not a rewrite — same
`profiler.py`/`question_generator.py`/`evaluator.py`/`interview_engine.py`/`persistence.py`
calls, just exposed over HTTP instead of called directly from Streamlit widgets. The Streamlit
frontend was initially kept as a fallback/reference, then removed once the Replit/Next.js path
was confirmed as the actual submission plan — see [BUILD_LOG.md](BUILD_LOG.md) for the
Streamlit build itself (kept as history) and its removal.
Accepted risk: this was chosen consciously as a timeline gamble (see the FastAPI/frontend
build conversation) in exchange for a more polished submission.

### PDF Processing

**Decision: `pdfplumber`.** Pure Python (no system-level dependencies to install, unlike
PyMuPDF which sometimes needs extra build tools on Windows), handles the multi-column/table
layouts common in CVs reasonably well, well documented. If a CV extracts badly, `PyMuPDF`
(`fitz`) is the fallback — faster and more robust on tricky layouts — but that dependency
isn't added until a real failure is hit.

### State & Persistence

- **Session state (must-have):** now that the frontend is a separately-hosted Next.js/React
  app calling `api/` over HTTP, there's no shared in-process session object between requests
  the way Streamlit's `session_state` provided for free. The API (`api/main.py`) holds active
  interview sessions in an in-memory `dict` keyed by `session_id`, returned to the frontend on
  `/api/upload` and used on every subsequent call. This was originally Streamlit's
  `session_state`; see [BUILD_LOG.md](BUILD_LOG.md) for that earlier version.
- **Persistence (should-have): Supabase (hosted Postgres).** Free tier, lets a user's report
  survive a page refresh and enables a "past interviews" history screen. Originally SQLite was
  chosen here for zero-config simplicity, but that decision had a real flaw: free container
  hosting tends to be ephemeral, so a local SQLite file isn't reliably persistent across
  restarts/redeploys — exactly the scenario this feature needs to survive during a live demo.
  Supabase's hosted Postgres actually persists regardless of container restarts, at the cost
  of a new account/project, an SDK dependency (`supabase-py`), and a live network dependency
  for every save. Worth the tradeoff specifically because "does the history feature actually
  work when deployed" was the whole point of building it.

### Auth

**Decision: none.** No login, no user accounts. For a hackathon demo this is pure scope creep
— the time it costs (OAuth setup, session security, edge cases) has near-zero payoff versus a
working interview flow. Flagged explicitly so it doesn't get built "for completeness."

### File Storage

**Decision: none needed.** Uploaded PDFs are read into memory, text is extracted immediately,
and the raw file is discarded. No S3/blob storage — there's nothing to persist beyond the
extracted text, which already lives in session state / Supabase.

### Deployment

**Revised: Render (backend) + Cloudflare Workers (frontend), both free tier.** The original
plan was Streamlit Community Cloud, which stopped being relevant once the frontend moved off
Streamlit. Render hosts `api/` (FastAPI) — free, no credit card, straightforward GitHub-connected
deploy; free-tier caveat: spins down after 15 min idle, ~1 min cold start on the next request,
worth warming up before a live demo. The frontend (generated via Replit, see
[replit_frontend_prompt.md](replit_frontend_prompt.md)) deploys to Cloudflare Workers via the
`@opennextjs/cloudflare` adapter — free tier: 100,000 requests/day, 10ms CPU time/request
(compute only, not time spent waiting on the backend API call).

### Testing

**Decision: `pytest` on the pure-logic layer, plus the API layer via FastAPI's `TestClient`**
— document parsing, prompt builders, response-schema validation, scoring aggregation, and API
routing/error-mapping (`tests/test_api.py`, pipeline functions mocked at the `api.main`
boundary — same reasoning as mocking `evaluate_answer` in `interview_engine` tests). These are
all fast, deterministic, no-network tests; a real (if small) test suite is a genuine signal of
engineering maturity to judges. The Next.js frontend (built via Replit) is **not** covered by
this repo's test suite — low return on time invested, and it's a separate codebase/deployment.

### Final stack summary

| Layer | Choice |
|---|---|
| Language | Python (backend), TypeScript (frontend) |
| Frontend | Next.js/React, generated via Replit, calling `api/` over HTTP |
| Backend API | FastAPI (`api/`), thin wrapper around `src/` |
| LLM | Google Gemini 3.5 Flash (free tier) |
| Orchestration | Plain Python + Pydantic schemas (no framework) |
| PDF parsing | pdfplumber |
| Retrieval | None — full context stuffing |
| Persistence | Supabase/Postgres (should-have), in-memory session dict (must-have) |
| Auth | None |
| File storage | None (in-memory only) |
| Backend hosting | Render (free tier) |
| Frontend hosting | Cloudflare Workers, `@opennextjs/cloudflare` adapter (free tier) |
| Testing | pytest on logic + API layer |

---

## 3. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         STREAMLIT APP                            │
│                                                                    │
│  Page 1: Upload        Page 2: Interview       Page 3: Report    │
│  ┌────────────┐        ┌────────────┐         ┌──────────────┐  │
│  │ CV upload   │        │ Chat UI     │         │ Score charts │  │
│  │ JD input    │  ───▶  │ Q&A loop    │  ───▶   │ Strengths/   │  │
│  │ Persona pick│        │ Live eval   │         │ weaknesses   │  │
│  └────────────┘        └────────────┘         │ Study plan   │  │
│                                                  └──────────────┘  │
└───────────────────────────┬───────────────────────────────────────┘
                             │  calls into
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC (plain Python)                │
│                                                                     │
│  document_processor.py   →  extract & clean text from PDF/JD      │
│  profiler.py              →  LLM call: CV+JD → structured profile │
│  question_generator.py    →  LLM call: profile → question set     │
│  interview_engine.py      →  state machine driving the Q&A loop   │
│  evaluator.py              →  LLM call: answer → STAR/score/notes │
│  report_builder.py         →  LLM call: all evals → final report  │
│  llm_client.py              →  thin Gemini SDK wrapper + schemas  │
└───────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┴───────────────┐
              ▼                               ▼
    ┌───────────────────┐          ┌────────────────────┐
    │  Gemini API        │          │  Supabase (Postgres) │
    │  (all AI calls)    │          │  session history      │
    └───────────────────┘          └────────────────────┘
```

### Data flow / user journey

```
1. User uploads CV (PDF) + pastes JD text, picks interviewer persona
        │
        ▼
2. document_processor extracts CV text (pdfplumber)
        │
        ▼
3. LLM call #1 (profiler): CV text + JD text → structured candidate
   profile (skills, seniority, experience gaps, role type) as JSON
        │
        ▼
4. LLM call #2 (question_generator): profile → 8-10 tailored
   questions across technical / behavioral / HR categories
        │
        ▼
5. INTERVIEW LOOP (interview_engine, state machine):
   ┌─────────────────────────────────────────────┐
   │ present question → user answers               │
   │        │                                       │
   │        ▼                                       │
   │ LLM call #3 (evaluator): answer → STAR check, │
   │ clarity, relevance, score 1-10, follow-up?     │
   │        │                                       │
   │        ▼                                       │
   │ if follow-up needed → ask it, loop             │
   │ else → next scripted question                 │
   └─────────────────────────────────────────────┘
   (repeats until question set exhausted)
        │
        ▼
6. LLM call #4 (report_builder): all Q&A + evaluations →
   final report — readiness score, strengths, weaknesses,
   study plan
        │
        ▼
7. Report rendered in Streamlit (charts + text), optionally
   saved to Supabase, downloadable
```

**Where AI is used:** steps 3, 4, evaluator (per answer), and 6 — four distinct LLM call
types, each with its own prompt template and a Pydantic schema that forces structured JSON
back, so the app code never has to guess-parse free text.

**Where conversation history lives:** `session_state["conversation"]` — a list of
`{question, answer, evaluation}` dicts, passed as context into the follow-up decision and the
final report call, so later calls stay coherent with everything said before.

---

## 4. MVP planning

### Must Have (the demo depends on these)
- CV upload (PDF) + JD text input
- CV/JD analysis → candidate profile
- Personalized question generation (technical + behavioral + HR mix)
- Chat-style mock interview loop
- Per-answer evaluation: STAR structure check, score, feedback
- Final report: overall readiness score, strengths, weaknesses

### Should Have (do these if Must-Have finishes with time to spare)
- Adaptive follow-up questions (evaluator decides to probe deeper)
- Supabase persistence of past interview sessions
- Interviewer persona selection (friendly HR / tough technical lead / startup founder)
- Basic pytest coverage on the logic layer
- Polished Streamlit theming/branding

### Nice to Have (only if everything above is rock solid)
- CV–JD match score + personalized study plan with resources
- Downloadable PDF report (vs. just on-screen)
- Voice input for answers (speech-to-text) — **actively recommended against.** It pulls in
  audio capture, a transcription API, latency, and a new failure surface, for a feature that's
  a "nice touch" not core to the value proposition. Skip unless Day 4 afternoon is genuinely
  empty.

---

## 5. Four-day roadmap

*(Day 1 = 2026-07-17. Adjust against the real submission deadline.)*

**Day 1 — Foundation & AI core (no UI polish yet)**
Build `document_processor.py`, `llm_client.py`, `profiler.py`, `question_generator.py`. Verify
end-to-end via a plain script: PDF in → questions out. Why first: everything downstream
depends on this working reliably, and it's the highest-risk, most novel part (structured LLM
output) — failures should surface on Day 1, not Day 3.

**Day 2 — Interview engine + chat UI**
Build `interview_engine.py` (state machine) and `evaluator.py`, wire into a Streamlit chat
page. By end of day: a working upload → chat interview → live per-answer feedback loop. This
is the "core product" — after today there's a demoable app, even if unpolished.

**Day 3 — Report, persistence, persona feature, polish**
Build `report_builder.py` + report dashboard page (charts via Streamlit's native plotting).
Add Supabase persistence and persona selection. Add pytest for the logic layer. Visual polish
pass on all three pages.

**Day 4 — Innovation feature, hardening, deploy**
Build the CV–JD gap analysis / readiness score (if not already in), full end-to-end
run-throughs to catch edge cases (bad PDF, empty JD, very short answers), deploy to Streamlit
Community Cloud, write the README, prep the demo script. Buffer time is deliberately here, not
earlier — Day 4 problems are the ones you can least afford.

---

## 6. Innovation features (to make this memorable)

1. **Adaptive interviewer personas.** Let the user pick "Friendly HR," "Tough Technical
   Lead," or "Startup Founder" before starting. This changes the system prompt's
   tone/behavior (not the underlying evaluation logic), so it's cheap to build but has real
   demo impact — judges watching a live demo feel the difference immediately, and it signals
   prompt-engineering sophistication.

2. **CV–JD fit score + personalized study plan.** Beyond just running the interview,
   quantify how well the CV matches the JD (skills present/missing, seniority alignment) and
   turn the gaps into a concrete "study before your real interview" checklist in the final
   report. This is the single feature most likely to make a judge say "I'd actually use this"
   — it's the difference between a quiz app and a coaching tool.

Both reuse LLM calls already being built (profiler, report_builder) — no new infrastructure,
just smarter prompts.

---

## 7. Deferred for later (explicitly not now)

Things that were considered and consciously postponed, so they don't get forgotten or
accidentally re-scoped in later. Revisit only if there's real slack, or after the hackathon.

- **~~FastAPI + Next.js/React v2 (post-hackathon)~~ — superseded, see §3.** The original plan
  here was to ship the hackathon on Streamlit and defer any custom-coded frontend rebuild
  (FastAPI + hand-written Next.js/React) until after the deadline, to avoid the risk of
  learning a new frontend framework from zero with ~2 days left. That got revisited: instead
  of hand-coding Next.js/React (still deferred, unhurried, post-hackathon — see the "Timing"
  decision in the frontend conversation), the FastAPI layer was built *now* so an AI app
  builder (Replit) could generate the submission frontend against it immediately. The
  decoupling work already done made the FastAPI half of this cheap; the frontend half is
  delegated to Replit rather than hand-built under time pressure. Hand-coded Next.js/React
  remains a genuine post-hackathon goal (learning + portfolio), just now with a working
  FastAPI backend already sitting there ready for it.

- **HR/recruiter-facing mode.** So far the product has one audience: the job seeker preparing
  for an interview. A second, distinct use case is plausible — HR/recruiters using the app to
  generate a personalized interview script for a real candidate (upload the candidate's CV +
  the JD, get back tailored questions to actually ask in a real interview), without the
  mock-interview chat/evaluation loop at all. Consciously not building this now: a hackathon
  pitch lands harder single-audience/focused, and this would be a second UI surface built
  under time pressure mid-pivot. Worth noting it'd be cheap when revisited — it only reuses
  `profiler.py` + `question_generator.py` as-is; `evaluator.py`/`interview_engine.py` wouldn't
  need to change at all.

- **PyMuPDF (`fitz`) as PDF-parsing fallback.** `pdfplumber` is the primary choice, but if a
  CV's layout extracts badly, PyMuPDF is faster and more robust on tricky layouts. Don't add
  the dependency preemptively — only bring it in once a real extraction failure is hit.

- **Auth.** Decision: none. No login, no user accounts. For a hackathon demo this is pure
  scope creep — the time it costs (OAuth setup, session security, edge cases) has near-zero
  payoff versus a working interview flow. Revisit only if the app ever needs real multi-user
  support beyond a single local demo session.

- **LangChain for orchestration.** Skipped in favor of raw SDK calls + Pydantic schemas,
  because the current pipeline is ~5 well-defined, mostly-linear LLM calls — LangChain's
  abstractions would add a learning curve and debugging opacity without a matching benefit at
  this scale. Worth reconsidering only if the app grows into something with many
  interacting tools/agents, at which point LangGraph (not LangChain's chains) would be the
  more relevant fit — see [LEARNING_NOTES.md](LEARNING_NOTES.md).

- **Voice input for answers (speech-to-text).** Would let users speak answers instead of
  typing, via browser audio capture + a transcription API (e.g., Whisper). Recommended
  against for the hackathon: adds audio capture, a new external API dependency, latency, and
  a new failure surface, for a feature that's a "nice touch" rather than core value. Only
  worth attempting if Day 4 afternoon is genuinely empty.

---

## Status

Architecture phase complete. No code written yet. Next step: walk through the concept, design,
and implementation strategy for `document_processor.py` and `llm_client.py`, then implement,
per the teach-then-build process.
