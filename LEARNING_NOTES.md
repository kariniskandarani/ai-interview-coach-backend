# Learning Notes — Concepts Explained

Reference notes for concepts that came up while designing the AI Job Interview Coach. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the full system design these concepts support.

---

## Orchestration

"Orchestration" just means: **the code that decides which LLM calls happen, in what order,
with what inputs, and what happens to the outputs.** It's the glue between raw model calls and
a working application.

Concretely in this app: something has to decide "first call the profiler, take its JSON
output, feed it into the question generator, take *that* output and start the interview loop,
feed each answer into the evaluator, decide if a follow-up is needed..." That
decision-making + data-passing logic is orchestration. It's not a special technology — it's
just control flow — but as apps get more complex (multiple tools, agents calling each other,
retries, branching), people build frameworks to manage it, which is where
LangChain/LlamaIndex/LangGraph come in.

## LangChain vs. LlamaIndex vs. LangGraph

All three are Python frameworks for LLM apps, but they solve different slices of the problem:

- **LangChain** — a general-purpose toolkit: pre-built abstractions for prompt templates,
  chaining calls together, giving models "tools" to call, memory, output parsers. Think of it
  as a big grab-bag of LLM-app building blocks. Pro: huge ecosystem, tutorials for everything.
  Con: heavy abstraction layers mean when something breaks, you're often debugging *inside
  LangChain's internals* rather than your own code — bad for a beginner who needs to fully
  understand and explain their code.

- **LlamaIndex** — originally "GPT Index," focused specifically on connecting LLMs to *your
  data*: loading documents, indexing them (this is where it overlaps with RAG/vector DBs),
  retrieving relevant chunks. If an app is fundamentally "search over a big pile of
  documents," LlamaIndex is the natural fit. Ruled out for this project already — the
  documents are tiny, no retrieval needed.

- **LangGraph** — built by the LangChain team, but a different shape: instead of linear
  "chains," you define an explicit **graph** — nodes are functions/steps, edges are
  transitions, and it supports loops and conditionals natively. It exists because real agents
  aren't linear (they loop, backtrack, wait for human input). It's essentially a state-machine
  library purpose-built for LLM agents.

**Why this matters for this project:** `interview_engine.py` (present question → get answer →
evaluate → maybe follow-up → loop) *is* a state machine — exactly the shape LangGraph is
designed for. But this graph has like 4 states and one conditional branch. Writing that as
plain Python (a function with an if/loop) takes 30 minutes and every line is fully understood.
Learning LangGraph's API to express the same thing would take longer and add a dependency, for
zero functional benefit at this scale. LangGraph earns its keep when there are many
interacting steps/agents — not the case here.

## Chainlit

Chainlit is "Streamlit, but purpose-built for chatbots." It gives you a polished chat UI
(message streaming, chat history, file-upload-in-chat) out of the box, in pure Python, similar
spirit to Streamlit. Considered and rejected for this project specifically because the app
isn't *only* a chat — it also needs a report/dashboard page with charts, and Streamlit handles
that combination (chat page + dashboard page) better than Chainlit, which is chat-first.

## Pydantic schemas

Pydantic is a Python library for **data validation using type hints.** You define a class
describing the *shape* of data you expect:

```python
class CandidateProfile(BaseModel):
    seniority: str
    skills: list[str]
    gaps: list[str]
```

Pydantic then guarantees (at runtime) that any data assigned to it actually matches — wrong
types raise a clear error immediately instead of a mysterious bug three steps later.

Why it matters for LLM calls specifically: when you ask an LLM to "return the analysis as
JSON," the naive approach is to get back a text string and `json.loads()` it and hope it
matches what you expected — this is fragile (the model might add commentary, use wrong field
names, nest things differently). Gemini (like most modern APIs) supports **structured
output**: you hand it a Pydantic schema, and it's constrained to return JSON matching that
schema exactly. So instead of parsing text, `llm_client.py` gets back an actual validated
`CandidateProfile` object with `.skills`, `.gaps`, etc. as real Python attributes. This is the
difference between "hope the LLM formatted it right" and "guaranteed to be right or you get an
error."

## Session state and "in-memory"

Streamlit's execution model is unusual: **every time the user interacts with anything** (clicks
a button, submits a chat message), Streamlit reruns the *entire script from top to bottom*.
Without special handling, any Python variable you set (`questions = [...]`) would just get
reset back to nothing on the next rerun — the whole interview would be lost after every single
message.

`st.session_state` is a dict-like object Streamlit provides that **persists across reruns**,
scoped to one browser tab/session. That's where the CV text, the question list, the
conversation-so-far, and scores live — everything that needs to survive from one user
interaction to the next.

"In-memory" just means this data lives in RAM inside the running Python process — not written
to disk anywhere. It's fast and requires zero setup, but it's temporary: close the tab,
restart the app, or the server process restarts, and it's gone. That's the exact reason SQLite
exists as a should-have — to survive beyond a single live session.

## Would SQLite actually persist when hosted on Streamlit Cloud?

Important nuance: **locally, yes** — SQLite writes to a file on disk and it'll be there next
time the app runs. **On Streamlit Community Cloud, not reliably.** Free hosted containers there
are ephemeral — they can restart, sleep after inactivity, or get redeployed, and any local file
(including a SQLite `.db`) can be wiped when that happens. There's no persistent disk guarantee
on the free tier.

For this project's purposes that's fine: during development and during a live demo session,
SQLite works perfectly (data persists across page refreshes within that running session). It
just shouldn't be marketed as "your interview history is saved forever" on the free-tier
deploy — treat it as "persists for this session/demo," not permanent storage. If long-term
persistence across redeploys ever mattered, an externally-hosted DB (e.g., Supabase Postgres,
or Turso for hosted SQLite) would be the fix — deliberately not doing that here, per the "skip
hosted DB" decision in the architecture doc.

## "Eval" and "persona pick"

**Eval** = evaluation — shorthand for the LLM call that grades the user's answer to an
interview question: does it follow the STAR structure (Situation, Task, Action, Result), is it
clear and relevant, what score 1–10, what feedback, and does it warrant a follow-up question.
That's `evaluator.py` / "LLM call #3" in the architecture pipeline — "eval" is just common
shorthand in AI engineering for "checking the quality of a model's or user's output against
some criteria."

**Persona pick** = a UI choice on the upload screen where the user selects the interviewer's
character before starting — e.g. "Friendly HR," "Tough Technical Lead," "Startup Founder."
Selecting one swaps the system prompt's tone/style instructions for question generation and
follow-ups (nothing else changes — same pipeline, same evaluation logic). It's a cheap way to
make the interview *feel* different per persona — one of the two "innovation" features
proposed in the architecture doc.

## `TypeVar` and generic types (`type[T]` vs `T`, `bound=`)

Normal type hints are fixed: `def double(x: int) -> int` always takes and returns an `int`.
But sometimes a function's return type depends on what you pass in — e.g. a function that
returns the first item of any list returns an `int` for a list of ints, a `str` for a list of
strings. There's no single fixed type to write for that.

`TypeVar` solves this by creating a **placeholder type name** — like a variable, but for types
instead of values:

```python
T = TypeVar("T")

def first_item(items: list[T]) -> T:
    return items[0]
```

Read the signature as: *"Whatever type is inside the list you give me, that's the exact type I
promise to return."* Call it with `list[int]` and the type checker infers `T = int` for that
call, so it knows the return type is `int`. Call it with `list[str]` and `T = str` instead.
Same function, same `T`, but it "becomes" a different concrete type depending on the call.

This project's `llm_client.py` uses the identical pattern with classes instead of list
contents:

```python
T = TypeVar("T", bound=BaseModel)

def generate_structured(prompt: str, response_schema: type[T], ...) -> T:
```

- **`bound=BaseModel`** restricts what `T` is allowed to be. `TypeVar("T")` alone means "T can
  be literally any type." Adding `bound=BaseModel` narrows that to "T can be any type, *as
  long as it's `BaseModel` or a subclass of it*." Without the bound, the type checker would
  happily allow `response_schema=str` even though `str` isn't a Pydantic model and the
  function would break at runtime — the bound catches that mistake before the code ever runs.

- **`type[T]` vs `T`** is the difference between *a class* and *an object built from that
  class*:
  - `T` alone = an instance — e.g. `greeting = Greeting(message="hi", enthusiasm_level=9)` has
    type `T` (i.e. `Greeting`).
  - `type[T]` = the class itself — e.g. `Greeting` (no parentheses, nothing built yet) has
    type `type[T]` (i.e. `type[Greeting]`).

  `response_schema` must be `type[T]` because the caller hands over the blueprint (`Greeting`)
  so the function can build one, not an already-finished object. The function then hands back
  `T` — an actual built instance — as its result. Calling `generate_structured(prompt,
  response_schema=Greeting)` locks in `T = Greeting` for that call, so the editor knows the
  result has `.message` and `.enthusiasm_level`, and will flag a typo like `.mesage` before you
  even run the code.

**Important:** none of this changes runtime behavior. If the `TypeVar` were deleted entirely
and the signature simplified to `response_schema: type[BaseModel] -> BaseModel`, the program
would run identically — the only thing lost would be the editor's ability to know exactly
which fields exist on the result. It's pure tooling/documentation value, not logic.

## The voice-input note — what it's actually about

This was flagging a **feature deliberately excluded from scope**, and explaining why, so it
doesn't quietly creep back in later. Concretely, "voice input for answers" would mean: let the
user speak their interview answer out loud instead of typing it, capture that audio in the
browser, send it to a speech-to-text API (e.g., Whisper) to transcribe it into text, then feed
that text into the evaluator same as today.

Why it's recommended against: it adds browser audio-capture code, a new external API
dependency, transcription latency (bad if it lags mid-demo), and a new way for things to break
(background noise, silence, API timeout) — for something that doesn't change the app's core
value (it's still evaluating text either way, just via typing vs. speaking). It's a "nice
touch," not something that makes the coaching better. Only worth touching if Days 1–3 finish
comfortably early and Day 4 has genuine slack.
