# AI Job Interview Coach

> Upload your CV and a job description, and get a personalized mock interview with
> real-time feedback and a final readiness report — built for [hackathon name] in 4 days.

**Status:** 🚧 In progress (Day 1 — document processing complete)

---

## What it does

- Analyzes your CV against a target job description
- Runs a personalized mock interview (technical, behavioral, HR questions)
- Evaluates each answer (STAR structure, clarity, scoring) with live feedback
- Produces a final report: readiness score, strengths, weaknesses, study plan

*(Demo link / screenshots go here once there's a UI to show.)*

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python |
| Frontend | Next.js/React, generated via Replit, calling the FastAPI backend |
| Backend API | FastAPI (`api/`) |
| LLM | Google Gemini 3.5 Flash (free tier) |
| PDF parsing | pdfplumber |
| Structured output | Pydantic |
| Persistence | Supabase (Postgres) |
| Backend hosting | Render (free tier) |
| Frontend hosting | Cloudflare Workers (OpenNext adapter) |

Full reasoning behind every choice: [ARCHITECTURE.md](ARCHITECTURE.md).

## API usage per session

Every step of the pipeline is exactly one Gemini call, except answer evaluation, which can
trigger a second (a follow-up) per question:

| Step | Calls |
|---|---|
| CV/JD analysis (`build_candidate_profile`) | 1 |
| Question generation (`generate_questions`) | 1 (all 8 questions in a single call) |
| Answer evaluation (`evaluate_answer`) | 1 per answer, up to 2 per question if a follow-up triggers (capped at 1 follow-up/question) |
| Final report (`report_builder`, Day 3) | 1 |

With 8 questions per interview, one full session costs:

- **Best case** (no follow-ups needed): `1 + 1 + 8 + 1 = 11 calls`
- **Worst case** (every question triggers its one allowed follow-up): `1 + 1 + 16 + 1 = 19 calls`

The follow-up cap is what bounds the worst case — without it, a strict evaluator could chain
follow-ups indefinitely. Well within Gemini's free-tier rate limits for a hackathon demo, but
worth knowing for reasoning about live-demo latency (each call adds a few seconds).

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt   # includes test dependencies

copy .env.example .env   # then fill in your GEMINI_API_KEY
```

### Getting a Gemini API key (free)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with any
   Google account.
2. Click **"Create API key"** (choose "Create API key in new project" if asked).
3. Copy the key it generates and paste it into `.env` as `GEMINI_API_KEY=...`.

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
| `POST` | `/api/upload` | Upload CV (PDF) + job description → candidate profile + question set |
| `GET` | `/api/sessions/{session_id}` | Fetch current interview state |
| `POST` | `/api/sessions/{session_id}/answer` | Submit an answer → evaluation + next question |
| `GET` | `/api/sessions` | List past completed sessions |

Full request/response shapes for each: [replit_frontend_prompt.md](replit_frontend_prompt.md#4-api-contract--call-this-dont-rebuild-it).

The frontend lives in a separate repo/deployment (see
[replit_frontend_prompt.md](replit_frontend_prompt.md)), generated via Replit and calling this
API over HTTP.

## Project docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, tech stack decisions, roadmap
- [BUILD_LOG.md](BUILD_LOG.md) — chronological build notes and code explanations
- [LEARNING_NOTES.md](LEARNING_NOTES.md) — concept explanations (RAG, orchestration, Pydantic, etc.)
