# Follow-up: visual polish pass

Paste this into the same Replit Agent conversation that built the app (not a fresh one — it
should keep all the existing working functionality and API integration exactly as-is).

## What's working, don't touch

The upload flow, chat interview flow, scoring/feedback display, and all API calls to the
FastAPI backend are functionally correct and tested end-to-end. **Do not change any API
integration logic, request/response handling, or state management.** This pass is visual/
styling only.

## The problem

The current design is clean but reads as visually plain/generic — it doesn't feel distinct or
have much personality. It needs more visual polish and a stronger sense of brand identity
while staying professional (this is a career-prep tool, not a toy).

## What to improve

- **Color and contrast:** introduce a real accent color used deliberately (buttons, active
  states, progress indicator, category badges) rather than an all-neutral gray/black/white
  palette. Pick something that feels trustworthy and modern, not garish.
- **Typography hierarchy:** make the landing page headline feel more like a hero moment —
  bigger contrast between the headline, subhead, and body text than currently exists.
- **Visual interest on the landing page:** consider a subtle background treatment (soft
  gradient, geometric pattern, or a simple illustration/icon set) instead of a flat white
  background — tasteful, not busy.
- **Micro-interactions:** hover states on buttons/cards, a smooth transition when a new
  question/feedback card appears in the chat, a more polished loading indicator during the
  AI-thinking states (currently just a bare spinner/text).
- **The score/feedback card:** give it more visual weight and clarity — right now it's
  functional but flat. Consider a color-coded score indicator (e.g. the number itself or a
  small badge shifts color by score range) so feedback quality is scannable at a glance
  without reading every word.
- **Category badges** (Technical/Behavioral/HR): give each a distinct, consistent color so
  the question type is recognizable instantly, not just from the text label.

## Constraint

Keep it desktop-first, keep the existing page structure (Landing/Upload → Interview →
Completion summary) and keep every existing API call exactly as it is — this is purely making
the same functional app look and feel more crafted, not restructuring it.
