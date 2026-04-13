# Research prompt — OCR backend options for game-screenshot activity extraction

You are a research agent evaluating backends for a specific OCR task.
**Produce a decision-enabling comparison. Do not pick the winner.**

## Hard rules

**YOU are the researcher. YOU do the research yourself.**
Do not launch, spawn, dispatch, or report on any other agent.

Your deliverable is a single markdown file: `research/04-ocr-backends.md`.

- **DO** read `NOTES.md`, `AGENTS.md`, `DECISIONS.md`, and
  `research/02-humility-needs.md` for context
- **DO** write the research report to `research/04-ocr-backends.md`
- **DO NOT** modify any file other than `research/04-ocr-backends.md`
- **DO NOT** launch subprocesses
- **DO NOT** pick the winner — present the options for the user

## The OCR Task

Humility is a gaming community Discord server. The owner manually tracks
per-member daily activity points from in-game leaderboard screenshots.
The screenshots show:

- Tabular data: player names (in-game names, may be Unicode) and numeric
  scores
- Dense layout: many rows, sometimes overlapping or partially occluded
- Variable quality: phone photos of screens, cropped screenshots, dark
  backgrounds
- Game-specific UI: the leaderboard format varies by game (Pixel Brave,
  Headless Knight, Sea of Stars, etc.)

The OCR task is: extract (player_name, score) pairs from a screenshot
reliably enough to replace manual spreadsheet entry.

## What to Compare

Evaluate these categories of backend:

### 1. Classical OCR engines
- **Google Cloud Vision** (`DOCUMENT_TEXT_DETECTION`) — hosted, per-image pricing
- **Tesseract** (self-hosted, open source)
- **PaddleOCR** (self-hosted, open source, multilingual)
- **EasyOCR** (self-hosted, open source)

### 2. Vision LLMs
- **Gemini (Flash/Pro)** — structured JSON output, vision input
- **Claude (Haiku/Sonnet)** — vision input, structured output
- **GPT-4o** — vision input

### 3. Mixed architectures
- Classical OCR primary + vision LLM fallback on low confidence
- Vision LLM primary with classical OCR validation

## Evaluation Criteria

For each option, assess:

1. **Accuracy on dense tabular game UIs** — can it handle the specific
   screenshot types described above?
2. **Structured output** — does it natively return structured data
   (JSON), or does it return raw text that needs post-processing?
3. **Cost at MVP scale** — ~5-20 screenshots/day, ~84 members
4. **Cost at scale** — 100+ screenshots/day
5. **Latency** — how long per image?
6. **Reliability** — uptime, rate limits, error modes
7. **Privacy** — does the provider train on input data?
8. **Self-hosting complexity** — if self-hosted, what does deployment look like?
9. **Unicode / multilingual support** — player names may be in any language
10. **Hallucination risk** — for LLM-based options, can the model
    fabricate rows that aren't in the image?

## Output Format

Write `research/04-ocr-backends.md` with:

1. **Task description** — what the OCR system needs to do
2. **Comparison table** — all options side-by-side on the evaluation criteria
3. **Architecture options** — classical-only, LLM-only, mixed, with
   pros/cons of each
4. **Cost modeling** — concrete numbers at MVP and at-scale volumes
5. **Recommendation for further investigation** — which 2-3 options
   the proposal author should consider most seriously, and why
6. **Open questions** — what the user needs to decide

Do not exceed 3000 words.
