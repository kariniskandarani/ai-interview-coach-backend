# Follow-up: final readiness report feature

Paste this into the same Replit Agent conversation. A new backend endpoint now exists that
wasn't available when the original app was built — this adds a real feature using it. **Do
not touch any existing API integration, request/response handling, or state management**
beyond what's described here.

## The new endpoint

### `GET /api/sessions/{session_id}/report`

Generates the final readiness report for a **finished** interview. This is a real AI call on
the backend (takes a few seconds) — **not automatic**, only call it when the user actually
asks to see their full report (e.g. a button on the completion screen), so it doesn't fire
on every interview completion by default.

**Response `200`:**
```json
{
  "readiness_score": 7,
  "overall_summary": "The candidate demonstrated solid backend fundamentals but struggled with distributed systems concepts...",
  "strengths": [
    "Clearly explained the N+1 query problem and how to resolve it with select_related/prefetch_related.",
    "Gave a concrete, specific example from real experience rather than generic statements."
  ],
  "weaknesses": [
    "Could not describe a Kubernetes deployment strategy when asked.",
    "Answers about distributed systems lacked depth on trade-offs."
  ],
  "study_plan": [
    "Build a small Kubernetes deployment locally (minikube/kind) and practice explaining it.",
    "Review CAP theorem and practice explaining consistency/availability trade-offs out loud."
  ]
}
```

`readiness_score` is 1-10. `strengths`, `weaknesses`, `study_plan` are each short lists of
strings (typically 2-5 items) — render as bullet lists, not paragraphs.

**Errors:** `404` (bad session_id), `400` (interview isn't finished yet — shouldn't happen if
the UI only shows the report button after `finished: true`, but handle it gracefully anyway),
`502` (the AI call failed — let the user retry).

## What to build

On the completion/summary screen (built in the original pass), add a **"Get my full report"**
button (or auto-trigger it once, your call — but if automatic, show a clear loading state
since this takes a few seconds). When the report loads, display it as a distinct section:

- `readiness_score` as a prominent visual element (a gauge, a big number with color-coding,
  whatever fits the existing design system — this is the headline number).
- `overall_summary` as a short paragraph.
- `strengths` and `weaknesses` as two clearly separated bullet lists (consider a
  green/positive vs. amber-or-red/constructive visual distinction).
- `study_plan` as an actionable checklist — this is the single most useful part of the report
  for the user, so give it real visual weight, not an afterthought at the bottom.

## Constraint

This is additive — one new API call, one new UI section on the existing completion screen (or
a dedicated report view, your call on structure). Don't change anything about the upload flow
or the interview chat flow.
