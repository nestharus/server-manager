# Application & Intake Bots — Research Findings

Researched on April 16, 2026. Scope: Discord-native application bots, external form stacks commonly paired with Discord, and dashboard-based review tooling.

The market splits into three buckets:
- Discord-native bots that keep submission and reviewer notifications inside Discord, but usually stop at `pending -> accept/deny/archive`.
- Discord-connected dashboards that improve moderation UX, but still lack rigorous reviewer ownership, auditability, and versioned contracts.
- External form products plus automation layers like Zapier, which offer stronger form builders than most Discord bots but weak Discord-native adjudication.

## Gather

### Application Workflow
- Forms are managed on the website and can be used in Discord through `/apply`. Gather documents explicit submission states: `Draft`, `Submitted`, `Approved`, `Rejected`, and `Cancelled`. It also gives applicants revocation rights after submission. Reviewer and reviewer-only comment channels exist on each submission.
- Gather is the only tool in this set that explicitly says each submission stores a snapshot of the form as it existed when submitted, so later template edits do not rewrite old applications.
- Gather can notify applicants about status changes and can automatically join approved users to the community and grant roles.

### Form Capabilities
- Official docs describe text inputs with min/max/pattern validation, single- or multi-select options, identity fields for Discord/Steam/Blizzard/Xbox, datetime, weekly availability, timezone offset, and checkbox elements.
- Its Top.gg listing also advertises file inputs and calls out eight question types total.

### Review Features
- Review happens on the website, with labels for filtering submissions and a permissions model separate from raw Discord role permissions.
- Gather can create a private interview text channel for the applicant and admins.
- Inference from docs: there is no explicit reviewer claim/lock mechanism or single-owner queueing model.

### Decision Tracking
- State transitions are explicit and user-visible. Reviewer/public-private comment channels and form snapshots are stronger than most competitors.
- Inference from docs: there is still no published appeal workflow, required decision rationale, or reviewer-collision prevention.

### Pricing
- The official site says most functionality is free and that Premium existed for extra perks, but the product is now deprecated and no current public pricing is surfaced.

### Limitations & User Complaints
- The official landing page now says Gather is deprecated, no longer actively maintained, and should not be used where active development or service guarantees are required.
- Public review surface is thin and stale. Top.gg only shows seven reviews, all positive but all from roughly four years ago, which weakens confidence in current product fit despite its unusually strong form-version snapshot model.

### Sources
- https://gather.sh/
- https://gather.sh/help/guides/01EGTP9PDS04BYYGFX1TYMKMBY
- https://gather.sh/help/guides/01EGTAK8MEABMM7V358FD7JKWY
- https://top.gg/bot/868195275464900618

## Appy

### Application Workflow
- Appy forms are configured in a web dashboard. Applications are submitted into a logging channel, then staff can accept or deny them. Users can apply via panels and `/apply <applicationName>`.
- Each application can be enabled/disabled, rate-limited with cooldowns, and configured to auto-deny if a user leaves the server while their application is pending.

### Form Capabilities
- Appy’s public docs describe two question types: ordinary text questions and multiple-choice questions.
- Form-level settings include logging channel, completion/accepted/denied messages, restricted roles, required roles, accept/deny role assignment and removal, ping roles, and staff threads.
- Premium expands this materially: up to 100 questions per application, unlimited applications/panels/roles, manager roles, custom cooldowns, and full panel customization.
- Inference from current docs and pricing page: Appy does not expose first-class form versioning for in-flight submissions.

### Review Features
- Reviewers work from the dashboard and Discord logging output. Staff threads let reviewers discuss an application without cluttering the main log message.
- Premium adds custom application manager roles and history/insights; Top.gg also advertises CSV export.
- Inference from docs: Appy has role-based review permissions, not per-application claim ownership or collision locks.

### Decision Tracking
- Appy supports accept/deny outcomes, customizable decision messages, role changes on decision, application history/insights, and user-leave handling.
- Inference from docs: it does not publish required decision reasons, waitlist handling, or an appeal workflow.

### Pricing
- Free plan exists.
- Premium x1 is `£4.99/month` for one server.
- Premium x3 is `£8.99/month` for up to three servers.
- Custom Bot is `£9.99/month`.

### Limitations & User Complaints
- Appy documents a hard Discord embed limit problem: if an application exceeds 6,000 embed characters, staff must open it on the dashboard instead of reviewing it in Discord.
- Appy’s own troubleshooting also shows a DM dependency: if the applicant has DMs closed or has blocked the bot, the form cannot be delivered.
- The dashboard permission model can force an awkward tradeoff: staff either need elevated `Manage Server` access or a premium manager-role feature to reliably view certain large applications.
- Inference from public review surfaces: sentiment is broadly positive, but the best-documented operational pain points come from Appy’s own troubleshooting docs rather than from mature review/assignment features.

### Sources
- https://appy.bot/
- https://docs.appy.bot/getting-started/set-up/applications-forms
- https://docs.appy.bot/getting-started/applications/settings
- https://docs.appy.bot/resources/troubleshooting/large-applications
- https://docs.appy.bot/resources/troubleshooting/closed-dms
- https://appy.bot/premium
- https://top.gg/bot/853327905357561948

## Application Bot

### Application Workflow
- Application Bot puts the application itself in Discord DMs and pushes moderation into a web dashboard.
- Moderators review and accept/reject from the dashboard. Approved and rejected applications can be kept in an application archive.
- It also supports interview channels that are automatically created and visible only to the applicant and a specified role.

### Form Capabilities
- Official marketing promises unlimited applications, unlimited applicants, unlimited questions, and multiple question types.
- The dashboard is positioned as the primary place to customize the system.
- Inference from docs: the product does not publish explicit form version snapshots, branching logic, or richer intake-state modeling beyond submit/review/accept/reject/archive.

### Review Features
- Review permissions are customizable and moderators work from a web dashboard.
- Interview channels are the clearest differentiator versus simpler application bots.
- Inference from docs: there is no published claim/assignment feature to stop two reviewers acting on the same application.

### Decision Tracking
- The documented workflow is mostly `submitted -> accept/reject -> archive`.
- Inference from docs and reviews: no required reasons, appeal handling, waitlist state, or auditable transition ledger are publicly documented.

### Pricing
- Premium is `£2.99/month` or `£17.99/year`.
- Premium feature list includes unlimited applications, unlimited applicants, multiple question types, application archive, and interview channels.

### Limitations & User Complaints
- This tool has the weakest review sentiment of the Discord-native bots reviewed here: Top.gg shows a `3.44` rating from `231` reviews.
- Public complaints repeatedly mention dashboard confusion, not being able to find the dashboard, servers not appearing in the dashboard, and paying for Pro/Premium without being able to use the gated features.
- This is a practical warning sign for Humility: even when the underlying model is serviceable, the operator UX appears brittle.

### Sources
- https://application-bot.com/
- https://fusiondiscordbots.com/premium
- https://top.gg/bot/418842777720193037

## ApplicationForms

### Application Workflow
- ApplicationForms combines a Discord bot with a dashboard. Moderators create forms on the dashboard, share them with `/shareform`, receive submissions in Discord, and then manage responses in the dashboard.
- Applicants can view their own submissions with `/myapplications`.
- Public workflow states are thin: submissions are active or archived, and archived responses can be restored.

### Form Capabilities
- The dashboard supports title, description, image banner URL, multiple-submission control with a six-hour cooldown, response channel, and open/closed status.
- Available field types are `Short Text`, `Long Text`, `Select (radio options)`, and `Checkbox (multiple options)`.
- Inference from docs: there is no published branching, no form snapshot/version history, and no file/image upload field.

### Review Features
- Moderators can browse all submissions in one place, archive/unarchive them, and report troll submissions.
- The dashboard centralizes submission data and settings cleanly for small teams.
- Inference from docs: there is no reviewer assignment, claim lock, prior-application context, or private interview-thread/channel support.

### Decision Tracking
- Public documentation emphasizes archive/unarchive rather than accept/deny or richer adjudication states.
- Inference from docs: there is no documented decision reason requirement, appeals flow, or structured audit trail.

### Pricing
- Premium exists. The public shop lists `ApplicationBot Premium [1 Month]` at `€4.49`.
- The public product page does not expose a detailed premium feature matrix, only generic references to premium activation.

### Limitations & User Complaints
- Compared with Appy, Gather, and Application Bot, ApplicationForms is much narrower on field types and reviewer workflow sophistication.
- The strongest gap is not UI polish but adjudication depth: public docs show storage and archiving, not queue ownership or decision-process rigor.

### Sources
- https://purplect.xyz/bot/applicationforms
- https://discord.com/discovery/applications/948949340842512397
- https://shop.purplect.xyz/

## Google Forms + Discord Automation

### Application Workflow
- This is not a Discord-native application system. The usual pattern is: publish a Google Form, collect responses in Forms/Sheets, then use Zapier or Apps Script/webhooks to notify Discord or assign roles.
- Google Forms supports publish/share controls, limiting to one response, editable responses, prefilled links, and collaborator analysis in Sheets.
- Zapier templates commonly used with Discord include posting new responses to a channel, DMing users, and assigning roles from form responses.

### Form Capabilities
- Google Forms supports short answer, paragraph, multiple choice, checkboxes, dropdown, file upload, linear scale, rating, grids, date, and time questions.
- It also supports section-based branching, but only from multiple-choice and dropdown questions.
- File upload questions can restrict file type, count, and size, but responders must sign in to a Google Account and uploaded files go to the owner’s Drive.

### Review Features
- Review is fundamentally manual unless you add a separate workflow layer. Forms/Sheets give you collaboration and analysis, and Zapier can mirror new responses into Discord.
- Inference from product docs: there is no native reviewer assignment, claim model, interview thread flow, prior-application history, or Discord-native trust context.

### Decision Tracking
- Google Forms has no native adjudication state machine. You can allow response editing, move data into Sheets, and build ad hoc status tracking, but that is a custom process rather than a product feature.
- Inference from docs: no built-in audit trail for decision transitions, no waitlist, and no appeals handling.

### Pricing
- For organizations, Google Forms is included in Google Workspace plans starting at `Business Starter $7/user/month` on annual commitment.
- Discord automation commonly adds Zapier, whose current Free tier includes `100 tasks/month`; paid plans start at `Professional $19.99/month` billed annually.
- Inference: consumer Google-account usage remains the cheapest path, but the real cost for a Discord application workflow usually comes from the automation and manual process overhead, not the form itself.

### Limitations & User Complaints
- Google Forms is a common Discord workaround, not a purpose-built Discord adjudication system. Old Reddit threads explicitly recommend it for guild applications or discuss webhooks that merely post submissions into Discord.
- File-upload questions force Google sign-in, and forms with file upload, rating, image questions/options, or secured quizzes cannot be embedded in email.
- The major product gap is process fragmentation: applicants leave Discord, reviewers split across Forms, Sheets, and Discord, and state management is entirely custom.

### Sources
- https://workspace.google.com/products/forms/
- https://support.google.com/docs/answer/7322334?hl=en
- https://support.google.com/docs/answer/141062?hl=en
- https://support.google.com/docs/answer/2839588?hl=en
- https://workspace.google.com/pricing
- https://zapier.com/apps/discord/integrations/google-forms
- https://zapier.com/pricing
- https://www.reddit.com/r/discordapp/comments/5swo0x/guild_applications_through_discord/
- https://www.reddit.com/r/discordapp/comments/8g53pg/i_made_a_handy_webhook_for_google_forms_to_post/
- https://www.reddit.com/r/discordapp/comments/dlxyry/discord_server_mod_applications/

## Typeform + Discord Automation

### Application Workflow
- Typeform gives a much stronger standalone form builder than Discord bots, but Discord integration is still usually notification-oriented rather than adjudication-oriented.
- The common setup is: collect the application in Typeform, then use Zapier or webhooks to post to Discord, create forum posts, add roles, or DM staff/users.
- Typeform itself remains the system of record for responses; Discord is the notification/action surface.

### Form Capabilities
- Typeform supports extensive question types: contact info, email, phone, address, website, multiple choice, dropdown, picture choice, yes/no, legal, checkbox, NPS, opinion scale, rating, ranking, matrix, long text, short text, video/audio answers, AI clarification, payment, number, file upload, date, Calendly, signature, question groups, multi-question pages, and more.
- File upload is available on `Basic` and higher, supports all file types, and allows uploads from desktop or mobile, but each file is capped at `10MB`.
- Typeform also exposes question/block references for API users, which is useful for custom integrations, but it is not the same thing as immutable submission-version contracts.

### Review Features
- Typeform supports multiple seats, organization/workspace permissions, response lookup, exports, APIs, and webhooks.
- Zapier can post new submissions to Discord channels, forum posts, DMs, and role actions.
- Inference from docs: none of this gives you Discord-native reviewer ownership, claim locks, interview channels, or integrated trust/history surfacing.

### Decision Tracking
- Zapier’s FAQ explicitly frames the Discord integration around notifications and limited actions, not full adjudication. It also says dynamic role creation is not supported directly and that more complex conditional logic or real-time handling may require extra steps or manual intervention.
- Typeform’s own higher plans add organization activity logs, but that tracks workspace user activity, not applicant decision transitions.
- File uploads also introduce a privacy tradeoff: when responses are exported or forwarded through integrations/webhooks, uploaded-file links can become publicly accessible to anyone with the link.

### Pricing
- Official pricing currently starts at `Basic $39/month` monthly or `$28/month` annual equivalent, `Plus $79/$56`, `Business $129/$91`, and `Talent $169/$119`, with Enterprise/custom options above that.
- Typeform says a free plan exists, but advanced capabilities like file upload require paid plans.
- If Discord automation is handled via Zapier, that adds another pricing layer.

### Limitations & User Complaints
- This stack is far more capable as a form builder than Discord bots, but much worse as a Discord adjudication product unless you build custom automation around it.
- Zapier’s own FAQ acknowledges limits around real-time updates and complex conditional logic in the Discord-Typeform integration.
- For Humility’s use case, the biggest issue is architecture mismatch: Typeform is excellent at intake, but not at reviewer collision control, audit-first decisions, or Discord-native interview flow.

### Sources
- https://www.typeform.com/pricing
- https://help.typeform.com/hc/en-us/articles/360051789692-Question-types
- https://help.typeform.com/hc/en-us/articles/360051567012-File-Upload-question
- https://zapier.com/apps/discord/integrations/typeform

## Gap Analysis

- **Form versioning / immutable in-flight contracts:** Gather is the only reviewed product that explicitly snapshots the form at submission time. That is a real differentiator, but Gather is deprecated. The mainstream bots do not publish anything close to versioned form contracts.
- **Reviewer collision prevention:** None of the reviewed tools publishes a genuine claim-lock or single-reviewer ownership model. The best most of them offer is role-based permissioning or a shared dashboard.
- **Trust profile integration:** None of the products meaningfully surfaces member trust context such as prior applications, server history, moderation signals, identity consistency, or linked off-platform reputation inside the review UI.
- **Structured audit trail:** Several tools have archives, comments, history pages, or org activity logs, but none combines application transitions, actor identity, timestamps, rationale, and rollback-friendly state history in a way that looks like a real adjudication audit ledger.
- **Waitlist management:** This is effectively absent. The reviewed Discord-native bots collapse decisions into approve/reject/archive, with Gather adding richer states but still not a first-class waitlist/re-queue process.
- **Interview workflow via private threads/channels:** Gather and Application Bot do support private interview channels, and Appy supports staff discussion threads. What none of them does well is tie interview creation, reviewer ownership, structured notes, and final decisioning into one coherent workflow.
- **Discord-first plus operator-grade intake:** The market forces a tradeoff. Discord-native bots are lighter and faster for communities, but weak on form sophistication and process control. External form platforms are stronger on intake UX and field logic, but weak on Discord-native review and state management.

## Bottom Line For Humility

- The closest match on **form rigor** is Gather, because of snapshots and explicit submission states, but it is strategically unusable now that the product is officially deprecated.
- The closest matches on **Discord-native operator workflow** are Appy and Application Bot, but both stop short of reviewer ownership, strong decision accounting, and waitlist/interview orchestration.
- External stacks like Google Forms or Typeform can outclass bot-native form builders, but they do not solve Humility’s core product problem: adjudication as a first-class workflow rather than a pile of notifications and spreadsheets.
