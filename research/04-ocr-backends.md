# Research: OCR Backends For Game-Screenshot Activity Extraction

Research date: 2026-04-13

## Scope

This note compares OCR backends for one narrow Humility use case:
extracting `(player_name, score)` pairs from dense game screenshots for
activity tracking.

It is limited to:

- OCR and multimodal backends relevant to stylized game screenshots
- current primary-source pricing, privacy, and capability claims
- workload-specific synthesis for decorative, non-document UI captures

It does not:

- choose the final backend
- propose the final system architecture
- implement or test anything

## Executive summary

For this workload, the field splits into three practical tiers.

`PaddleOCR` is the strongest self-hosted candidate to investigate
first. Its current PP-OCRv5 release explicitly improved detection and
recognition on artistic text, distortion, rotation, and other
non-document scenarios, and a 2026 scene-text benchmark found it to be
the strongest open-source option behind Google Vision.

`Google Cloud Vision` is the strongest managed OCR candidate. It has
low operational burden, predictable per-image cost, bounding-box output,
and the best result in the 2026 real-world scene-text benchmark I found.
It still does not directly return `(name, score)` tuples, so Humility
would need deterministic row-pairing and sanity checks on top.

`Claude Vision` and `Gemini Vision` are the most attractive options if
the priority is direct structured extraction rather than raw OCR text.
They can emit schema-constrained JSON and reason over layout, but their
core risk is different from classic OCR: they can return a perfectly
well-formed but wrong answer. For this workload, that makes them worth
investigating as a comparative track, but risky as an unverified
standalone extractor.

`Tesseract`, `AWS Textract`, and `Azure Vision Read` are lower-priority
for this specific problem. Tesseract is cheap and simple, but its own
docs still emphasize image cleanup to get good results. Textract and
Azure Read are stronger fits for documents than decorative game UIs.

## Comparison matrix

Cost notes:

- Hosted OCR prices below are steady-state paid prices, excluding free
  tiers or introductory credits.
- Self-hosted prices are explicit estimates, not vendor OCR pricing:
  they assume a dedicated always-on AWS Lightsail Linux instance.
  `Tesseract`: Small-2GB at `$12/month`. `PaddleOCR` and `EasyOCR`:
  Medium-4GB at `$24/month`. If Humility co-hosts OCR on an existing
  daemon, marginal cost is lower.
- LLM vision prices below are explicit estimates based on one
  `1920x1080` screenshot and about `60` output tokens. `Claude` uses
  Anthropic's published image-token formula and resize guidance.
  `Gemini` uses Google's published image tiling formula.

| Backend | Accuracy on stylized game text | Structured output support | Cost at 50 / 500 / 5000 images per month | Privacy and retention | Self-hosting burden | Failure modes and detectability | Typical latency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Tesseract` | `Low-Medium`. Upstream still warns that image quality often must be improved for better OCR. A 2026 packaging benchmark found surprisingly strong accuracy on one real-world corpus, but a 2026 scene-text benchmark still trailed Google Vision and PaddleOCR. High workload variance. | `No direct pairs`. Outputs text, `hOCR`, `TSV`, `ALTO`, `PAGE`, PDFs; Humility would need row grouping and score parsing. | About `$12 / $12 / $12` monthly on the stated VM assumption, or effective `$0.24 / $0.024 / $0.0024` per image. | Best privacy profile: images stay on Humility infrastructure. | `Low`. CPU-only, small runtime, no GPU requirement. Container footprint is relatively small by OCR standards. | Common errors are segmentation mistakes, missed glyphs, merged rows, and wrong digits. Detectability is `Medium` because TSV output and confidence proxies make post-checking possible. | Usually the fastest self-hosted CPU option in practice, but upstream docs do not publish a canonical per-image benchmark. Treat as `sub-second to low-single-digit seconds`, hardware-dependent. |
| `PaddleOCR` | `High` among open-source options. PP-OCRv5 explicitly improved complex scenes, distortion, rotation, and artistic text. In the 2026 scene-text benchmark, it was close behind Google Vision and ahead of EasyOCR and Tesseract. | `No direct pairs`. Returns detected text regions, recognized text, and scores, which is better than plain text but still requires pairing logic. | About `$24 / $24 / $24` monthly on the stated VM assumption, or effective `$0.48 / $0.048 / $0.0048` per image. | Best privacy profile when self-hosted. | `Medium`. Heavier Python stack than Tesseract; GPU optional, not required. CPU deployment is feasible but slower. Container footprint is multi-GB in typical packaged deployments. | Common errors are split rows, false positives on decorative UI, and score/name box mismatch. Detectability is `High-Medium` because detection boxes and scores allow stronger sanity checks than Tesseract. | Official PP-OCRv5 benchmark: about `1.75s/image` on CPU for the mobile model and `0.62s/image` on GPU; server models are slower on CPU and about `0.74s/image` on GPU. |
| `EasyOCR` | `Medium`. Scene-text-oriented and easier to use than training your own pipeline, but current evidence still puts it behind PaddleOCR on harder scene-text workloads. | `No direct pairs`. Returns bounding boxes, text, and confidence, so deterministic post-processing is still required. | About `$24 / $24 / $24` monthly on the stated VM assumption, or effective `$0.48 / $0.048 / $0.0048` per image. | Best privacy profile when self-hosted. | `Medium`. Simple `pip` install path, but PyTorch dependency makes it materially heavier than Tesseract. GPU optional. Container footprint is also multi-GB in typical packaged deployments. | Common errors are decorative-text false positives, box fragmentation, and multilingual confusion. Detectability is `High-Medium` because outputs include boxes and confidence. | No vendor-style latency table is published in the README. In practice it is usually `low-single-digit seconds` on CPU and faster on GPU, but this needs local benchmarking. |
| `Google Cloud Vision` | `High`. In the 2026 assistive scene-text benchmark, Google Vision had the highest overall accuracy, with PaddleOCR the closest open-source alternative. | `No direct pairs`. Returns hierarchical OCR output and bounding boxes, not `(name, score)` tuples. | Steady-state paid cost is about `$0.08 / $0.75 / $7.50`. Google also lists the first `1,000` units each month as free, which would reduce the first two scenarios to `$0`. | Images leave Humility infrastructure. Privacy is governed by Google Cloud terms rather than a short public log-retention window on the pricing page. Lower risk than consumer AI services, but still external processing. | `None` operationally beyond API integration. | Common errors are OCR misreads on stylized text and row-order ambiguity. Detectability is `High-Medium` because the API returns bounding boxes and text hierarchy. | Usually `sub-second to a few seconds`, network plus service time. No single canonical latency figure is published on the pricing page. |
| `AWS Textract` | `Low-Medium` for this use case. Textract is document-centric. AWS's own positioning separates Textract document OCR from Rekognition's scene-text detection use cases such as signs and posters. | `No direct pairs`. Returns `Block` objects and relationships; still needs parser logic. | Steady-state paid cost is about `$0.08 / $0.75 / $7.50`. AWS also lists `1,000` free pages/month for the first `3` months. | Images leave Humility infrastructure. AWS docs say Textract stores results internally for retrieval unless `OutputConfig` is used, and AI-services opt-out changes retention behavior. | `None` operationally beyond API integration. | Common errors are document-biased grouping and awkward line segmentation on decorative UIs. Detectability is `Medium` because block graphs help, but false structure can still look plausible. | Usually `sub-second to a few seconds` for simple pages; async flows add polling overhead. |
| `Azure Vision Read` | `Medium`. Azure explicitly targets posters, street signs, and product labels as well as documents, which makes it more scene-friendly than Textract, but I found less direct evidence that it beats Google Vision or PaddleOCR on hard stylized screenshots. | `No direct pairs`. Returns words, lines, and text blocks, not domain tuples. | Steady-state paid cost is about `$0.08 / $0.75 / $7.50`. Azure also lists `500` free pages/month on the Read tier. | Images leave Humility infrastructure in cloud mode, but Azure also offers an OCR container path, which materially changes the privacy story. | `Low` as a hosted API, `Medium` if Humility runs the container. | Common errors are line ordering issues and decorative-background misses. Detectability is `Medium` because line-level output exists, but it still needs pairing logic. | Usually `sub-second to a few seconds` as a cloud API. |
| `Claude Vision` | `Medium-High` for layout-to-JSON extraction, but with lower determinism than OCR APIs. Strength is joint reasoning over text and layout, not raw OCR repeatability. | `Yes`. Anthropic documents structured outputs with JSON-schema compliance, so it can emit `(player_name, score)` objects directly. | Using `Claude Sonnet 4.5` as a realistic comparison point: about `$0.29 / $2.85 / $28.50`. Using `Haiku 4.5` as the low-cost floor would be about `$0.10 / $0.95 / $9.50`. | Images leave Humility infrastructure. Anthropic's data-usage docs for commercial/API users describe no training by default, standard `30-day` retention, and zero-data-retention with appropriately configured API keys. | `None` operationally beyond API integration. | The critical risk is hallucinated but well-formed tuples. Detectability is only `Medium-Low` unless Humility cross-checks totals, row counts, or a second extractor. | Usually `seconds`, with latency increasing on larger images; Anthropic explicitly recommends resizing to about `1.15 MP` for better speed. |
| `Gemini Vision` | `Medium-High` for layout-aware extraction, similar to Claude: stronger at direct tuple extraction than OCR APIs, weaker at deterministic fidelity than classic OCR. | `Yes`. Gemini supports schema-constrained structured output. | Using `Gemini 2.5 Flash` as a realistic comparison point: about `$0.03 / $0.31 / $3.07`. A cheaper floor such as `Gemini 2.5 Flash-Lite` would be even lower. | Images leave Humility infrastructure. Gemini Developer API logs expire after `55` days by default, and Google says paid-project logs are not used for product improvement unless shared. Zero-data-retention options exist but require specific configuration and constraints. | `None` operationally beyond API integration. | Same core risk as Claude: a clean JSON answer can still be wrong. Detectability is `Medium-Low` unless paired with confidence gates or a second extractor. | Usually `seconds`, with token cost and latency driven by image tiling and model choice. |

## Backend-by-backend synthesis

### 1. `Tesseract`

Tesseract remains the cheapest and simplest self-hosted baseline, but
it is not the most promising fit for decorative game screenshots. Its
own README still points users to image-quality improvement guidance,
which is a warning sign for a workload full of gradients, overlays,
glow effects, and evolving UI layouts.

The most important takeaway is variance. A 2025 packaging benchmark
found Tesseract unexpectedly strong on one dense, real-world corpus,
while a 2026 scene-text benchmark put it behind Google Vision and
PaddleOCR. That means Tesseract should be treated as a baseline to
measure against real screenshots, not as a confidence-inspiring default.

### 2. `PaddleOCR`

PaddleOCR is the strongest open-source candidate in this comparison.
Its current PP-OCRv5 documentation explicitly calls out improvements in
challenging scenarios and reports stronger results on artistic text,
rotation, distortion, and general-scene evaluation sets than the prior
generation.

That lines up with the external scene-text benchmark, where PaddleOCR
was the best open-source engine and close to Google Vision overall.
For Humility, that makes it the most credible self-hosted option to
benchmark first.

### 3. `EasyOCR`

EasyOCR is a practical middle ground: easier to stand up than a more
composed OCR stack, more scene-text-friendly than Tesseract, but not as
strongly supported by current evidence as PaddleOCR.

Its main weakness in this comparison is not catastrophic failure. It is
that PaddleOCR looks better on both current evidence and explicit
vendor focus, while EasyOCR still carries the heavier PyTorch runtime
cost of a deep-learning stack.

### 4. Hosted OCR APIs

The hosted OCR APIs are not equally attractive for this use case.

- `Google Cloud Vision` is the strongest managed OCR option here.
  It performed best in the current scene-text benchmark and has
  straightforward OCR pricing.
- `Azure Vision Read` is more plausible than Textract for game
  screenshots because Microsoft explicitly frames Read as useful for
  posters, signs, and product labels, not only documents.
- `AWS Textract` is the weakest fit of the three because AWS positions
  it around document extraction, while scene-text use cases are pushed
  toward Rekognition's text detection.

All three share the same fundamental limitation: they return OCR text
and structure, not domain tuples. Humility would still need deterministic
logic to turn lines and boxes into `(player_name, score)` pairs.

### 5. `Claude Vision` and `Gemini Vision`

These models are attractive because they can skip the OCR-to-parser
split and go directly to schema-constrained JSON. For screenshots with
inconsistent layouts, that matters.

The tradeoff is that their failure mode is harder than ordinary OCR.
Classic OCR usually fails visibly: a wrong digit, a split row, a missed
line. LLM vision can instead fail by producing a tidy structured answer
that looks correct. That makes verification mandatory.

For this workload, the LLM-based options are best thought of as
high-potential extractors with a verification burden, not as
drop-in replacements for OCR.

## Shortlist for further investigation

### 1. `PaddleOCR`

Why it made the shortlist:

- strongest open-source fit for stylized scene text
- self-hosted privacy profile is the cleanest
- returns boxes and scores, which makes downstream verification easier
  than plain-text OCR
- current documentation and recent external evidence both support it as
  the best open-source place to start

### 2. `Google Cloud Vision`

Why it made the shortlist:

- strongest managed OCR evidence on current scene-text benchmarking
- low ops burden and predictable per-image pricing
- easier to trial quickly than a self-hosted stack
- likely to set a useful "managed baseline" for accuracy and latency

### 3. `Gemini Vision` or `Claude Vision`

Why the LLM track made the shortlist:

- direct structured extraction is genuinely useful for this problem
- layout reasoning may help when rows are visually noisy or not perfectly
  aligned
- cost is no longer prohibitive, especially on Gemini's lower-cost
  models

Why it is a comparative track, not a default winner:

- verification burden is materially higher than with OCR APIs
- wrong structured output is more dangerous than visibly noisy OCR text

If only two options are taken forward, the best pair is `PaddleOCR`
plus `Google Cloud Vision`.

## Known risks and mitigations for shortlisted options

### `PaddleOCR`

Known risks:

- performance can still degrade after a game UI patch changes fonts,
  spacing, or overlays
- OCR boxes and text may be individually correct but paired into the
  wrong rows
- CPU-only latency may be acceptable for Humility's volume, but not for
  instant feedback if the UX becomes synchronous

Mitigations:

- build a gold-set of real screenshots before choosing anything
- record detection boxes and scores so failures are inspectable
- validate extracted scores with numeric regexes, row counts, and
  threshold checks
- benchmark both CPU and GPU modes before assuming GPU is necessary

### `Google Cloud Vision`

Known risks:

- image data leaves Humility infrastructure
- OCR still requires a deterministic pairing layer for `(name, score)`
- vendor lock-in risk is higher than with self-hosted OCR

Mitigations:

- scope a trial against a real screenshot corpus before deeper
  integration
- keep the parser layer backend-agnostic so OCR engines can be swapped
- use region controls and standard cloud governance review before
  production use

### `Gemini Vision` / `Claude Vision`

Known risks:

- hallucinated tuples can look correct enough to pass casual review
- latency and cost vary more by model choice and prompt design than with
  classic OCR
- retention posture is weaker than self-hosting unless higher-tier data
  controls are configured

Mitigations:

- require schema-constrained output
- cross-check totals, row counts, and numeric ranges before accepting
  output
- consider dual extraction during evaluation, such as LLM output plus a
  classical OCR cross-check
- route low-confidence or inconsistent results to human review

## Open questions before final backend selection

- What does the real screenshot corpus look like across devices,
  resolutions, crops, and game updates?
- Are player names always Latin-script, or do they include Unicode,
  emoji-like glyphs, clan tags, or mixed scripts?
- Is Humility willing to send screenshots to external APIs, or is
  self-hosting a policy requirement?
- What error rate is operationally acceptable: one wrong player per
  hundred screenshots, one wrong score per thousand, or something else?
- Is the intended UX synchronous at upload time, or is batch processing
  acceptable?
- Are screenshots full-screen captures, or can the UI be cropped to a
  smaller known region first?
- Will Humility keep a retained gold-set of screenshots for regression
  testing after game UI changes?
- Does the workflow need only `(name, score)` extraction, or also
  duplicate detection, date extraction, chapter mapping, or screenshot
  authenticity checks?

## Recommendation boundary

This research supports a shortlist, not a final choice.

The strongest current evidence supports:

1. `PaddleOCR` as the best self-hosted candidate to benchmark
2. `Google Cloud Vision` as the best managed OCR baseline
3. one `LLM vision` track as a structured-extraction comparison, with
   strict verification

That is enough to move into Humility-specific synthesis and later
proposal work, but not enough to skip corpus-based evaluation.

## Cost assumptions and source-derived formulas

### Self-hosted OCR estimate basis

These are explicit estimates, not OCR-vendor prices:

- AWS Lightsail `Small-2GB Linux`: `$12/month`
- AWS Lightsail `Medium-4GB Linux`: `$24/month`

Interpretation:

- `Tesseract` can plausibly live on the smaller instance
- `PaddleOCR` and `EasyOCR` were modeled on the larger instance because
  their Python ML stacks are heavier
- if Humility already runs an always-on daemon host with spare CPU and
  RAM, marginal OCR cost may be close to zero

### LLM vision estimate basis

`Claude Sonnet 4.5` estimate:

- image input assumed at about `1,600` tokens after resize guidance
- output assumed at about `60` tokens
- cost per image about `((1600 * $3) + (60 * $15)) / 1,000,000`
- result: about `$0.0057/image`

`Gemini 2.5 Flash` estimate:

- `1920x1080` image
- Gemini tiling formula gives `6` tiles
- each tile costs `258` image tokens, so about `1,548` input tokens
- output assumed at about `60` tokens
- cost per image about `((1548 * $0.30) + (60 * $2.50)) / 1,000,000`
- result: about `$0.000614/image`

## Primary sources consulted

### Upstream docs and pricing

- [Tesseract README](https://github.com/tesseract-ocr/tesseract)
- [Tesseract user docs](https://tesseract-ocr.github.io/)
- [PP-OCRv5 Introduction](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)
- [EasyOCR README](https://github.com/JaidedAI/EasyOCR)
- [Google Cloud Vision pricing](https://cloud.google.com/vision/pricing)
- [AWS Textract pricing](https://aws.amazon.com/textract/pricing/)
- [AWS Textract `OutputConfig`](https://docs.aws.amazon.com/textract/latest/dg/API_OutputConfig.html)
- [Azure Vision OCR overview](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)
- [Azure Vision pricing](https://azure.microsoft.com/en-us/pricing/details/computer-vision/)
- [Azure Document Intelligence pricing](https://azure.microsoft.com/en-us/pricing/details/document-intelligence/)
- [Anthropic pricing](https://www.anthropic.com/pricing#api)
- [Anthropic data usage](https://docs.anthropic.com/en/docs/claude-code/data-usage)
- [Anthropic Vision docs](https://docs.anthropic.com/en/docs/build-with-claude/vision)
- [Anthropic structured output guidance](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini image understanding docs](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Gemini structured output docs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini data logging and sharing](https://ai.google.dev/gemini-api/docs/logs-policy)
- [Gemini zero data retention](https://ai.google.dev/gemini-api/docs/zdr)
- [AWS Lightsail instance bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)

### Comparative research used for workload-specific synthesis

- [Evaluating OCR Performance for Assistive Technology: Effects of Walking Speed, Camera Placement, and Camera Type](https://arxiv.org/abs/2602.02223)
- [Evaluating OCR performance on food packaging labels in South Africa](https://arxiv.org/abs/2510.03570)
