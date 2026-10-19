# Follow-up: resume-on-refresh + past interviews history

Paste this into the same Replit Agent conversation that built the app (not a fresh one — keep
all existing working functionality exactly as-is). This adds two things; **do not change
anything about the upload flow, the interview chat flow, or any existing API calls** beyond
what's described below.

## What's working, don't touch

CV upload, question generation, the chat interview loop, scoring/feedback display — all
functionally correct against the live API. Do not modify any existing request/response
handling or state management for those flows.

---

## 1. Resume an in-progress interview after a page refresh

**Problem:** refreshing the page mid-interview loses all progress — the app just shows the
upload screen again, even though the backend still has the session.

**Fix:**
- Right after `POST /api/upload` succeeds and you get back a `session_id`, save it to the
  browser's `localStorage` (e.g. key `interview_session_id`).
- On app load, before showing the upload screen, check `localStorage` for a saved
  `session_id`. If one exists, call `GET /api/sessions/{session_id}` instead of showing
  upload:
  - If it returns `200`, use that response to resume the interview UI exactly where it left
    off (same rendering logic you already use for the answer response — same shape).
  - If it returns `404` (the backend restarted and lost the in-memory session — this happens
    on our free-tier hosting), clear the stored `session_id` from `localStorage` and fall back
    to showing the upload screen normally. Don't show a scary error for this — it's an
    expected, normal case, just treat it as "no active session."
- Once an interview reaches `finished: true`, clear `interview_session_id` from
  `localStorage` — a finished interview shouldn't try to "resume" on the next visit.

## 2. A "Past Interviews" page/section

**Problem:** there's currently no way to see interviews you've already completed.

**Fix:**
- Add a simple page or section (a nav link, e.g. "History," is fine) that calls
  `GET /api/sessions` and lists what it returns: each item has `id`, `created_at`, and
  `role_type`. Sort by `created_at` descending if the API doesn't already (it does, but don't
  rely on that — sort client-side too, defensively).
- Simple list view is enough — role type + a formatted date/time per row. No need for a
  detailed drill-down into each past session's full transcript; that data isn't available from
  this endpoint (it only returns the summary fields above, not each session's Q&A).
- Empty state: if the list is empty, show something friendly like "No completed interviews
  yet" rather than a blank page.

## Constraint

Keep it desktop-first, keep the existing page structure, and don't touch any existing API
call's request/response handling — only add the two things above.
