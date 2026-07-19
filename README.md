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
| Frontend + app | Streamlit |
| LLM | Google Gemini 3.5 Flash (free tier) |
| PDF parsing | pdfplumber |
| Structured output | Pydantic |
| Persistence | SQLite |
| Deployment | Streamlit Community Cloud |

Full reasoning behind every choice: [ARCHITECTURE.md](ARCHITECTURE.md).

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

Run the app *(once `app.py` exists)*:

```bash
.venv\Scripts\streamlit run app.py
```

## Project docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, tech stack decisions, roadmap
- [BUILD_LOG.md](BUILD_LOG.md) — chronological build notes and code explanations
- [LEARNING_NOTES.md](LEARNING_NOTES.md) — concept explanations (RAG, orchestration, Pydantic, etc.)
