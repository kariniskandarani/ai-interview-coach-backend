# AI Job Interview Coach

> Upload your CV and a job description, and get a personalized mock interview with
> real-time feedback and a final readiness report — built in 4 days.

**Status:** ✅ Core AI pipeline complete and live-verified (profile → questions → interview
loop with follow-ups → final report). Backend deployed on Render; frontend deployed on Cloudflare.

---

## What it does

- Analyzes your CV against a target job description
- Runs a personalized mock interview (technical, behavioral, HR questions)
- Evaluates each answer (STAR structure, clarity, scoring) with live feedback
- Produces a final report: readiness score, strengths, weaknesses, study plan

**Live demo:** https://ai-interview-coach-frontend.kariniskandarani2000.workers.dev/ · **Walkthrough:** https://ka.nz/ai/kariniskandarani

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python |
| Frontend | React + TypeScript (Vite), built with AI coding tools, calling the FastAPI backend ([repo](https://github.com/kariniskandarani/ai-interview-coach-frontend)) |
| Backend API | FastAPI (`api/`) |
| LLM | `nvidia/nemotron-3-super-120b-a12b:free` via OpenRouter (free tier) |
| PDF parsing | pdfplumber |
| Structured output | Pydantic |
| Persistence | Supabase (Postgres) |
| Auth | Supabase Auth (email/password), optional -- "Try Me" guest path skips it |
| Backend hosting | Render (free tier) |
| Frontend hosting | Cloudflare Workers (OpenNext adapter) |

Full reasoning behind every choice: [ARCHITECTURE.md](ARCHITECTURE.md).

## API usage per session

Every step of the pipeline is exactly one LLM call, except answer evaluation, which can
trigger a second (a follow-up) per question:

| Step | Calls |
|---|---|
| CV/JD analysis (`build_candidate_profile`) | 1 |
| Question generation (`generate_questions`) | 1 (all 8 questions in a single call) |
| Answer evaluation (`evaluate_answer`) | 1 per answer, up to 2 per question if a follow-up triggers (capped at 1 follow-up/question) |
| Final report (`build_report`, opt-in) | 1, only if `GET /api/sessions/{id}/report` is actually called |

The report call is deliberately **not automatic** on interview completion — it's a separate,
opt-in endpoint the frontend calls only if the user wants the full AI-written report, so
finishing an interview doesn't always cost an extra call.

With 8 questions per interview, one full session costs:

- **Best case** (no follow-ups needed): `1 + 1 + 8 = 10 calls` (11 if the report is requested)
- **Worst case** (every question triggers its one allowed follow-up): `1 + 1 + 16 = 18 calls`
  (19 if the report is requested)

The follow-up cap is what bounds the worst case — without it, a strict evaluator could chain
follow-ups indefinitely. This project originally ran on Gemini, whose free tier turned out to
be a stingy 5 requests/minute and 20 requests/**day** per model — a single session could burn
most or all of a day's quota. Switched to OpenRouter's free tier instead (50-1,000 requests/day
depending on account credit), which is why the LLM layer lives entirely behind
`generate_structured()` in `llm_client.py` — the swap only touched that one file. Full story in
[LEARNING_NOTES.md](LEARNING_NOTES.md) and `BUILD_LOG.md`. `GET /` returns a live
`llm_calls_since_start` counter (resets on process restart) if you want to track real usage
rather than just the theoretical math above.

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt   # includes test dependencies

copy .env.example .env   # then fill in your OPENROUTER_API_KEY
```

### Getting an OpenRouter API key (free)

1. Go to [openrouter.ai](https://openrouter.ai) and sign in.
2. Go to [openrouter.ai/keys](https://openrouter.ai/keys) and click **"Create Key"**.
3. Give it a name; optionally set a credit limit on the key itself (a genuine hard spending
   cap, unlike Google Cloud's alert-only budgets).
4. Copy the generated key (`sk-or-...`) and paste it into `.env` as `OPENROUTER_API_KEY=...`.

Run the tests:

```bash
.venv\Scripts\python -m pytest
```

### Running the API locally

```bash
.venv\Scripts\uvicorn api.main:app --reload
```

- Runs at **http://localhost:8000**.
- `--reload` auto-restarts the server on code changes — drop it for anything production-like.
- Interactive API docs (try out every endpoint from the browser, no `curl`/frontend needed):
  **http://localhost:8000/docs**
- Health check — `GET http://localhost:8000/` should return `{"status": "ok"}`.

**Endpoints** (try any of these live at [localhost:8000/docs](http://localhost:8000/docs)):

| Method | Path | What it does |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/upload` | Upload CV (PDF) + job description → candidate profile + question set. Optional `Authorization: Bearer <token>` — if present, the resulting interview gets saved to that user's history on completion |
| `GET` | `/api/sessions/{session_id}` | Fetch current interview state |
| `POST` | `/api/sessions/{session_id}/answer` | Submit an answer → evaluation + next question |
| `GET` | `/api/sessions/{session_id}/report` | Generate the final readiness report (opt-in, only once the interview is finished) |
| `GET` | `/api/sessions` | List the logged-in user's past sessions. **Requires** `Authorization: Bearer <token>` — `401` without one |
| `GET` | `/api/history/{session_id}` | Fetch one saved past session (full transcript with scores). **Requires** `Authorization: Bearer <token>`; `404` if it does not exist or belongs to another user |

Full request/response shapes for each: [docs/prompts/01-frontend.md](docs/prompts/01-frontend.md#4-api-contract--call-this-dont-rebuild-it).

The frontend lives in a separate repo/deployment (see
[docs/prompts/01-frontend.md](docs/prompts/01-frontend.md)), built with AI coding tools and calling this
API over HTTP.

## Project docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, tech stack decisions, roadmap
- [BUILD_LOG.md](BUILD_LOG.md) — chronological build notes and code explanations
- [LEARNING_NOTES.md](LEARNING_NOTES.md) — concept explanations (RAG, orchestration, Pydantic, etc.)
