# Pricing Data for Pitch Deck

_As of April 16, 2026. All prices USD. Where a vendor did not expose checkout pricing publicly, that is noted explicitly._

## Competitor Pricing

| Bot | Free tier | Premium | Source |
|---|---|---|---|
| MEE6 | Free tier includes core moderation, leveling, embeds, and baseline automation. | Premium is per server. Monthly: $5.99/mo. Yearly: $24.99 for the first year ($2.08/mo shown), then $49.99/yr. Lifetime: $44.99. | [MEE6 Premium](https://mee6.xyz/en/premium) |
| Carl-bot | Free tier covers core moderation, automod, reaction roles, and logging. | Public pricing is server-count based rather than named Basic/Standard/Premium on accessible pages. 1 server: $7.99/mo. 2 servers: $12.99/mo. 3 servers: $16.99/mo. 5 servers: $24.99/mo. 8 servers: $35.99/mo. A public 2-server 1-year gift example is $129.39. | [Carl premium features](https://carl.gg/get-premium), [Patreon pricing update](https://www.patreon.com/posts/price-for-carl-131208404), [Patreon gift page](https://www.patreon.com/carlbot/gift) |
| Dyno | Free tier includes automod plus limited embeds, custom commands, autoresponders, giveaways, forms, and reaction roles. | Standard: $5.99/mo. Premium: $7.99/mo. Custom: $12.99/mo. Monthly pricing is public; yearly pricing was not exposed in the accessible scrape. | [Dyno Premium](https://dyno.gg/premium) |
| Arcane | Free tier includes leveling and base server management. | Premium: $7/mo or $75/yr. One premium subscription can be transferred between servers. | [Arcane Premium](https://arcane.bot/premium) |
| Ticket Tool | Standard plan is free. | Premium Monthly: $7.99/mo per server. Public premium page exposed monthly pricing and premium features; no public yearly or lifetime pricing was exposed on the accessible official page. | [Ticket Tool Premium](https://tickettool.xyz/premium) |
| Helper.gg | Free: $0/mo with unlimited tickets, panel replies, staff accounts, logs, embeds, and AI replies. | Premium: $4.90/mo. Supreme: $3.90/mo and listed as a Premium add-on, implying $8.80/mo for Premium + Supreme on one server. | [Helper.gg Pricing](https://helper.gg/pricing/) |
| Wick | Public pricing was not exposed on accessible `wickbot.com` premium pages. | A public `wicks.bot` pricing page lists Monthly: $5.99/mo and 3-Month Plan: $14.99, both per server. Treat this as a public reference point, but branding differs from `wickbot.com`. | [Wicks pricing](https://wicks.bot/en/pricing), [Wick premium landing](https://wickbot.com/premium) |
| Gather | Deprecated / historical only. | No accessible public pricing found. | [Top.gg Gather listing](https://top.gg/bot/868195275464900618) |
| Apollo | Free event-management tier available. | Premium: $5.99/mo or $49.99/yr ($4.17/mo effective). | [Apollo Premium](https://apollo.fyi/premium) |
| Raid-Helper | Free raid and event tooling is public. | No public premium pricing found on accessible official pages; premium flow appeared gated behind Discord login. | [Raid-Helper](https://raid-helper.xyz/) |

### Typical community bot-stack cost

Most mainstream premium Discord bots cluster around roughly $5.99-$7.99 per server per month. That puts a typical 3-bot stack at about $18-$24/mo and a typical 5-bot stack at about $30-$40/mo. If a community adds higher-end security or ticket add-ons such as Helper Premium + Supreme or Dyno Custom, total stack cost can push past $40-$50/mo. A clean investor-ready shorthand is **$20-$40/mo across 3-5 premium bots**. Sources: [MEE6](https://mee6.xyz/en/premium), [Dyno](https://dyno.gg/premium), [Arcane](https://arcane.bot/premium), [Ticket Tool](https://tickettool.xyz/premium), [Apollo](https://apollo.fyi/premium), [Helper.gg](https://helper.gg/pricing/).

## Vultr Infrastructure Costs

| Component | Spec | Monthly cost | Source |
|---|---|---|---|
| VKE control plane | Managed Kubernetes control plane | $0/mo | [VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost) |
| VKE worker cluster, lean | 3 x Regular Cloud Compute nodes, each 1 vCPU / 2 GB RAM / 55 GB SSD / 2 TB bandwidth | $30/mo total | [Vultr pricing](https://www.vultr.com/pricing/), [VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost) |
| VKE worker cluster, higher performance | 3 x High Performance nodes, each 1 vCPU / 2 GB RAM / 50 GB NVMe / 3 TB bandwidth | $36/mo total | [Vultr pricing](https://www.vultr.com/pricing/), [VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost) |
| Load balancer | 1 managed load balancer | $10/mo | [Vultr pricing](https://www.vultr.com/pricing/) |
| Block storage | Attached SSD volumes | $1 per 10 GB, or $0.10/GB-mo | [Vultr pricing](https://www.vultr.com/pricing/) |
| Object storage | 1 TB storage + 1 TB outbound transfer included | $18/mo base; extra storage $18/TB-mo; extra outbound $10/TB or $0.01/GB | [Vultr Object Storage](https://www.vultr.com/products/object-storage/) |
| Managed PostgreSQL, smallest single-node | Regular managed database, 1 GB RAM / 1 vCPU / 25 GB storage / 0 replicas | $15/mo | [Vultr pricing](https://www.vultr.com/pricing/) |
| Managed PostgreSQL, smallest HA-style option | Regular managed database, 2 GB RAM / 1 vCPU / 55 GB storage / 1 replica | $60/mo | [Vultr pricing](https://www.vultr.com/pricing/) |
| Bandwidth overage | Beyond included instance bandwidth | $0.01/GB | [Vultr pricing](https://www.vultr.com/pricing/) |

### Phase 0 minimum viable monthly cost

Direct platform floor, assuming VKE with 3 regular 2 GB nodes, one load balancer, and 50 GB block storage:

- Cluster: $30/mo
- Load balancer: $10/mo
- Block storage: ~$5/mo
- Total bare platform floor: **~$45/mo**

If Phase 0 also uses object storage and the smallest single-node managed PostgreSQL instance, the stack is:

- Bare platform floor: ~$45/mo
- Object storage: $18/mo
- Managed PostgreSQL: $15/mo
- Total with managed DB + object storage: **~$78/mo**

If Phase 0 assumes higher-performance nodes and a smallest HA-style managed PostgreSQL deployment, the stack is:

- Higher-performance 3-node cluster: $36/mo
- Load balancer: $10/mo
- Block storage: ~$5/mo
- Object storage: $18/mo
- Managed PostgreSQL with 1 replica: $60/mo
- Total: **~$129/mo**

For investor-deck purposes, the clean planning range is **~$80-$130/mo for Phase 0 hosted infrastructure**, with **~$45-$56/mo** as the absolute floor if object storage and managed database are deferred. The 3-node regular cluster above includes about **6 TB** of bundled instance bandwidth before overage; the 3-node high-performance variant includes about **9 TB**. Sources: [VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost), [Vultr pricing](https://www.vultr.com/pricing/), [Vultr Object Storage](https://www.vultr.com/products/object-storage/).

## OCR Pipeline Costs

### Google Cloud Vision `DOCUMENT_TEXT_DETECTION`

- Free tier: first **1,000 images/month**.
- Paid tier: **$1.50 per 1,000 images** from 1,001 to 5,000,000 images/month, then **$0.60 per 1,000 images** above 5,000,000.
- Effective standard per-image cost after the free tier: **$0.0015/image**.
- Source: [Google Cloud Vision pricing](https://cloud.google.com/vision/pricing)

### Gemini 3 Flash Preview (paid tier)

- Input: **$0.50 per 1M input tokens** for text, image, and video inputs.
- Output: **$3.00 per 1M output tokens** for text output.
- Practical OCR estimate for one screenshot: Gemini bills on tokens rather than file size. A reasonable planning assumption for a ~1 MB screenshot is one image at default/high image resolution, about **1,120 input tokens**, plus an OCR response of roughly **500-1,000 output tokens**.
- Estimated cost per fallback OCR call:
  - Input: 1,120 x $0.50 / 1,000,000 = **$0.00056**
  - Output: 500-1,000 x $3 / 1,000,000 = **$0.00150-$0.00300**
  - Total: **~$0.0021-$0.0036 per fallback call**
- Sources: [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Gemini 3 Flash model docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash), [Gemini 3 API docs](https://ai.google.dev/gemini-api/docs/gemini-3)

### Blended per-screenshot cost estimate

If every screenshot is first processed by Vision and only low-confidence cases fall back to Gemini, the blended cost is:

- Vision on 100% of screenshots: **$0.0015 each** after the free tier
- Gemini on 5% of screenshots: 5% x **$0.0021-$0.0036** = **$0.00010-$0.00018**
- Blended all-in OCR cost: **~$0.00160-$0.00168 per screenshot**

That means:

- 100,000 screenshots/month: **~$160-$168/mo**
- 200,000 screenshots/month: **~$320-$336/mo**

Sources: [Google Cloud Vision pricing](https://cloud.google.com/vision/pricing), [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Gemini 3 Flash model docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash)

## Seed Funding / Runway Benchmarks

- Typical seed round for an early startup still sits in a broad **$500k-$5M** range; Carta reports a **$3.5M median seed round in 2024**. Source: [Carta seed funding guide](https://carta.com/learn/startups/fundraising/seed-funding/)
- Typical Series A range remains about **$5M-$15M**; Carta reports a **$7.9M median Series A round in Q1 2025**. Source: [Carta Series A guide](https://carta.com/learn/startups/fundraising/series-a/)
- Standard runway target is still **18-24 months** per round. Source: [Carta seed funding guide](https://carta.com/learn/startups/fundraising/seed-funding/)
- Typical burn for a lean founding team is an inference rather than a published market constant. Using Kruze's 2025 benchmark of roughly **$147k annual seed-stage founder pay** plus **$80k-$125k annual seed-stage developer pay**, a 1-2 person team with light infra lands around **$15k-$30k/mo**, while a 3-person founding team plus infra lands around **$35k-$45k/mo**. Sources: [Kruze founder salary benchmarks](https://kruzeconsulting.com/do-founders-of-startups-that-have-raised-millions-give-themselves-paychecks-if-so-how-much-money-do-they-pay-themselves/), [Kruze startup wage benchmarks](https://kruzeconsulting.com/startup-wages-seriesa/)
- Open-source sponsorship tiers cluster in familiar bands: **$5-$10/mo** individual backer tiers, **$25-$50/mo** supporter tiers, and **$100-$150+/mo** sponsor tiers. Sources: [GitHub Sponsors docs](https://docs.github.com/en/sponsors/receiving-sponsorships-through-github-sponsors/managing-your-sponsorship-tiers), [Martin Costello Sponsors](https://github.com/sponsors/martincostello), [Josh Beckman Sponsors](https://github.com/sponsors/joshbeckman), [Open Collective V2](https://blog.opencollective.com/open-collective-v2-is-live/), [psutil on Open Collective](https://opencollective.com/psutil)

## Synthesis for Pitch Deck

Ready-to-plug figures for the pitch deck placeholders:

- **MEE6 Premium per-server:** $5.99/mo monthly, $24.99 first-year annual, $44.99 lifetime. Source: [MEE6 Premium](https://mee6.xyz/en/premium)
- **Ticket Tool Premium:** $7.99/mo per server. Source: [Ticket Tool Premium](https://tickettool.xyz/premium)
- **Typical community bot-stack cost:** **$20-$40/mo across 3-5 premium bots**, with heavier custom/security stacks running higher. Sources: [MEE6](https://mee6.xyz/en/premium), [Dyno](https://dyno.gg/premium), [Arcane](https://arcane.bot/premium), [Ticket Tool](https://tickettool.xyz/premium), [Apollo](https://apollo.fyi/premium), [Helper.gg](https://helper.gg/pricing/)
- **Vultr VKE Phase 0 monthly:** **~$80-$130/mo** for a realistic Phase 0 stack with VKE, load balancer, block storage, object storage, and managed PostgreSQL; **~$45-$56/mo** is the bare infrastructure floor before managed DB/object storage. Sources: [VKE cost doc](https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost), [Vultr pricing](https://www.vultr.com/pricing/), [Vultr Object Storage](https://www.vultr.com/products/object-storage/)
- **Google Vision monthly example:** at **2,000 screenshots/community/month x 100 communities = 200,000 screenshots/month**, Vision alone is about **$299/mo** after the first 1,000 free images. Source: [Google Cloud Vision pricing](https://cloud.google.com/vision/pricing)
- **Gemini fallback monthly example:** at the same volume, **5% fallback = 10,000 Gemini calls/month**, or about **$21-$36/mo**. Sources: [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), [Gemini 3 Flash model docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash)
- **Blended OCR monthly example:** at 200,000 screenshots/month, total OCR cost is about **$320-$336/mo**. Sources: [Google Cloud Vision pricing](https://cloud.google.com/vision/pricing), [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- **Suggested seed raise range:** **$1.5M-$3.5M**. This is an inferred recommendation: it sits inside Carta's broader seed market range and near the recent median while staying appropriate for a lean pre-product developer-tool/community-platform company. Source benchmark: [Carta seed funding guide](https://carta.com/learn/startups/fundraising/seed-funding/)
- **Target runway:** **18-24 months**. Source: [Carta seed funding guide](https://carta.com/learn/startups/fundraising/seed-funding/)
- **Implied burn:** **$15k-$30k/mo** for a 1-2 person lean build, or **$35k-$45k/mo** for a 3-person founding team including infra. This is an inference from Kruze compensation benchmarks rather than a direct market quote. Sources: [Kruze founder salary benchmarks](https://kruzeconsulting.com/do-founders-of-startups-that-have-raised-millions-give-themselves-paychecks-if-so-how-much-money-do-they-pay-themselves/), [Kruze startup wage benchmarks](https://kruzeconsulting.com/startup-wages-seriesa/)
- **Open-source sponsor tier range:** **$5-$10/mo** individual, **$25-$50/mo** supporter, **$100-$150+/mo** organizational sponsor. Sources: [GitHub Sponsors docs](https://docs.github.com/en/sponsors/receiving-sponsorships-through-github-sponsors/managing-your-sponsorship-tiers), [Martin Costello Sponsors](https://github.com/sponsors/martincostello), [Josh Beckman Sponsors](https://github.com/sponsors/joshbeckman), [Open Collective V2](https://blog.opencollective.com/open-collective-v2-is-live/), [psutil on Open Collective](https://opencollective.com/psutil)
