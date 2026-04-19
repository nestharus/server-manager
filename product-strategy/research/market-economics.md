# Market Economics for Investor Pitch Deck

Method note:

- `Measured` = directly disclosed by a public source.
- `Estimated` = arithmetic applied to public pricing/usage figures.
- `Inferred` = judgment call built from public signals where no exact count is disclosed.
- Exact counts for "serious gaming guilds with 50-500 members" are not public. That part of the model is therefore a bottoms-up estimate, not a Discord-reported metric.

## 1. Market Cap / TAM

### Discord bot industry

Key ecosystem scale:

- `Measured:` Discord says it is used by [200 million people every month](https://discord.com/blog/discords-next-chapter) and had [90M+ daily active users in Q4 2025](https://discord.com/company).
- `Measured:` Discord says [90%+ of users play video games](https://discord.com/company), which is important because the product wedge here starts in gaming guild operations.
- `Measured, but dated:` CNBC reported in May 2021 that Discord had [19 million weekly active servers](https://www.cnbc.com/2021/05/08/what-is-discord-chat-service-fosters-community-expands-beyond-gaming.html), which is still the closest public server-count disclosure I could trace.
- `Measured:` Discord says [thousands of creators have started earning on Discord and Discord has paid out millions of dollars to thousands of creators and communities](https://discord.com/blog/server-subscriptions-updates-media-channels-tier-templates-and-more), but it does not publish an exact count of monetized or premium servers.

Public scale of major bots:

| Bot / category signal | Public scale | Pricing signal |
|---|---:|---:|
| [MEE6](https://www.scaleway.com/en/customer-testimonials/mee6/) | 21M servers | [Promo pricing page](https://mee6.xyz/en/pro) shows $3.49/mo intro monthly, $1.99/mo annual equivalent, and $42.49 lifetime as of 2026-04-17 |
| [Dyno](https://dyno.gg/) | 11.3M servers | [Standard $5.99/mo, Premium $7.99/mo](https://dyno.gg/premium) |
| [Carl-bot](https://carl.gg/) | 14.1M servers | [$5/mo or $50/yr](https://carl.gg/get-premium) |
| [Ticket Tool](https://tickettool.xyz/) | 5.37M servers | [$9.99/mo or $99.99/yr](https://tickettool.xyz/billing) |
| [Top.gg largest list](https://top.gg/list/largest) | MEE6 19.5M, Dyno 11.3M, Ticket Tool 5.37M, Dank Memer 8.63M | Confirms moderation, ticketing, and engagement bots all operate at multi-million-server scale |

Category-level takeaways:

- `Moderation / admin automation:` the largest category by visible scale. MEE6, Dyno, and Carl-bot each sit in the 11M-21M server range. That is strong evidence that server-ops tooling is a real software category on Discord, not a hobby edge case.
- `Engagement / economy:` MEE6 and Dank Memer both show very large install bases on [Top.gg](https://top.gg/list/largest), which matters because many servers already budget for engagement tooling.
- `Applications / ticketing:` Ticket Tool alone is in [5.37M servers](https://top.gg/list/largest). This is the closest public comp to a support/applications workflow wedge.
- `Gaming guild management:` no standalone vendor publishes anything close to moderation-bot scale, which implies the niche is smaller but not zero; pricing data below shows it is still monetizable.

Public revenue disclosures:

- `Measured:` MEE6 was described by IBTimes as a [“multimillion-dollar business” with 45 employees, 21M servers, and 300M users](https://www.ibtimes.co.uk/bootstrapping-global-scale-how-two-founders-built-multimillion-dollar-business-without-external-1729456). I did not find a public exact ARR number.
- `Not publicly disclosed:` I did not find public ARR disclosures for Dyno, Carl-bot, or Ticket Tool.
- `Estimated:` a paid-bot software ceiling TAM can be framed as `19M weekly active servers x 1 paid bot x $5-$10/mo`, or roughly `$1.14B-$2.28B annualized`. This is an upper-bound software spend ceiling, not a realistic near-term revenue pool, because many servers stay on free tiers.

### Guild management tool market

Direct and adjacent market signals:

- `Measured:` Discord's own [Guilds FAQ](https://support.discord.com/hc/en-us/articles/23187611406999-Guilds-FAQ) defines a guild as a "small, exclusive server where people who regularly play games together collaborate, compete, and hang out." That is almost exactly the wedge this product targets.
- `Measured:` Discord's [Server Insights FAQ](https://support.discord.com/hc/en-us/articles/360032807371-Server-Insights-FAQ) uses `500+ members` as the threshold for more advanced community analytics. That suggests 50-500 member groups are already large enough to create operational overhead, even before they qualify for Discord's larger-community tooling.
- `Measured:` [Guild Manager](https://guildmanager.app/pricing), a current multi-game guild-management product, prices at `$19.99/mo` for up to 300 members, `$29.99/mo` for up to 600, and `$49.99/mo` for unlimited.
- `Measured:` legacy guild-hosting products also showed willingness to pay before Discord-native SaaS became common:
  - [Shivtr](https://shivtr.com/plans): `$5/$10/$15` monthly tiers.
  - [Gamer Launch](https://www.gamerlaunch.com/order/d/comparison/): `$7.49/$15.99/$23.99` monthly tiers.
- `Measured:` Roblox disclosed in its SEC filing that the [Guilded acquisition carried $77.6M in consideration](https://www.sec.gov/Archives/edgar/data/1315098/000131509821000033/rblx-20210930.htm). That is not a market-size number, but it is strong evidence that gaming-community infrastructure has strategic value.
- `Measured:` Discord said in late 2025 that there were [over 10,000 game communities on Discord with more than 80 million members](https://discord.com/press-releases/discord-deepens-its-ability-to-drive-growth-for-games). I read this as an official lower-bound signal for game-centric communities, not as a count of all gaming guilds on Discord.

Adjacent TAM:

- `Measured:` Goldman Sachs sized the [creator economy at $250B and projected $480B by 2027](https://www.goldmansachs.com/insights/articles/the-creator-economy-could-approach-half-a-trillion-dollars-by-2027?query=landing+page&src=blog-guestpost-nate).
- `Measured:` broader community platforms price much higher than Discord bots:
  - [Circle](https://circle.so/pricing): `$89/mo` Professional, `$199/mo` Business.
  - [Mighty Networks](https://www.mightynetworks.com/pricing): `$79/mo` Launch, `$179/mo` Scale.
  - [Slack](https://slack.com/pricing): `$8.75/user/mo` Pro, `$18/user/mo` Business+.
  - [Notion](https://www.notion.com/pricing): `$10/user/mo` Plus, `$20/user/mo` Business.

Interpretation:

- Pure "gaming guild ops" is a real spend category, but it is much smaller than the total Discord-bot ecosystem.
- The strategically interesting version of this company is not "yet another bot." It is "the operating system for admin-heavy Discord communities," starting with gaming guilds and expanding into creator, fandom, and private-community operations.

### Bottoms-up SAM calculation

Working assumptions:

| Input | Value | Type | Basis |
|---|---:|---|---|
| Weekly active Discord servers | 19.0M | Measured | [CNBC citing Discord](https://www.cnbc.com/2021/05/08/what-is-discord-chat-service-fosters-community-expands-beyond-gaming.html) |
| Users who play games | 90%+ | Measured | [Discord company page](https://discord.com/company) |
| Serious gaming guild share of active servers | 1.0%-3.0% | Inferred | Conservative low-single-digit subset of all active servers; anchored by Discord's gaming skew, the [Guilds FAQ](https://support.discord.com/hc/en-us/articles/23187611406999-Guilds-FAQ), the [500-member Server Insights threshold](https://support.discord.com/hc/en-us/articles/360032807371-Server-Insights-FAQ), and the fact that serious guilds are only a slice of all casual/friend/creator servers |
| Addressable guild count | 190k-570k | Estimated | `19.0M x 1%-3%` |
| Midpoint guild count | 427.5k | Estimated | `19.0M x 2.25%` |
| Annual WTP per guild | $240-$480 | Estimated | Equivalent to roughly `3-5 bots x $5-$10/mo`, cross-checked against [Dyno](https://dyno.gg/premium), [Carl-bot](https://carl.gg/get-premium), [Ticket Tool](https://tickettool.xyz/billing), and [Guild Manager](https://guildmanager.app/pricing) |
| Midpoint annual WTP | $360 | Estimated | Midpoint of the pricing band |

SAM outputs:

- `Low case:` `190,000 guilds x $240/year = $45.6M`
- `Base case:` `427,500 guilds x $360/year = $153.9M`
- `High case:` `570,000 guilds x $480/year = $273.6M`

Recommended investor-deck number:

- `SAM (guild-management wedge): ~$150M ARR-equivalent software spend`

Why this is the right framing:

- It is conservative enough to avoid pretending every Discord server is a buyer.
- It still leaves room for a solid SaaS business.
- It also shows why the company probably needs to expand from "gaming guild ops" into broader community operations if the goal is classic VC-scale outcomes.

## 2. Revenue Model and ROI

### Pricing benchmarks

Current pricing benchmarks as of 2026-04-17:

| Product | Current benchmark pricing | What it implies |
|---|---|---|
| [Dyno](https://dyno.gg/premium) | $5.99-$12.99/mo | Mature utility-bot pricing band starts around $6/mo |
| [Carl-bot](https://carl.gg/get-premium) | $5/mo or $50/yr | Large moderation bots can monetize at low single-digit monthly price points |
| [Ticket Tool](https://tickettool.xyz/billing) | $9.99/mo or $99.99/yr | Specialized workflow bots can charge near $10/mo |
| [Guild Manager](https://guildmanager.app/pricing) | $19.99-$49.99/mo | Purpose-built guild software supports meaningfully higher pricing than generic bots |
| [Circle](https://circle.so/pricing) | $89-$199/mo | Broader community operating systems price much higher than bots |
| [Mighty Networks](https://www.mightynetworks.com/pricing) | $79-$179/mo | Community platform pricing supports premium tiers once the product expands beyond utility tooling |
| [Slack](https://slack.com/pricing) | $8.75-$18/user/mo | Teams already accept seat-based pricing for collaboration ops |
| [Notion](https://www.notion.com/pricing) | $10-$20/user/mo | Admin tooling can credibly move beyond per-server pricing over time |

Pricing conclusion:

- `Bot-only wedge:` `$5-$10/server/mo`
- `Guild-ops wedge:` `$20-$50/server/mo`
- `Broader multi-admin community OS:` `$79+/mo` becomes credible only after the product expands beyond a bot replacement

Recommended pricing architecture:

- `Individual guild:` `$29/mo`
- `Multi-chapter org / esports org / alliance:` `$79/mo`
- `Design partner tier:` `$50/mo` only if it includes white-glove onboarding, migration, and prioritized support

### Plausible ARR trajectory

Observed market precedent:

- Category leaders are already massive: [MEE6 21M servers](https://www.scaleway.com/en/customer-testimonials/mee6/), [Carl-bot 14.1M](https://carl.gg/), [Dyno 11.3M](https://dyno.gg/), [Ticket Tool 5.37M](https://tickettool.xyz/).
- That means the constraint is not "does Discord have enough guilds?" The constraint is product quality, trust, distribution, and whether the workflow replaces enough paid bots to justify a consolidated bill.

Monetization-path comparison:

| Model | Good | Bad | Verdict |
|---|---|---|---|
| Per-server subscription | Matches how Discord admins already buy tools; easiest to explain | Caps upside on larger orgs | Best default launch model |
| Design partner / VIP early access | Can start at $50/mo+ with setup help | High-touch; hard to scale | Good for first 20-100 customers |
| Open-source core + hosted SaaS | Good credibility and adoption; mirrors the existence of [open-source/self-hosted ticket alternatives](https://github.com/discord-tickets/bot) | Usually slows near-term ARR unless hosting/admin UX is clearly superior | Attractive only if GTM needs trust and self-hosting distribution |
| Take-rate monetization | MEE6 shows a [5% subscription fee](https://mee6.xyz/en/memberships) can work | Depends on customer monetization, not ops pain | Useful add-on later, not core pricing today |

Plausible trajectory:

| Year | Paying guilds | Blended price | ARR | Read |
|---|---:|---:|---:|---|
| Year 1 | 50-100 | $20-$50/mo | $12k-$60k | Realistic for MVP + founder-led sales; 100 true design partners is possible but aggressive without pre-existing distribution |
| Year 2 | 300-800 | $20-$25/mo | $72k-$240k | Achievable if the product clearly replaces multiple bots and wins a repeatable guild-admin use case |
| Year 3 | 1,000-2,000 | $30/mo blended | $360k-$720k | Plausible if the company expands from single guilds into larger orgs and multi-chapter communities |

The scenarios you proposed are internally consistent:

- `100 design-partner guilds x $50/mo = $60k ARR`
- `500 guilds x $20/mo = $120k ARR`
- `2,000 guilds x $30/mo = $720k ARR`

Those are not category-stretch goals. They are tiny relative to the install footprint of existing Discord tooling. They are, however, ambitious on GTM for a solo founder without current design partners.

## 3. Equity Ask and Dilution

### Seed-stage benchmarks

Fundraising benchmark summary:

- `Measured:` [90% of pre-seed rounds on Carta in Q1 2025 were SAFEs](https://carta.com/learn/startups/fundraising/convertible-securities/pre-money-vs-post-money-safes/).
- `Measured:` Carta's 2025 pre-seed benchmarks show median post-money SAFE caps of:
  - [`$7.5M` for rounds under $250k](https://carta.com/data/state-of-pre-seed-q2-2025/)
  - [`$10M` for rounds from $250k to $1M](https://carta.com/data/state-of-pre-seed-2025/)
  - [`$15M` for rounds from $1M to $2.5M](https://carta.com/data/state-of-pre-seed-2025/)
- `Measured:` Carta's [Q1 2025 private markets report](https://carta.com/data/state-of-private-markets-q1-2025/) put the median pre-money valuation for new seed rounds at `$16M`.
- `Measured:` [Post-money SAFEs were ~83%-87% of all SAFEs](https://kruzeconsulting.com/blog/preseed-funding/), and [only about 30% of SAFEs included both a cap and a discount](https://kruzeconsulting.com/blog/preseed-funding/). In other words: cap-only SAFEs dominate.
- `Measured / benchmark:` Typical SAFE discounts, when present, are [15%-20% according to Kruze](https://kruzeconsulting.com/blog/safe-notes/) and [typically 20% according to OpenVC](https://www.openvc.app/blog/safe).
- `Measured / benchmark:` Typical first priced-round dilution is [15%-25%](https://www.rebelfund.vc/blog-posts/founder-dilution-benchmarks-seed-2025-stay-under-18-percent), with [19% cited as a 2025 median](https://www.rebelfund.vc/blog-posts/founder-dilution-benchmarks-seed-2025-stay-under-18-percent).

### Valuation math for this project

Runway math from current burn:

- Current burn: `$9,500/mo`
- `18 months runway = $171,000`
- `24 months runway = $228,000`

That is the absolute minimum capital requirement, not a realistic fundraising target. A real round also needs buffer for:

- incorporation/legal/accounting costs,
- cloud and tooling,
- travel / customer development,
- some contractor or part-time design / frontend help.

Recommended raise size:

- `Recommended range: $300k-$500k`
- Why: it covers 18-24 months of solo runway plus some operating slack, without forcing the company into a team build before the wedge is validated.

Implied valuation math at typical priced-round dilution:

| Raise | Dilution | Implied pre-money | Implied post-money |
|---:|---:|---:|---:|
| $300k | 15% | $1.70M | $2.00M |
| $300k | 20% | $1.20M | $1.50M |
| $500k | 15% | $2.83M | $3.33M |
| $500k | 20% | $2.00M | $2.50M |
| $500k | 25% | $1.50M | $2.00M |

Interpretation:

- For a `solo, pre-product, no-design-partner` founder, a priced-equity round at `$1.5M-$3.0M` pre-money is mathematically consistent with a small $300k-$500k raise and 15%-25% dilution.
- But that is `below` the 2025 institutional pre-seed SAFE market on Carta, where `$7.5M-$10M` post-money caps were more typical even for smaller rounds.
- The practical conclusion is:
  - `Angel / friends-and-family priced round:` `$1.5M-$3M` pre-money can happen.
  - `Institutional pre-seed SAFE:` more likely to be framed as a `$7.5M-$10M` post-money cap, but only if the founder can sell the market wedge and product vision despite limited traction.

My valuation read for this project:

- `Realistic solo pre-product pricing-equity equivalent:` `$4M-$8M pre-money` is the defensible zone if there is a credible deck and sharp wedge story.
- `Below $4M` starts to look like a desperation raise.
- `Above $8M` is hard to justify without stronger evidence than exists today.

## 4. Team Expansion Economics

### Salary benchmarks

Role benchmarks:

- `Senior software engineer / founding UI engineer`
  - [Pave](https://www.pave.com/blog-posts/how-much-comp-should-the-first-engineer-get): `$187k-$250k` cash, `0.33%-1.32%` equity.
  - [TopStartups examples](https://topstartups.io/startup-salary-equity-database/?title=Senior%20software%20engineer): `$200k`, `$216k`, `$224k` with `0.02%-0.44%` equity examples.
- `Product / technical product partner`
  - [Carta](https://carta.com/data/startup-compensation-h1-2025/): average new-hire product salary `~$189k`.
  - [TopStartups PM examples](https://topstartups.io/startup-salary-equity-database/?title=Product%20manager): `$200k-$255k`, `0.08%-0.2%` equity examples.
  - [Pave](https://www.pave.com/blog-posts/who-to-hire-first-the-data-behind-team-building): first product hire is typically `employee #8`, which argues strongly against hiring this role too early.
- `Marketing / growth hire`
  - [TopStartups marketing examples](https://topstartups.io/startup-salary-equity-database/?title=Marketing%20manager): `$137k-$200k`, `0.002%-0.14%` equity examples.
  - `Inference:` first true marketing hire usually comes after repeatable acquisition is visible, not before.

Equity grants for employees 1-5:

- `Founding engineer:` `0.33%-1.32%` from [Pave](https://www.pave.com/blog-posts/how-much-comp-should-the-first-engineer-get); [Index Ventures](https://www.indexventures.com/rewarding-talent/allocation-considerations-and-benchmarks) puts a seed-stage senior engineer at `~1.0%`.
- `Mid-level early engineer:` [Index](https://www.indexventures.com/rewarding-talent/allocation-considerations-and-benchmarks) suggests `~0.45%`.
- `Product / marketing early hires:` public startup-offer examples cluster much lower, roughly `0.01%-0.2%`, unless the role is genuinely founding-level.
- `Company-level option pool:` [Index Ventures](https://www.indexventures.com/rewarding-talent/allocation-considerations-and-benchmarks) recommends `10%-20%` at seed.

### Team expansion thresholds

Cash cost reality:

- A true market-rate US early hire is more expensive than the placeholder assumptions in the prompt.
- Rough monthly cash equivalents before benefits/payroll load:
  - senior UI engineer: `$15.5k-$20.8k/mo`
  - product partner: `$15.8k-$21.3k/mo`
  - marketing hire: `$11.4k-$16.7k/mo`

That implies a 4-person team is more like:

- founder burn `$9.5k/mo`
- plus UI engineer `$16k-$21k/mo`
- plus product partner `$16k-$21k/mo`
- plus marketing `$11k-$17k/mo`
- `Result: roughly $52.5k-$68.5k/mo before extra cloud/software spend`

Decision rule:

- `Do not hire full-time product before the company reaches product pull.` Pave's benchmark that first product hires tend to be employee `#8` is a useful warning sign here.
- `Do not hire marketing before a repeatable acquisition loop exists.` Otherwise the company just increases burn without improving learning speed.

Practical thresholds:

- `Inferred:` these MRR gates are operator heuristics derived from the salary benchmarks above and the modeled ARR scenarios below; they are not externally published benchmark lines.

| Hire | Better reason to hire | Minimum sensible MRR |
|---|---|---:|
| UI engineer | Product scope is blocked by frontend quality / speed | `$15k-$25k MRR` |
| Product partner | The founder is bandwidth-constrained by cross-functional coordination, not by core product uncertainty | `$25k-$40k MRR` |
| Marketing hire | Acquisition loop is already working and needs scale, not discovery | `$35k-$50k MRR` |
| Full 4-person team | Product, support, and acquisition all justify specialization | `$60k-$75k MRR` |

Why those thresholds:

- A `$50k-$60k/mo` team burn implies `$600k-$720k` annual burn.
- That maps closely to your `2,000 guilds x $30/mo = $720k ARR` scenario.
- In other words: a 4-person team becomes rational only when the business is already approaching the upper end of the 3-year base case.

### Market-cap feasibility check

Using the base-case SAM above:

- `Base-case SAM:` `$153.9M`
- `ARR needed to support a lean 4-person team:` `$600k-$720k`
- `Share of SAM needed to support that team:` `0.39%-0.47%`

That is actually feasible.

- Supporting a small, focused 4-person team does `not` require heroic market share.
- Reaching `~2,000 guilds` in 2-3 years would be enough to justify a small team if the product and retention are strong.

What is harder:

- A classic VC outcome on the pure guild-management wedge alone.
- `$10M ARR` would require roughly `4.9%-9.8%` of the modeled SAM, depending on which SAM case you use.
- That is possible only if the company expands beyond "gaming guild management" into a wider admin-heavy Discord/community operating system.

Verdict:

- `Pure guild-management wedge:` attractive small SaaS / sustainable company.
- `Guild-management wedge + broader community-ops expansion:` can justify venture-style upside.
- Best label for the pitch today: `hybrid`.

## Synthesis for Pitch Deck

Ready-to-plug numbers for the investor pitch deck:

- **TAM (Discord bot software ceiling):** `$1.1B-$2.3B`
- **SAM (guild management specifically):** `~$150M` base case, with a `$46M-$274M` modeled range
- **SOM (realistic 3-year capture):** `~$720k ARR` at `2,000 guilds`, equal to about `0.47%` of base-case SAM
- **Target pricing tier:** `$29/mo` individual guild, `$79/mo` multi-chapter org
- **Year-1 ARR target (realistic):** `$25k-$60k`
- **Year-3 ARR target (realistic):** `$360k-$720k`
- **Recommended raise size (given burn + runway):** `$300k-$500k`
- **Implied pre-money valuation at seed / pre-seed:** `$4M-$8M` realistic target; `$7.5M-$10M` post-money SAFE cap is the closest institutional pre-seed market benchmark
- **Typical dilution at this raise size:** `15%-25%` for a priced round; materially less if raised on a higher-cap SAFE
- **Minimum MRR to justify team expansion:** `~$60k MRR` for a full 4-person build; earlier hires only make sense in the `$15k-$50k MRR` band depending on role
- **Market-cap feasibility verdict:** `Hybrid` — the gaming-guild wedge can support a solid business and a small team, but true VC-scale returns likely require expanding into broader Discord/community operations
