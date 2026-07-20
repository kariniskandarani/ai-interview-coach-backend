# Build the frontend for: AI Job Interview Coach

Paste this entire document into Replit's AI Agent to build the frontend. **The backend
already exists and works — do not reimplement any of the AI/business logic below. Build only
the frontend, calling the API described in Section 4.**

## Tech stack requirement

**Build this as a Next.js + React application** (App Router, TypeScript). Use Tailwind CSS
for styling unless you have a strong reason to prefer something else. This is a deliberate
choice, not a suggestion — do not build this as a plain static site, a Python/Streamlit app,
or in any other framework.

---

## 1. Business Requirements (BRD)

**Problem:** Job seekers preparing for interviews rely on generic question banks and prep
articles that ignore their actual CV and the actual job they're applying for. They get no
real feedback until the interview that counts, and by then it's too late to improve.

**Target audience (this build): job seekers only.** Early-career through experienced
professionals preparing for a specific role, especially technical/skilled roles where CV-to-job
fit and concrete, structured answers (e.g. STAR-format behavioral answers) matter. (An
HR/recruiter-facing mode is a deliberately separate, later concept — do not build anything for
that audience in this pass.)

**Business goal (context: this is a hackathon submission):** Demonstrate a genuinely useful,
personalized AI coaching product — not a quiz app. Judges and users should come away thinking
"I would actually use this before a real interview," not "this is a generic chatbot with a
CV upload bolted on."

**Success looks like:** A user uploads a CV + pastes a job description, gets a personalized
mock interview generated specifically for that CV/role pairing, completes it in a natural
chat-like flow, and receives honest, specific, non-generic feedback on every answer.

## 2. Product Requirements (PRD)

### Core user stories

1. As a job seeker, I upload my CV (PDF) and paste a target job description, so the app can
   tell me how I match up and generate interview questions specific to that pairing.
2. As a job seeker, I answer mock interview questions in a chat interface and get honest,
   specific feedback (a score, clarity notes, relevance notes) right after each answer.
3. As a job seeker, if my answer is vague or incomplete, the interviewer should naturally push
   me for more detail with a targeted follow-up question — like a real interviewer would, not
   just move on.
4. As a job seeker, at the end of the interview I want to see a summary of how I did across
   all questions.

### Explicit scope boundaries — read before building

- **There is no report/dashboard endpoint yet.** Do not build a dedicated analytics/report
  page or invent an endpoint for it. After the interview finishes, show a simple completion
  view built from data the `/answer` endpoint already returns (final transcript with each
  question's score and feedback) — see Section 4.
- **There is no authentication.** Do not build login/signup. This is a single-session demo
  tool.
- **Do not add a persona picker** (e.g. "friendly interviewer" vs "tough interviewer") — the
  backend doesn't support it yet. Keep the interviewer tone neutral/professional.
- **Do not build anything for HR/recruiters** (e.g. a "generate an interview script" mode) —
  that's a distinct, deliberately deferred concept. This build is job-seeker-only.
- **Do not reimplement CV parsing, scoring, or question generation in the frontend or in any
  frontend-side backend/edge function.** All of that already exists and is already tested —
  call the API for it (Section 4).

### Pages needed

1. **Landing / Upload page** — brief pitch (see Section 3 for copy), CV upload (PDF only),
   job description textarea, a primary call-to-action button ("Analyze & Start Interview" or
   similar). Show a clear loading state while the upload call runs — it takes several seconds
   (two real AI calls happen server-side).
2. **Interview page** — chat-style UI. Show the current question as an "interviewer" message,
   a text input for the user's answer (chat-input style, not a big form), and after each
   submission show the interviewer's next question. Show live progress (e.g. "Question 3 of
   8"). After each answer, surface the score/feedback for that answer (e.g. an expandable
   card under that exchange) — don't hide it, this is a core value-add of the product, but it
   shouldn't dominate the chat visually the way the questions/answers do.
3. **Completion / summary view** — once the interview finishes (the API response's `finished`
   field becomes `true`), show a summary: overall stats (e.g. average score across questions),
   and the full list of questions with their scores and feedback. This can be a section of
   the Interview page rather than a separate route.

### Non-functional requirements

- AI calls can take 3–8 seconds each — always show a clear loading/thinking indicator, never
  a frozen UI.
- Handle API errors gracefully: show a readable error message (the API returns a `detail`
  field on errors — see Section 4), never a raw stack trace or blank screen.
- Visual design: clean, modern, professional/trustworthy (this is a career-prep tool, not a
  toy). No specific color palette is mandated — use your own design judgment for the visual
  theme/design system.
- Desktop-first is fine for a hackathon demo; mobile-responsive is a nice-to-have, not
  required.

## 3. Marketing / positioning copy (use or adapt for the landing page)

**One-liner:** AI Job Interview Coach turns any job posting and CV into a personalized mock
interview — with real, specific feedback after every answer.

**Value proposition bullets:**
- Not generic questions — every question is generated from *your* CV and *this* job posting.
- Real feedback, not just a transcript — every answer gets scored and critiqued specifically
  enough to actually improve on, not vague encouragement.
- Feels like a real interviewer — follow-up questions when your answer needs more depth,
  exactly like a real interview would.

**Suggested taglines (pick one or riff):**
- "Practice the interview before it counts."
- "Walk in already having done this once."
- "Your CV. Their job posting. A real mock interview in minutes."

---

## 4. API contract — call this, don't rebuild it

Base URL: `https://ai-interview-coach-backend-g522.onrender.com` — already deployed and live.
Confirm it's reachable by hitting `GET https://ai-interview-coach-backend-g522.onrender.com/`
which returns `{"status": "ok"}`. Note: this is Render's free tier, which spins down after 15
minutes of inactivity — the very first request after idle time can take up to ~1 minute to
respond while it wakes back up. Handle that gracefully (a loading state that doesn't look
broken during a slow first request), don't assume every request is fast.

All requests/responses are JSON except `/api/upload`, which is `multipart/form-data`.

### `POST /api/upload`

Starts a new interview session: analyzes the CV against the job description and generates
the question set.

**Request:** `multipart/form-data`
- `cv`: file (PDF)
- `job_description`: string (plain text, the full job posting)

**Response `200`:**
```json
{
  "session_id": "26d6015d-2304-4ca6-9906-ee2617430d02",
  "profile": {
    "seniority": "Mid-level",
    "role_type": "Backend Engineer",
    "key_skills": ["Python", "Flask", "Django", "PostgreSQL"],
    "skill_gaps": ["Kubernetes", "gRPC", "Distributed systems architecture"],
    "strengths_summary": "Jane has a solid five-year background in Python backend development..."
  },
  "questions": [
    {
      "category": "Technical",
      "text": "How do you identify and resolve an N+1 query problem when fetching relational data using Django's ORM?",
      "target_area": "Django ORM and PostgreSQL optimization"
    }
  ]
}
```
`questions` always has 8 entries, `category` is one of `"Technical"`, `"Behavioral"`, `"HR"`.
Use `session_id` for every subsequent call. Store it client-side (e.g. in React state), it
isn't recoverable from anywhere else.

**Errors:** `400` (bad/unreadable PDF or empty job description, `detail` explains why), `502`
(the AI call failed, `detail` has the error message) — show `detail` to the user.

### `GET /api/sessions/{session_id}`

Fetches the current state of a session (useful on page refresh/reload to resync).

**Response `200`:** same shape as the `/answer` response below.

**Errors:** `404` if the session_id doesn't exist (e.g. backend restarted — in-progress
sessions are in-memory only; show a friendly "session expired, please start again" message).

### `POST /api/sessions/{session_id}/answer`

Submits the user's answer to the current question, gets back the evaluation and the next
state.

**Request:**
```json
{ "answer": "I noticed the query count spiking in Django Debug Toolbar, then used select_related..." }
```

**Response `200`:**
```json
{
  "session_id": "26d6015d-2304-4ca6-9906-ee2617430d02",
  "finished": false,
  "current_question_number": 1,
  "total_questions": 8,
  "current_question_text": "Could you explain the difference between select_related and prefetch_related under the hood...",
  "current_category": "Technical",
  "transcript": [
    {
      "question_text": "How do you identify and resolve an N+1 query problem...",
      "category": "Technical",
      "answer_text": "I noticed the query count spiking...",
      "evaluation": {
        "score": 6,
        "star_feedback": null,
        "clarity_feedback": "The answer is extremely concise and easy to understand, but...",
        "relevance_feedback": "You directly addressed both identification and resolution...",
        "follow_up_needed": true,
        "follow_up_question": "Could you explain the difference between select_related and prefetch_related..."
      }
    }
  ],
  "saved_session_id": null
}
```

**Important behavior to build around:**
- `current_question_text` changing to a *follow-up* question (not the next scripted one) is
  normal — it happens when `evaluation.follow_up_needed` was `true` for the previous answer.
  The UI doesn't need to distinguish these — just always show whatever
  `current_question_text` currently is as the next thing to ask.
- `star_feedback` is `null` for Technical/HR questions — only render that field if it's
  non-null (it's only meaningful for Behavioral questions).
- When `finished` becomes `true`, `current_question_text` is `null` — stop showing an input,
  show the completion summary instead (built from the full `transcript` array).
- `saved_session_id` is populated only once, on the response where `finished` first becomes
  `true`. It can be `null` even when finished (a non-fatal save failure) — don't treat that as
  an error, just don't show a "saved" confirmation if it's null.

**Errors:** `404` (bad session_id), `400` (answer submitted after the interview already
finished — shouldn't happen if the UI respects `finished`, but handle it gracefully anyway),
`502` (the AI evaluation call failed — let the user retry submitting the same answer).

### `GET /api/sessions`

Lists past completed sessions, most recent first. Optional — only build a history view if
time allows; not part of the core flow.

**Response `200`:**
```json
[
  { "id": "abc-123", "created_at": "2026-07-19T12:11:15+00:00", "role_type": "Backend Engineer" }
]
```

---

## 5. What "done" looks like

A Next.js + React app where a user can land on the page, upload a CV + paste a JD, watch the
AI generate a personalized profile and question set, go through a natural chat-style interview
(including at least one follow-up question happening naturally), see honest per-answer
feedback, and reach a completion summary — all against the real API above, no mocked/
fabricated data, no reimplemented AI logic.
