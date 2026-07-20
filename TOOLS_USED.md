# Tools & Services Used

A quick-reference inventory of every tool/platform/service leveraged for this project, and
what each one is for. Full reasoning for each choice lives in
[ARCHITECTURE.md](ARCHITECTURE.md) and [BUILD_LOG.md](BUILD_LOG.md) — this file is just the
"what did I use again?" checklist.

## AI / LLM

- **OpenRouter** (`nvidia/nemotron-3-super-120b-a12b:free`) — powers every AI call in the
  pipeline (CV/JD analysis, question generation, answer evaluation), via the OpenAI-compatible
  `openai` Python package pointed at OpenRouter's API. Free tier via
  [openrouter.ai/keys](https://openrouter.ai/keys) — 50-1,000 requests/day depending on
  account credit. Switched from Google Gemini after its free tier turned out to be a much
  stingier 5 requests/minute / 20 requests/day per model than commonly reported — see
  [LEARNING_NOTES.md](LEARNING_NOTES.md) and `BUILD_LOG.md`'s Version 7 entry.
- **Claude Code** — AI pair-programming assistant used to design and build the entire project
  (architecture, backend, tests, docs, this file included).

## Backend

- **FastAPI** (`api/`) — thin HTTP wrapper around the business logic in `src/`, so a
  separately-hosted frontend can call it.
- **Pydantic** — schema definitions for every structured LLM response and API
  request/response; also what makes OpenRouter's `response_format: json_schema` mode work.
- **pdfplumber** — extracts text from uploaded CV PDFs.

## Frontend

- **Next.js / React** (generated via **Replit**'s AI Agent, per
  [replit_frontend_prompt.md](replit_frontend_prompt.md)) — the submission frontend, calling
  the FastAPI backend over HTTP. Downloaded from Replit (zip or GitHub push) and hosted
  independently. *(An earlier Streamlit frontend was built and verified first, then removed
  once this path was confirmed — see [BUILD_LOG.md](BUILD_LOG.md).)*

## Database / Persistence

- **Supabase** (hosted Postgres) — stores completed interview session records (`jsonb`
  columns), now scoped per-user via `user_id`. Chosen over SQLite because free container
  hosting tends to be ephemeral — see [LEARNING_NOTES.md](LEARNING_NOTES.md) for the full
  reasoning.
- **Supabase Auth** — email/password login, used directly from the frontend
  (`@supabase/supabase-js`) with no custom backend auth code. The backend only verifies
  tokens Supabase already issued, via `client.auth.get_user(token)`. Free, same project as
  persistence, so no new service. A "Try Me" guest path bypasses it entirely.

## Hosting / Deployment

- **Render** — hosts the FastAPI backend (`api/`). Free tier, no credit card required. Note:
  spins down after 15 min idle; first request after that takes ~1 min to wake up — warm it up
  before a live demo.
- **Cloudflare Workers** (via the `@opennextjs/cloudflare` adapter — *not* the older/deprecated
  Cloudflare Pages or `next-on-pages`) — hosts the Next.js frontend. Free tier: 100,000
  requests/day, 10ms CPU time/request (CPU time only, not time spent waiting on the backend
  API).
- **Replit** — used to generate the frontend code plus BRD/PRD and presentation-prompt content.
  Free published app lasts 30 days, plenty for the hackathon window.

## Testing / Dev tooling

- **pytest** — offline test suite (`tests/`) for all pure logic and mocked-external-call paths.
- **fpdf2** — test-only dependency, generates real in-memory PDFs so `document_processor.py`
  tests exercise real `pdfplumber` parsing instead of a mock.
- **Playwright** (Python) — used once, ad hoc, to drive a real headless Chromium against the
  (since-removed) Streamlit app and verify the golden path end to end. Not a standing project
  dependency.
- **python-dotenv** — loads `.env` (API keys/secrets) into environment variables locally.
