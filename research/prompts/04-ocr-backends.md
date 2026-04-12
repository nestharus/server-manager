# Research prompt — OCR backend options for game-screenshot activity extraction

## Hard rules (read these first)

**YOU are the research agent. YOU do the research yourself. Do not
launch, spawn, dispatch, or report on any other agent.** There are no
subprocesses. There is no orchestrator. This prompt is your
assignment, and your job is to USE your web search / fetch tools to
research the topic below, then WRITE the findings to
`research/04-ocr-backends.md` using the Write tool.

Your deliverable is a single markdown file: `research/04-ocr-backends.md`.

- **DO** use your web/search/fetch tools to find real evidence
- **DO** write the final report as a markdown file via your Write tool
- **DO NOT** write progress commentary to stdout or to any log file
- **DO NOT** modify any files other than `research/04-ocr-backends.md`
- **DO NOT** describe what the research process will do — just do it
- **DO NOT** treat the `prompts/` directory as the place to write the
  report. The report goes in `research/04-ocr-backends.md` (the
  parent directory)
- **DO NOT** edit `research/00-INDEX.md` — leave it alone
- **DO NOT** pick a winner at the end — lay out the tradeoffs

You have access to file-write and web-search tools. Use them. Your
entire job is: search → read → synthesize → write the markdown file →
stop.

## Task

## Task being supported

A Discord bot needs to accept **game screenshot uploads** and extract
structured activity data from them. The specific shape:

- A user (chapter officer) uploads a screenshot via Discord (either
  as an attachment to a slash command, to a specific channel, or to a
  DM to the bot).
- The screenshot is a **game UI**, not a document. Typical contents
  include: a leaderboard or activity-log panel, per-player rows with
  numerical scores ("activity points"), timestamps, and sometimes
  player names and guild-visible strings.
- Multiple players per screenshot (likely 10–50 rows).
- Cadence: **daily-ish**. A moderate number of images per day, not
  thousands. Ballpark 1–30 images/day across all chapters combined
  in the MVP year.
- Goal: extract `(player_name, activity_points, date)` tuples and
  return them for storage and threshold-checking.

The user has told us they currently maintain this data by hand in a
spreadsheet. A reliable-enough OCR path is high value.

## What to research

### 1. OCR backend options

For each of the following, document capabilities, accuracy expectations
on noisy game-UI text (not standard documents), deployment model,
pricing, language support, and operational risks:

- **Tesseract** (OSS, LSTM-based) — baseline self-hosted option
- **PaddleOCR** (Baidu, OSS) — often better on stylized text
- **EasyOCR** (OSS, PyTorch) — simpler Python API
- **docTR** (Mindee, OSS) — document-oriented but flexible
- **Google Cloud Vision** API (`TEXT_DETECTION` + `DOCUMENT_TEXT_DETECTION`)
- **AWS Textract** — document-centric, may be overkill
- **Azure AI Document Intelligence / Computer Vision Read** API
- **Hugging Face OCR models** (TrOCR, etc.) — self-hostable via
  transformers
- **OpenAI** vision models (`gpt-4o`, `gpt-4o-mini`, `gpt-5`-class
  equivalents in 2026) — not OCR per se; general-purpose vision LLMs
- **Anthropic Claude Vision** (`claude-sonnet-4-6`, `claude-haiku-4-5`,
  etc. in 2026) — same category as OpenAI
- **Google Gemini Vision** (`gemini-2.x-pro`, `gemini-2.x-flash`) —
  same category

For the three large-model vision APIs (OpenAI / Anthropic / Google),
note specifically:
- Can they reliably extract structured data from a game HUD in one
  shot, bypassing the need for classical OCR + post-processing?
- What's the cost per image at typical input sizes?
- What's the latency distribution?
- Do they honor JSON schema / tool-use for structured output?
- Are there content-safety risks in game screenshots (e.g., character
  names that look like usernames, chat bubbles)?

### 2. Accuracy dimension

Game UIs are notoriously hard for classical OCR because:
- Non-standard fonts, sometimes stylized
- Unusual spacing and alignment
- Colored backgrounds, gradients, translucent panels
- Icons interleaved with numbers
- Number-like strings that are actually icons (`1,234,567` score vs
  level badge `99`)

Document:
- Known benchmarks or user reports on game-UI accuracy specifically
- Typical failure modes (missed digits, merged rows, mis-row alignment)
- Whether the backend supports region-of-interest crops or layout hints
- Whether custom model fine-tuning is possible and what that looks like

### 3. Deployment shape for a Railway + Supabase stack

The daemon runs in a Railway container. Document what each backend
would require:

- Self-hosted (Tesseract, Paddle, EasyOCR, docTR): additional
  dependencies in the container, CPU/RAM footprint, cold-start
  behavior, container size impact. Does this still fit in a small
  Railway service?
- Hosted (Google Vision, AWS Textract, Azure, OpenAI, Anthropic,
  Gemini): API key management, rate limits, cost at the MVP cadence,
  egress considerations, latency SLA
- Mixed (self-hosted for common cases, hosted as a fallback)

### 4. Cost modeling

For the hosted options, compute a **concrete monthly cost** at the
expected MVP volume (30 images/day × 30 days = 900 images/month).
Show the arithmetic. Flag which are pennies, which are dollars, which
are meaningful budget lines at scale.

### 5. Structured output

Specifically for the LLM vision APIs, document:
- How reliable is JSON mode / structured output for extracting an
  array of `(player_name, activity_points, ...)` rows?
- Will the LLM hallucinate players or point values under ambiguity?
- What strategies exist to detect and flag hallucinations (e.g.,
  returning confidence, returning the original quoted text, OCR
  double-check pass)?

### 6. Operational risks

- Rate limits at MVP volume and at 10x MVP volume
- Vendor lock-in / EOL risk for each backend (some OCR SaaS services
  have been discontinued historically)
- Data privacy — does the image get stored by the vendor, for how
  long, and under what jurisdiction?
- If Anthropic, Google, or OpenAI changes its prompt-caching, vision
  pricing, or safety policies, what's the blast radius for this
  feature?

### 7. Recommendation matrix (not a winner pick)

End the report with a **table** scoring each backend on:

- Accuracy on game UIs (low / med / high, with caveats)
- Monthly cost at MVP volume
- Container/ops footprint
- Structured-output fit (for the tuple-extraction task)
- Vendor lock-in / portability
- Overall suitability for THIS task (a qualitative note, not a single
  number)

Do not declare a winner. The next phase (synthesis → proposal) will
pick based on the full context including the user's cost tolerance,
privacy preferences, and how many extra hosted dependencies the project
is willing to take on.

## Anti-goals

- **Do not pick a winner.** Lay out the tradeoffs and let the
  proposal phase decide.
- **Do not assume classical OCR will work.** Game UIs are the
  specific hard case; classical OCR is a baseline, not a default.
- **Do not recommend fine-tuning** unless the evidence shows it is
  actually necessary for this volume.
- **Do not design the bot's ingestion flow.** That's a proposal
  concern.
- **Do not speculate on specific game UIs.** We don't yet know which
  game(s) this will need to handle; assume "variable, stylized".

## Evidence quality bar

- Links must resolve
- Prefer primary sources (vendor docs, benchmark papers, community
  reports) over summaries
- Quote pricing pages with date of capture
- Note when evidence is thin

## Output

Write the report to `research/04-ocr-backends.md` (project path
passed via `-p`). Target length: 2000–4000 words. Include the
recommendation matrix as a real markdown table.
