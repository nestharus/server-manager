# OCR backend options for game-screenshot activity extraction

_Captured and synthesized on April 11, 2026._

## Scope and framing

The target input is not a clean document. It is a stylized game screenshot: leaderboard/activity panels, 10-50 player rows, scores, dates/timestamps, icons, gradients, translucent overlays, and game fonts. That matters because most OCR products are optimized either for documents/forms or for general scene text, not for dense HUD tables. The practical question is not “which OCR is best in general,” but “which backend can reliably turn a medium number of screenshots per day into `(player_name, activity_points, date)` rows with tolerable ops cost and a clear failure story.”

One broad conclusion from the research: evidence for **game-UI OCR specifically is thin**. There are many document-OCR benchmarks and some scene-text benchmarks, but far fewer game-HUD datasets. A recent game-text thesis explicitly notes the lack of benchmark datasets for OCR in games and builds around that gap ([Automatic In-Place Text Detection and Translation, 2025](https://run.unl.pt/bitstream/10362/190204/1/TGI4549.pdf)). So the ratings below are partly based on vendor docs, model design, and community operating experience, not on a definitive public benchmark for “Discord-uploaded game leaderboard screenshots.”

## What matters technically for this use case

For this task, raw text recognition is only part of the problem. The backend also needs to:

- preserve row structure well enough to keep `player_name` aligned with the right score
- tolerate stylized fonts, colored backgrounds, icons, and imperfect crops
- behave predictably on small text and numerals
- fit either a small Railway container or a modest hosted bill
- expose enough structure or confidence metadata to support validation

The hardest failure modes are not “no text found.” They are:

- missed digits (`1834` -> `134` or `183`)
- row merge/split errors
- name-score misalignment across adjacent rows
- icons interpreted as digits or punctuation
- hallucinated rows when a vision LLM tries to “complete” a partially legible table

Region-of-interest cropping is therefore high leverage. Every backend looks better if the bot first crops the relevant leaderboard panel and, when possible, chops a tall screenshot into smaller row bands.

## Backend-by-backend notes

### Tesseract

Sources: [project site](https://tesseract-ocr.github.io/), [user manual](https://tesseract-ocr.github.io/tessdoc/), [GitHub](https://github.com/tesseract-ocr/tesseract)

Tesseract is the baseline self-hosted option: mature, portable, free, CPU-only, and easy to package in a container. It supports many languages and gives you classic OCR controls such as page segmentation mode, whitelists, and image preprocessing hooks.

For game UIs, its ceiling is limited. Tesseract is still strongest on high-contrast, relatively regular text. It can do well on cropped numeric columns or clean name cells, but full-screen HUD OCR is where it usually breaks down first. The predictable pattern is: decent on simple numbers after preprocessing, weak on stylized fonts and mixed icon/text rows, and very weak at preserving table structure without an external layout step.

Deployment fit is excellent. Installing `tesseract-ocr` plus selected language packs is small by OCR standards and works fine on CPU in a small Railway container. Cold start is negligible compared with deep-learning OCR stacks. If the pipeline becomes “crop -> threshold/upscale -> Tesseract on a narrow region,” it remains attractive.

Fine-tuning is possible but relatively painful. Custom training exists, but it is not the shortest path for an MVP with 1-30 screenshots/day.

### PaddleOCR

Sources: [PaddleOCR repo](https://github.com/PaddlePaddle/PaddleOCR), [docs](https://www.paddleocr.ai/)

Among open-source OCR stacks, PaddleOCR is one of the strongest fits for noisy UI text. Its detector + recognizer pipeline is closer to scene-text OCR than Tesseract, it supports 100+ languages, and the project explicitly publishes inference/benchmark guidance for different configurations. The current repo also notes split core vs optional dependencies and deployment references for latency and memory on common hardware.

For game screenshots, PaddleOCR is one of the more credible OSS options because it is better than Tesseract at finding text regions on non-document backgrounds. It still will not “understand” a leaderboard semantically, but it is materially better positioned to recover bounding boxes and text from stylized panels. Likely failure mode: the recognizer catches text, but row grouping still needs custom post-processing.

Deployment cost is higher than Tesseract. `paddlepaddle` plus model weights is a real container-size and cold-start tax. CPU inference is viable for MVP volume, but expect slower startup and higher RAM usage. It should still fit a small-to-medium Railway service if the container is built carefully and models are cached into the image.

PaddleOCR also has the cleanest story among OSS options for future custom training if a specific game UI eventually dominates.

### EasyOCR

Sources: [GitHub](https://github.com/JaidedAI/EasyOCR)

EasyOCR is attractive because it is easy to call from Python and returns bounding boxes, text, and confidence with little setup. It supports many languages and is simpler to integrate than PaddleOCR.

The tradeoff is that it is usually chosen for convenience first, not maximum accuracy. On game HUDs it should outperform Tesseract on many screenshots, but it is generally not the OSS option people reach for when they need the strongest small-text/stylized-text recovery. A reasonable expectation is “good prototype path, medium ceiling.”

Operationally, EasyOCR is heavier than it looks because it pulls in PyTorch and model weights. On Railway that means bigger images, slower cold starts, and more RAM pressure than Tesseract. At MVP volume that is still feasible, but it is not “cheap” in container terms.

### docTR

Sources: [docTR docs](https://mindee.github.io/doctr/), [GitHub](https://github.com/mindee/doctr)

docTR is a modern deep-learning OCR library with separate detection and recognition components. It is document-oriented in branding, but technically flexible enough for arbitrary image OCR, and it exposes geometry that is useful for row reconstruction.

For this use case, docTR sits in the middle: more modern than Tesseract, less battle-tested for game UI than PaddleOCR’s broader scene-text positioning. It should be capable when the screenshot panel is reasonably clean, but the “document-first” orientation is a warning sign for HUDs with heavy game styling.

Ops cost is similar to other deep stacks: PyTorch or TensorFlow backend, model downloads, heavier import time, more RAM, and a larger image than a Tesseract-based service. Feasible, but not the lightest choice for a single small Railway worker.

### Google Cloud Vision

Sources: [pricing](https://cloud.google.com/vision/pricing), [quotas](https://cloud.google.com/vision/quotas), [product docs](https://cloud.google.com/vision/docs)

Cloud Vision’s `TEXT_DETECTION` and `DOCUMENT_TEXT_DETECTION` are standard hosted OCR baselines. They are easy to call, low-ops, and cheap at MVP volume. Pricing as of capture: first 1,000 units/month are free, then `$1.50 / 1,000` units for both Text Detection and Document Text Detection. At 900 screenshots/month, that is effectively **$0/month** if the free tier is unused elsewhere, or **$1.35/month** without the free tier.

For game UIs, the likely profile is “better than Tesseract on general OCR, but still not a semantic table extractor.” Vision returns hierarchical text structure and boxes, which is helpful. It also has strong quotas for this use case: 1,800 text-detection requests/minute by default, far above MVP and 10x MVP volume.

Its main limitation is the same as most classic OCR APIs: it reads text, but does not reliably solve row semantics. The bot would still need grouping logic.

### AWS Textract

Sources: [pricing](https://aws.amazon.com/textract/pricing/), [quota docs](https://docs.aws.amazon.com/textract/latest/dg/limits-quotas-explained.html)

Textract is document-centric. For this task, that is both its strength and its weakness. If the screenshot resembles a rigid table, Textract can be compelling. If it looks like a game HUD with icons, glow, gradients, or floating panels, its document assumptions become a liability.

Pricing for `DetectDocumentText` is straightforward: `$0.0015/page` for the first million pages in US West (Oregon). At 900 screenshots/month, that is **$1.35/month**. The API is near-real-time for single-page documents, and AWS positions the synchronous APIs for single-page processing.

The bigger concern is fit, not cost. Textract’s advanced structured features are aimed at forms, queries, signatures, receipts, IDs, and lending docs, not game leaderboards. Custom Queries/adapters exist, but they are still document-oriented and feel like overkill for an MVP unless the screenshots happen to be extremely form-like.

### Azure AI Vision / Read / Document Intelligence

Sources: [Azure Vision pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/computer-vision/), [Vision docs](https://learn.microsoft.com/azure/ai-services/computer-vision/)

Azure splits older OCR and the newer Read path. The pricing page currently places `OCR` in Group 1 at `$1.00 / 1,000` transactions and `Read` in Group 2 at `$1.50 / 1,000`; the free tier includes 5,000 transactions/month and 20 TPM. For 900 screenshots/month, Read is either **$0** on F0 or **$1.35/month** on S1 arithmetic.

Practically, the newer Read path is the relevant one. Like Google Vision, Azure is cheap, low-ops, and returns structured OCR output that can feed row grouping. It is still fundamentally OCR, not semantic UI understanding.

The public pricing/docs are strong on cost, but thinner on “game UI” evidence. Expect similar behavior to Google Vision: viable baseline, especially if you crop panels first, but still not a one-step row extractor.

### Hugging Face OCR models (TrOCR and relatives)

Sources: [Transformers OCR task docs](https://huggingface.co/docs/transformers/tasks/optical_character_recognition), [TrOCR model card](https://huggingface.co/microsoft/trocr-base-printed)

The important nuance here is that “Hugging Face OCR” is not one backend. It is a toolbox. TrOCR is strong as a recognizer, but not a complete end-to-end screenshot OCR solution by itself. In practice you usually need a detector first, then cropped word/line images for the recognizer.

That makes the Hugging Face path flexible but operationally expensive. It is best if the team is willing to own a custom pipeline and possibly fine-tune later. It is not the shortest path to an MVP on Railway. CPU-only inference is possible, but model load time and latency are worse than Tesseract and often worse than a well-packaged PaddleOCR deployment.

The upside is portability: very low vendor lock-in and a clear future path if a specific game eventually justifies task-specific tuning.

### OpenAI vision models

Sources: [images and vision guide](https://developers.openai.com/api/docs/guides/images-vision), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [pricing](https://developers.openai.com/api/docs/pricing), [data controls](https://developers.openai.com/api/docs/guides/your-data)

OpenAI’s vision-capable general models are the clearest “skip classical OCR and ask for rows directly” option. The structured-output story is mature: JSON Schema is supported, strict schema adherence is documented, refusals are programmatically detectable, and image input cost is explicitly tokenized.

This is the strongest path for **one-shot structured extraction**, but it is not free of OCR failure. The model can read screenshots and return rows directly, yet the documented limitations still include small text, rotation, spatial reasoning, and occasional inaccuracies. Dense HUD tables with many tiny rows are exactly where a model may miss a digit or infer a row that is only half visible.

Representative cost for a dense `1024x1024` screenshot on `gpt-5.4-mini`:

- image input: `1024` 32px patches × `1.62` multiplier = `1659` image tokens ([tokenization guide](https://developers.openai.com/api/docs/guides/images-vision))
- input cost: `1659 / 1,000,000 × $0.75 = $0.00124`
- if output is ~150 tokens of JSON: `150 / 1,000,000 × $4.50 = $0.000675`
- rough total: **$0.0019/image**, or **about $1.73/month** at 900 images

On full `gpt-5.4`, the same arithmetic is about **$5.76/month**. These are still small numbers at MVP scale.

Data/privacy posture is explicit: API data is not used for training by default; abuse-monitoring logs are retained up to 30 days unless approved for modified or zero data retention; image/file inputs can still be retained for manual review if flagged for CSAM. OpenAI also now documents regional storage/processing options for several regions.

### Anthropic Claude Vision

Sources: [vision docs](https://docs.anthropic.com/en/docs/build-with-claude/vision), [pricing](https://docs.anthropic.com/en/docs/about-claude/pricing), [tool use overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)

Claude is similar to OpenAI in product shape: general multimodal reasoning, strong extraction quality, and a credible tool/schema path. Anthropic’s docs explicitly recommend resizing images to about `1.15 MP` and give a direct image-token formula: `tokens = (width * height) / 750` when the image does not need resizing.

For a ~1 MP screenshot on Sonnet 4.6:

- input tokens: about `1334`
- input cost: `1334 / 1,000,000 × $3 = $0.0040`
- with ~150 output tokens: `150 / 1,000,000 × $15 = $0.00225`
- rough total: **$0.00625/image**, or **about $5.63/month** at 900 images

Haiku 4.5 is much cheaper: roughly **$1.88/month** on the same assumptions.

Claude’s docs are especially candid about image limits: small text, spatial reasoning, and hallucination are real concerns. It also supports strict tool use, which helps when you want the model to emit schema-conforming arguments. That makes it usable for row extraction, but the same caution applies as with OpenAI: schema validity is not semantic truth.

### Google Gemini Vision

Sources: [pricing](https://ai.google.dev/gemini-api/docs/pricing), [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [token counting](https://ai.google.dev/gemini-api/docs/tokens), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

Gemini is the cheapest of the big vision-LLM options on current published pricing, while still supporting JSON-schema constrained output. Google’s docs are unusually explicit on multimodal tokenization: images up to `384x384` count as `258` tokens; larger images are tiled into `768x768` tiles, each also `258` tokens.

For a `1024x1024` screenshot, a practical estimate is four tiles, or about `1032` input tokens. On `Gemini 3 Flash Preview` pricing:

- input cost: `1032 / 1,000,000 × $0.50 = $0.000516`
- ~150 output tokens at `$3 / MTok` = `$0.00045`
- rough total: **$0.00097/image**, or **about $0.87/month** at 900 images

Gemini 3.1 Pro Preview pricing is higher but still modest. Structurally, Gemini is in the same camp as OpenAI and Claude: strong one-shot extraction potential, but output values still require validation. Google’s structured-output docs say the JSON will be syntactically valid and schema-matching, but explicitly warn that values may still be semantically wrong.

One notable policy detail: Google’s pricing page states that **free-tier** Gemini Developer API content is used to improve products, while **paid-tier** content is not. That is a meaningful privacy distinction.

## Deployment shape for Railway + Supabase

### Self-hosted options

- **Tesseract**: easiest container fit; CPU-only; low cold-start cost; best when paired with aggressive preprocessing and ROI cropping.
- **PaddleOCR**: still realistic on Railway, but heavier image, more RAM, slower import/model load; strongest OSS candidate if staying self-hosted.
- **EasyOCR**: moderate implementation effort, but PyTorch weight and cold-start tax are significant.
- **docTR**: similar or heavier than EasyOCR; viable, but not lightweight.
- **Hugging Face models**: highest engineering flexibility, highest pipeline ownership burden, weakest fit for “small always-on Railway worker” unless there is later justification for custom training.

### Hosted options

- **Google Vision / AWS Textract / Azure Read**: trivial ops, tiny MVP bill, straightforward API-key management, good fit if you want deterministic OCR plus your own row parser.
- **OpenAI / Anthropic / Gemini**: also trivial ops and still low MVP bill, but you are buying semantic extraction rather than pure OCR. This reduces post-processing work and increases ambiguity risk.

### Mixed shape

The most credible mixed architecture is:

1. cheap deterministic OCR or OSS OCR on cropped regions
2. escalate only ambiguous screenshots to a vision LLM

That contains hosted spend, reduces hallucination exposure, and keeps a portable fallback. It also matches the actual volume: 900 images/month is low enough that a fallback tier is operationally simple.

## Structured output and hallucination risk

For the vision LLMs, JSON/schema support is good:

- OpenAI: strong JSON Schema support with strict mode and explicit refusal handling
- Anthropic: strong tool-call schema path with `strict: true`
- Gemini: explicit JSON-schema response mode and streaming structured output

The failure is not malformed JSON. The failure is **wrong-but-valid JSON**.

Hallucination controls worth carrying into any proposal:

- return raw extracted text alongside normalized fields
- require per-row evidence snippets or quoted OCR text
- run a second pass that validates totals/row counts against the image
- fall back to a classical OCR pass when the LLM reports uncertainty or returns sparse rows
- flag low-confidence screenshots for human review instead of silently writing rows

## Cost model at MVP volume

Assumption: `30 images/day × 30 days = 900 images/month`, single screenshot = single page / single OCR transaction.

| Backend | Pricing basis | Monthly cost at 900 images |
| --- | --- | --- |
| Google Cloud Vision | `$1.50 / 1,000` units after first 1,000 free | `$0` with unused free tier, otherwise `$1.35` |
| AWS Textract DetectDocumentText | `$0.0015 / page` | `$1.35` |
| Azure Read | `$1.50 / 1,000` transactions; F0 gives 5,000 free/month | `$0` on F0, otherwise `$1.35` |
| OpenAI `gpt-5.4-mini` vision | ~`$0.0019 / image` representative | `~$1.73` |
| OpenAI `gpt-5.4` vision | ~`$0.0064 / image` representative | `~$5.76` |
| Claude Haiku 4.5 vision | ~`$0.0021 / image` representative | `~$1.88` |
| Claude Sonnet 4.6 vision | ~`$0.00625 / image` representative | `~$5.63` |
| Gemini 3 Flash Preview vision | ~`$0.00097 / image` representative | `~$0.87` |

At MVP volume, the hosted options are all either pennies or low single-digit dollars per month. The meaningful budget question is not raw inference spend; it is whether the project wants another vendor dependency and whether validation logic offsets the convenience of one-shot extraction.

## Operational risks

- **Rate limits**: MVP and 10x MVP are trivial for every hosted option researched. Google Vision defaults to 1,800 text-detection requests/minute. Azure F0 is only 20 TPM, but even that is comfortably above 300 screenshots/day. AWS synchronous single-page OCR is also comfortably within default quotas at this scale. Gemini/OpenAI/Anthropic rate limits are tiered, but this workload is far below interactive-app norms.
- **Vendor lock-in**: lowest for Tesseract/PaddleOCR/Hugging Face, medium for Google/AWS/Azure OCR, highest for vision LLM extraction prompts because prompt behavior and schema-following quirks become part of the application.
- **EOL / product drift**: classic cloud OCR products are relatively stable. General-purpose vision models are more exposed to pricing, safety, and snapshot churn. Pinning model snapshots is mandatory.
- **Privacy / retention**: OpenAI is the clearest in docs: no training by default, 30-day abuse logs by default, optional ZDR approval, special handling for flagged images. Gemini Developer API free tier may use content to improve products; paid tier does not. Google Vision/AWS/Azure are better fits when the organization wants a conventional cloud OCR service instead of a frontier-model provider. Anthropic public developer docs in this pass were less explicit on retention than OpenAI’s, so that point needs a separate legal/privacy review before adoption.

## Recommendation matrix

| Backend | Accuracy on game UIs | Monthly cost at MVP volume | Container / ops footprint | Structured-output fit | Vendor lock-in / portability | Overall suitability for this task |
| --- | --- | --- | --- | --- | --- | --- |
| Tesseract | Low-Med; best on clean crops and digits | Free software | Low | Low | High portability | Useful baseline or fallback, weak as sole full-screen extractor |
| PaddleOCR | Med-High among OSS; still needs row logic | Free software | Med-High | Low | High portability | Strongest self-hosted OCR candidate if the team accepts heavier packaging |
| EasyOCR | Medium | Free software | Medium | Low | High portability | Good prototype path, less convincing long-term than PaddleOCR |
| docTR | Medium | Free software | High | Low | High portability | Technically capable, but not the most natural fit for stylized HUDs |
| Google Cloud Vision | Medium | `$0-$1.35` | Very low | Medium | Medium | Cheap, stable OCR API; still needs layout/row reconstruction |
| AWS Textract | Low-Med for HUDs; better on document-like panels | `$1.35` | Very low | Medium | Medium | Cost is fine, document bias is the main concern |
| Azure Read | Medium | `$0-$1.35` | Very low | Medium | Medium | Similar to Google Vision; viable hosted OCR baseline |
| Hugging Face TrOCR family | Med-High potential, but pipeline-dependent | Free software | High | Low | High portability | Flexible research path, not the shortest MVP path |
| OpenAI vision | High potential, but ambiguity can become hallucinated rows | `~$1.73-$5.76` | Very low | High | Medium-High | Strong one-shot extractor if paired with validation and model pinning |
| Anthropic vision | High potential, similar caveats to OpenAI | `~$1.88-$5.63` | Very low | High | Medium-High | Strong extractor, but still not deterministic OCR |
| Gemini vision | High potential, cheapest current vision-LLM option in this pass | `~$0.87` | Very low | High | Medium-High | Very attractive on price and schema support; still needs semantic validation |

