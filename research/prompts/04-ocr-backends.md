# Research prompt — OCR backend options for game-screenshot activity extraction

You are a `gpt-high` research worker. Your job is to produce a
decision-enabling comparison of OCR backends, not to make the final
choice.

## Output

Write your report to `research/04-ocr-backends.md`.

## Context

The Humility Discord server needs to track per-player activity points
from game screenshots. Members currently do this manually via a
spreadsheet. The target workflow: a member uploads a screenshot of a
game's activity/points screen, the system extracts `(player_name, score)`
pairs, and logs them for daily tracking and compliance flagging.

These are **dense, stylized game screenshots** — not generic documents.
Expect custom fonts, decorative backgrounds, varying layouts across
game updates, and potentially overlapping text elements. The system
needs to reliably extract structured data (player names and numeric
scores) from this visual noise.

## Requirements

Compare at least the following backends:

1. **Tesseract** (open-source, self-hosted)
2. **PaddleOCR** (open-source, self-hosted)
3. **EasyOCR** (open-source, self-hosted)
4. **Hosted Vision APIs** (Google Cloud Vision, AWS Textract, Azure
   Computer Vision)
5. **Claude Vision / Gemini Vision** (LLM-based multimodal extraction)

For each backend, evaluate:

- **Accuracy on stylized game text**: How well does it handle custom
  fonts, colored text on complex backgrounds, non-standard layouts?
- **Structured output support**: Can it directly produce `(name, score)`
  pairs, or does it require post-processing?
- **Cost modeling**: Per-image cost at 50, 500, and 5000 images/month.
  Include self-hosting compute costs for open-source options.
- **Privacy and data retention**: Where does the image data go? What
  are the retention policies? Is there a compliance risk for a Discord
  community?
- **Self-hosting burden**: Setup complexity, maintenance overhead,
  GPU requirements, container size.
- **Failure modes**: What happens when extraction fails? Partial
  results? Silent errors? How detectable are failures?
- **Latency**: Per-image processing time for typical game screenshots.

## Deliverables

Your report should include:

1. A comparison matrix covering all backends and evaluation criteria
2. A shortlist of 2-3 backends recommended for further investigation,
   with reasoning
3. Open questions that need answers before a final backend can be
   selected
4. Known risks and mitigations for each shortlisted option

## Hard rules

- You are the researcher. Do your own work — do not delegate to other
  agents or suggest that someone else should investigate.
- Do NOT inspect the Discord server or run any Discord commands.
- Do NOT propose the final backend architecture — that is a later phase.
- Do NOT implement anything — this is research only.
- Focus on the specific use case (game screenshot activity extraction),
  not generic OCR capabilities.
