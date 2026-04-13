# OCR backend options for game-screenshot activity extraction

As of 2026-04-13, Humility’s OCR task is: take a leaderboard screenshot posted in Discord and extract reliable `(player_name, score)` pairs from dense, game-specific UIs with dark backgrounds, partial occlusion, and multilingual names. The target is to replace manual spreadsheet entry, so the practical question is not “can this read text at all,” but “can this read crowded score tables with low enough error and enough structure to support officer workflows.”

Important caveat: the accuracy assessments below are expected fit based on vendor capabilities and documented output formats, not a measured benchmark on Humility screenshots. A real decision still needs a small eval set from Pixel Brave, Headless Knight, Sea of Stars, and any other live chapter games.

## Comparison table

| Option | Dense tabular game UI fit | Structured output | MVP cost (150-600 imgs/mo) | 100+/day cost (3000 imgs/mo) | Latency | Reliability | Privacy / training | Self-hosting complexity | Unicode / multilingual | Hallucination risk |
|---|---|---|---:|---:|---|---|---|---|---|---|
| Google Cloud Vision `DOCUMENT_TEXT_DETECTION` | Medium-High. Mature OCR, word boxes, confidences; no native table semantics | JSON OCR hierarchy, but not native `(player, score)` schema | $0 if under first 1,000 images/mo | ~$3/mo at 3,000 imgs/mo | Low seconds | Strong managed service; quota-bound | Google Cloud terms say customer data is not used to train/fine-tune AI/ML models without permission | None | Strong language coverage, auto-detect + hints | None; misreads/drops instead |
| Tesseract | Low-Medium. Very preprocessing-sensitive; weak on crowded/overlapping rows | `txt`, `tsv`, `hocr`, PDF; parser required | $0 license; infra only | $0 license; infra only | Fast on CPU, but quality tuning costs time | Your uptime, your bugs | Best privacy; stays on your infra | Low install, high tuning burden | UTF-8, 100+ languages | None |
| PaddleOCR | Medium-High among classical engines. Better fit for dense layouts; table-structure tooling exists | OCR results plus PP-Structure/table modules | $0 license; infra only | $0 license; infra only | CPU/GPU; usually sub-second to low seconds | Your uptime; more moving parts than Tesseract | Best privacy; stays on your infra | Medium. Python/Docker/Paddle runtime, CPU or GPU tuning | Strong multilingual support | None |
| EasyOCR | Medium. Better than raw Tesseract on messy screenshots, but no table model | Bounding boxes, text, confidence; parser required | $0 license; infra only | $0 license; infra only | Low seconds; model load matters | Your uptime; fewer external dependencies than APIs | Best privacy; stays on your infra | Low-Medium. Simple Python install, Torch dependency | 80+ languages, but not all language combos work together | None |
| Gemini Flash | Medium-High. Vision model can reason over rows and return final pairs directly | Native structured outputs with JSON schema | Roughly $0.4-$1.5/mo* | Roughly $7.5/mo* | Low seconds | Managed API; tier/rate-limit dependent | Paid tier: prompts/files not used to improve products; unpaid tier: yes | None | Good multilingual handling | Medium |
| Gemini Pro | High expected fit, especially when layout reasoning matters more than raw OCR | Native structured outputs with JSON schema | Roughly $1.5-$6/mo* | Roughly $30/mo* | Multi-second, slower than Flash | Managed API; tier/rate-limit dependent | Paid tier: prompts/files not used to improve products; unpaid tier: yes | None | Good multilingual handling | Medium |
| Claude Haiku | Medium. Fast and cheap, but weaker than Sonnet on ambiguous dense layouts | Good JSON via tool schema / constrained prompting, less “native” than Gemini/OpenAI | Roughly $0.9-$3.6/mo* | Roughly $18/mo* | Low seconds | Managed API; rate-limit tiers published | Commercial/API use is not trained on by default | None | Strong multilingual handling | Medium |
| Claude Sonnet | High expected fit. Stronger visual reasoning for crowded rows and partial occlusion | Good JSON via tool schema / constrained prompting | Roughly $2.7-$10.7/mo* | Roughly $54/mo* | Multi-second | Managed API; rate-limit tiers published | Commercial/API use is not trained on by default | None | Strong multilingual handling | Medium-High |
| GPT-4o | High expected fit. Strong multimodal reasoning and native structured outputs | Native structured outputs | Roughly $1.3-$5.2/mo* | Roughly $25.8/mo* | Low-to-mid seconds | Managed API; usage-tier rate limits published | API inputs/outputs are not used for training by default | None | Strong multilingual handling | Medium |

\* LLM cost estimates are illustrative, not quoted list prices per screenshot. They assume one 1080x2400-ish screenshot and about 500 output tokens per result. Real cost moves with image resolution, number of visible rows, and whether retries/human-review prompts are needed.

## Architecture options

### 1. Classical-only

Pros:
- Lowest hallucination risk. Engines misread or omit text, but they do not invent players.
- Cheapest ongoing vendor cost, especially self-hosted.
- Easier to justify in an audit trail because outputs map to OCR boxes/confidences.

Cons:
- You still need game-specific post-processing to pair names and scores.
- Dense layouts, dark themes, and overlap are exactly where classical OCR degrades.
- New games may require preprocessing rules rather than just a prompt change.

### 2. LLM-only

Pros:
- Fastest path to direct `(player_name, score)` JSON.
- Best adaptability to changing game UIs without writing table parsers.
- Handles “understand the screenshot” and “format the answer” in one step.

Cons:
- Highest hallucination risk: a model can output a row that looks plausible but is not present.
- Harder to produce calibrated confidence per row.
- Reliability depends on prompt discipline and downstream validation, not just vendor uptime.

### 3. Mixed

Two viable variants:
- Classical OCR primary + vision LLM fallback on low confidence / parse failure
- Vision LLM primary + classical OCR validation on names/scores/bounding boxes

Pros:
- Best tradeoff if Humility wants high automation without fully trusting a single model pass.
- Lets classical OCR act as a non-hallucinating evidence layer while LLMs solve layout ambiguity.
- Keeps LLM spend small because only ambiguous cases escalate.

Cons:
- More implementation work: routing, confidence thresholds, disagreement handling.
- Requires defining what “low confidence” means at row level, not just whole-image level.
- Debugging is more complex because failures can come from either stage or the merge logic.

## Cost modeling

Assumptions:
- MVP volume: 5-20 screenshots/day = 150-600/month
- Scale volume: 100 screenshots/day = 3,000/month
- Google Vision pricing is exact list pricing
- Self-hosted rows show software cost only; infra cost depends on whether Humility already has a Python host

Hosted OCR / vision:
- Google Cloud Vision: first 1,000 images/month free, then $1.50 per 1,000 for `DOCUMENT_TEXT_DETECTION`. That makes MVP effectively $0/month and 3,000 images/month about $3/month.
- Gemini Flash: approximately $0.0025/image under the assumption above, so about $0.38-$1.50/month at MVP and about $7.50/month at 3,000 images/month.
- Gemini Pro: approximately $0.010/image, so about $1.50-$6/month at MVP and about $30/month at 3,000 images/month.
- Claude Haiku: approximately $0.006/image, so about $0.90-$3.60/month at MVP and about $18/month at 3,000 images/month.
- Claude Sonnet: approximately $0.018/image, so about $2.70-$10.70/month at MVP and about $54/month at 3,000 images/month.
- GPT-4o: approximately $0.0086/image, so about $1.29-$5.16/month at MVP and about $25.80/month at 3,000 images/month.

Self-hosted OCR:
- Tesseract / PaddleOCR / EasyOCR: $0 license cost at both MVP and scale. In practice, the cost question is not per-image billing but whether Humility wants to own Python runtime, model downloads, image preprocessing, and CPU/GPU performance tuning.

## Recommendation for further investigation

The proposal author should seriously investigate these three paths:

1. **Google Cloud Vision** as the hosted classical baseline. It is the cheapest managed option, returns OCR structure plus confidences, and sets a strong “no hallucinations” reference point.
2. **PaddleOCR** as the strongest open-source classical candidate. Relative to Tesseract and EasyOCR, it is the most aligned with dense layouts because it has stronger multilingual OCR tooling and table-structure support.
3. **Mixed architecture: classical OCR primary + LLM fallback**, with Gemini Flash or GPT-4o as the fallback model. This is the most plausible way to get both low operational cost and acceptable accuracy on messy screenshots without fully trusting hallucination-prone end-to-end vision output.

That is not a winner declaration. It is a shortlist for the next phase because it covers the three materially different bets: hosted deterministic OCR, self-hosted deterministic OCR, and hybrid reasoning.

## Open questions

1. What error rate is acceptable before officer review is still cheaper than manual entry?
2. Must every extracted row be backed by a visible bounding box/confidence for auditability?
3. Are chapter screenshots allowed to leave Humility-controlled infrastructure, or is self-hosting preferred on privacy grounds?
4. Is Humility willing to maintain image preprocessing rules per game, or is prompt-only adaptability more valuable?
5. Should the system optimize for “fully automatic insert” or for “draft extraction for officer confirmation”?
6. What eval set will be used for the next phase, and how many screenshots per game are needed to make the comparison real?

## Sources

- Google Cloud Vision pricing: https://cloud.google.com/vision/pricing
- Google Cloud Vision OCR language support: https://cloud.google.com/vision/docs/languages
- Google Cloud Vision OCR response structure: https://cloud.google.com/vision/docs/reference/rest/v1p2beta1/images/annotate
- Google Cloud AI/ML training restriction: https://cloud.google.com/terms/service-terms/index-20240606
- Tesseract docs and outputs: https://tesseract-ocr.github.io/tessdoc/FAQ.html
- Tesseract language support: https://github.com/tesseract-ocr/tesseract
- PaddleOCR installation: https://www.paddleocr.ai/main/en/version3.x/installation.html
- PaddleOCR table structure / PP-Structure: https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppstructure/overview.html
- EasyOCR README: https://github.com/JaidedAI/EasyOCR
- Gemini structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini vision tokenization: https://ai.google.dev/gemini-api/docs/vision
- Gemini pricing and data-use terms: https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/terms_preview
- Anthropic model pricing: https://platform.claude.com/docs/en/about-claude/models/overview
- Anthropic vision costs: https://platform.claude.com/docs/en/build-with-claude/vision
- Anthropic rate limits: https://docs.anthropic.com/en/api/rate-limits
- Anthropic commercial data usage: https://docs.anthropic.com/en/docs/claude-code/data-usage
- OpenAI GPT-4o model page: https://developers.openai.com/api/docs/models/gpt-4o
- OpenAI vision cost calculation: https://platform.openai.com/docs/guides/images-vision
- OpenAI business/API data privacy: https://openai.com/business-data/
