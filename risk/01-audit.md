# Audit risk assessment — proposals/01-v1-scope.md

Date: 2026-04-13
Assessor: claude-opus (audit)

## Verdict

**LOW**

The proposal demonstrates deliberate attention to the audit-risk surface. Credentials are env-var-only with explicit scrubbing rules for logs and audit rows. Visible Discord mutations are funneled through a single bounded wrapper with per-operation audit events. The OCR pipeline isolates failures from the gateway client. The main residual concerns are (a) audit-trail append-only semantics enforced by convention rather than DB constraint, (b) no per-invoker rate limit on OCR uploads, and (c) staging/production separation relying entirely on environment variables without a code-level guard. None of these concerns have a realistic exploit path that would cause data loss or security breach given the proposal's operational context: single-tenant, single-developer, trusted daemon as the only DB writer. Each concern is addressable with a contained proposal edit, not a rewrite.

## Findings

### Finding 1 — Audit trail append-only is convention, not enforced

- **Severity**: MEDIUM
- **Section of proposal**: §3, §8, §9
- **Description**: `audit.audit_events` is described as "append-only by convention in v1." RLS is explicitly disabled. The daemon service role has unrestricted UPDATE and DELETE access to audit rows. No DB-level trigger, rule, or policy prevents mutation of historical audit records.
- **Why it matters**: A code bug in the daemon (not an external attacker — the daemon is the only writer) could UPDATE or DELETE audit rows, silently destroying the safety-net trail that the mutation wrapper depends on for post-incident forensics. If a provisioning or role-mutation bug occurs and the same bug path corrupts the audit record, the operator loses both the safety control and the evidence of what happened.
- **Recommendation**: Add a DB-level constraint. The simplest option is a row-level trigger on `audit.audit_events` that raises an exception on UPDATE or DELETE. Alternatively, grant the daemon's Supabase service role INSERT-only on the `audit` schema and use a separate restricted role for reads. This is a one-paragraph schema addition, not a rewrite.

### Finding 2 — No per-invoker rate limit on OCR uploads

- **Severity**: LOW
- **Section of proposal**: §6 (Phase 2a)
- **Description**: `/activity upload` copies the attachment to Supabase Storage, then dispatches to Google Cloud Vision. The proposal describes Discord rate-limit awareness for outbound mutations but does not describe any per-user, per-chapter, or per-time-window limit on inbound upload volume. An officer with upload permission could submit dozens of images in rapid succession.
- **Why it matters**: Rapid uploads could exhaust Google Cloud Vision quota (1,000 free images/month, then billed), generate unexpected costs on the Gemini fallback path in Phase 2b, and create a backlog of review-required rows that degrades the officer workflow. The blast radius is contained to the activity subsystem (§10 confirms OCR failures don't crash the gateway), but cost and operator burden are real.
- **Recommendation**: Add a sentence to §6 specifying a per-chapter or per-officer upload throttle (e.g., N uploads per chapter per hour) enforced at the command handler level before the image reaches storage or the OCR provider. Accept as LOW because the officer pool is small and trusted, and the mutation wrapper's blast-radius isolation already prevents cascading failure.

### Finding 3 — Staging/production separation is env-var-only

- **Severity**: LOW
- **Section of proposal**: §9, §11
- **Description**: Staging and production are distinguished solely by which `DISCORD_GUILD_ID` and `SUPABASE_DB_URL` values are set in environment variables. There is no code-level guard (e.g., a startup assertion that the connected guild ID matches an expected environment label, or a schema-level environment tag) to prevent a misconfigured local `.env` from pointing the daemon at the production guild and database simultaneously.
- **Why it matters**: A developer running the daemon locally with a stale or wrong `.env` could execute mutations — including provisioning, role changes, or audit writes — against production. Given that the developer is also the sole operator and guild owner, the realistic blast radius is self-inflicted cleanup, not an adversarial exploit. But the proposal's own mutation-safety design philosophy ("bounded, audited, confirmed") would benefit from a startup guard that catches environment misconfiguration before any mutation runs.
- **Recommendation**: Add a startup check that logs the resolved environment label (staging vs. production) and optionally asserts against an `ENVIRONMENT` env var. This is a minor enhancement, not a blocking concern. Accept as LOW given single-operator context.

### Finding 4 — Transaction boundaries for multi-step workflows not specified

- **Severity**: LOW
- **Section of proposal**: §4, §7, §8
- **Description**: Application approval is described as a bounded mutation sequence: add member role, remove applicant role, insert chapter_members row, record status transition, DM applicant, post terminal embed, archive thread. The proposal does not specify which of these steps run within a single DB transaction versus as separate commits. Similarly, provisioning (§7) writes multiple DB rows across `chapters`, `chapter_roles`, `chapter_channels`, `application_forms`, and `application_form_versions` during a single run.
- **Why it matters**: If the daemon crashes between inserting the `chapter_members` row and recording the status transition, the DB state is internally inconsistent. The Discord mutations (role add, DM, thread archive) are inherently non-transactional, so the proposal correctly records them via the audit trail. But the pure-DB writes within a single logical operation should be atomic to prevent partial-commit corruption.
- **Recommendation**: Add a sentence to §8 or §4 stating that all DB writes within one logical operation (approval, denial, provisioning) execute within a single Postgres transaction. Discord API calls remain outside the transaction boundary and are reconcilable via audit events. This is implicit good practice but worth making explicit given the audit focus.

### Finding 5 — Gemini fallback has a bounded prompt-injection surface

- **Severity**: LOW
- **Section of proposal**: §6 (Phase 2b)
- **Description**: The Gemini fallback receives "the original image plus classical OCR output" and is asked to return structured JSON rows. A malicious image could contain text designed to manipulate the vision LLM's extraction (e.g., injected text overlays that instruct the model to add or modify rows). The proposal describes hallucination controls: reject when quoted text can't be grounded in classical OCR, reject when row count diverges, reject when scores violate expectations.
- **Why it matters**: The grounding controls described in §6 Phase 2b are the correct mitigation. Gemini output is validated against the classical OCR baseline, so an injected instruction would need to simultaneously fool both the classical OCR confidence check (which wouldn't flag text it can read clearly) and the grounding validator. The residual risk is that a carefully crafted overlay passes classical OCR cleanly but manipulates Gemini's interpretation. At Humility's volume and trust model (officer-uploaded images from known games), this is theoretical.
- **Recommendation**: Accept as written, LOW severity. The grounding validation, officer review for flagged rows, and the explicit "no auto-punishment" rule (§14) together mean a hallucinated row results in a flag for officer review, not silent data corruption. If the gold corpus evaluation (§11) reveals that Gemini outputs ever diverge from classical OCR on clean images, that is the signal to tighten grounding rules.

### Finding 6 — Forever retention without a data-deletion procedure

- **Severity**: LOW
- **Section of proposal**: §3, §4, §5, §14
- **Description**: The proposal implements the user's "keep everything forever" decision (D4) with soft deletes across all tables. Application answers, ticket transcripts, member identities, and in-game names are retained indefinitely. There is no described procedure for responding to a data-deletion request from a Discord member who leaves the guild and asks for their data to be removed.
- **Why it matters**: Humility is a private gaming guild, not a commercial service, so GDPR/CCPA formal compliance is unlikely to be required. However, a former member could request deletion of their application answers or ticket content. Without a documented deletion procedure, the operator would need to manually scrub records. The "forever" design is correct for operational audit needs; the gap is purely procedural.
- **Recommendation**: Accept as written, LOW severity. This is an operational procedure question, not an architectural flaw. If a deletion request occurs, the operator can archive or null out PII fields on specific records. The proposal's soft-delete pattern already supports this without schema changes.

### Finding 7 — Token leakage paths are well-addressed

- **Severity**: LOW
- **Section of proposal**: §8, §9, §10
- **Description**: The proposal describes three independent layers preventing secret leakage: (1) `request_json` stores logical parameters only, never raw HTTP/vendor payloads; (2) `error_text` is sanitized before persistence; (3) structured logs pass through the same secret-scrubbing filter before emission. Railway stores all secrets; local `.env` is dev-only.
- **Why it matters**: This is a positive finding. The three-layer approach means a single implementation bug in one layer does not expose secrets if the other layers are intact. The scrubbing filter is described as shared between log emission and audit persistence, reducing the chance of divergent behavior.
- **Recommendation**: Accept as written, LOW severity. Implementation should ensure the scrubbing filter is tested against known secret patterns (bearer tokens, connection strings, API keys) as part of the unit test strategy described in §11.

## Overall assessment

Seven findings: one MEDIUM, six LOW. The MEDIUM finding (audit trail enforced by convention only) is the most material concern because audit integrity is a foundational assumption of the mutation-safety design. However, the realistic attack path is a daemon code bug corrupting its own audit trail, not an external adversary — the daemon is the only DB writer, and there is no untrusted client in v1. The fix is a contained schema addition (one trigger or one restricted grant), not a rewrite.

The remaining LOW findings are either already mitigated by described controls (Gemini grounding, blast-radius isolation, secret scrubbing) or are proportionate gaps given Humility's single-tenant, single-operator context (staging guard, upload throttle, deletion procedure, transaction explicitness).

No finding forces a rewrite or blocks implementation. The MEDIUM finding requires a small, contained proposal edit (adding DB-enforced append-only semantics to the audit schema). With that edit, all material concerns drop to LOW. The overall verdict is **LOW**.

## What a LOW verdict requires

The verdict is LOW because every material concern has either (a) no realistic attack/data-loss path given the proposal's described controls, or (b) a mitigation already described in the proposal that reduces the residual risk to negligible. The one MEDIUM finding (audit append-only enforcement) has a contained fix that does not force structural changes to any other section of the proposal. The combination of bounded mutation wrapper, secret scrubbing, blast-radius isolation, officer-reviewed OCR, and no-auto-punishment policy provides defense in depth that makes the residual risk from any single gap negligible.
