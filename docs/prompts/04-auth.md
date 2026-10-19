# Follow-up: authentication (Supabase Auth)

Paste this into the same Replit Agent conversation. **Do not touch any existing API
integration for the upload/interview/report flows beyond what's described here** — this adds
login/signup and a "Try Me" guest path on top of what already works.

## Why Supabase Auth, not custom auth

The backend already uses Supabase for data storage. Supabase Auth is part of the same
platform — free, and gives real email/password authentication without building password
hashing, session tokens, or reset flows from scratch. Use the `@supabase/supabase-js` client
library directly from the frontend for all auth actions (sign up, sign in, sign out, get
current session) — **auth itself does not go through our FastAPI backend at all.**

## Supabase project details

```
SUPABASE_URL=<your-project>.supabase.co
SUPABASE_ANON_KEY=<your-publishable-key>
```

This "publishable" key is specifically designed to be safe to embed in frontend code (it's
the client-facing key, not the secret server-side one) — put it in your frontend's env
config as normal.

## What to build

### 1. Sign up / log in screen

A simple email + password form (styled to match the existing dark theme). Two modes on one
screen (toggle between "Sign up" and "Log in") is fine — don't need separate pages. Use:
- `supabase.auth.signUp({ email, password })` for new accounts
- `supabase.auth.signInWithPassword({ email, password })` for existing accounts
- `supabase.auth.signOut()` for logging out (add a logout button/menu item once logged in)
- `supabase.auth.getSession()` / `supabase.auth.onAuthStateChange(...)` to track whether the
  user is currently logged in, app-wide

### 2. "Try Me" button

On the landing page, alongside (or instead of, your call on layout) the login prompt, add a
**"Try Me"** button that skips auth entirely and goes straight to the upload flow. Sessions
started this way are **not saved to history** — that's expected backend behavior, not a bug
to work around. If a guest reaches the completion screen, it's fine to show a subtle note
like "Sign up to save your interview history" rather than pretending it was saved.

### 3. Attach the auth token to API calls

When a user **is** logged in, get their access token via
`(await supabase.auth.getSession()).data.session.access_token` and send it as:

```
Authorization: Bearer <access_token>
```

on these two calls specifically:
- `POST /api/upload` — this is what determines whether the resulting interview gets saved to
  history later. **If the user is logged in, attach the header here.** If they're in "Try Me"
  guest mode, don't attach it at all (no header, not an empty one).
- `GET /api/sessions` — **requires** this header now. If there's no logged-in user, don't call
  this endpoint at all (there's nothing to show — guests have no history, and the call will
  return `401` if attempted without a token).

No other endpoints need the header (`/api/sessions/{id}`, `/api/sessions/{id}/answer`,
`/api/sessions/{id}/report` all work the same regardless of login state — the auth check only
matters at upload-time and for the history list).

### 4. Handle 401s gracefully

If `GET /api/sessions` ever returns `401` (e.g. the session token expired), treat it as "not
logged in" — redirect to login or show the guest state, not a raw error message.

## Constraint

This is additive: a new auth screen, a "Try Me" path, and header attachment on two specific
calls. Don't change the request/response handling for `/api/sessions/{id}`,
`/api/sessions/{id}/answer`, or `/api/sessions/{id}/report` — those are unaffected by any of
this.
