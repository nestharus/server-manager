# Needs Synthesis: daemon/applications.py

Date: 2026-04-13

## Context

The research (research/18-applications.md) documented the discord.py 2.7.1
API surface and identified four mismatches between the design doc and the
actual platform/library behavior. This synthesis maps those findings to
Humility's specific context and flags gaps.

## Mismatch Resolutions for Humility

### 1. Select components in modals (research finding #1)

Discord now supports select components inside modals, and discord.py 2.7.1
supports this. However, `multi_select` maps to setting `max_values > 1`
on a single `discord.ui.Select` in the modal. This simplifies the Dark
Nemesis form significantly: all 7 questions can fit in a single modal
(5 text inputs + 1 select + 1 multi-select = 7 components, but modals
allow only 5). So we still need a multi-step flow for Dark Nemesis.

**Decision needed**: Since selects can now go in modals, the step planner
should pack questions into modals greedily (up to 5 components per modal),
mixing text and select types. The current config.py `_build_steps` groups
all text first, then all selects — this should be updated to preserve
source order and pack greedily. However, this is a config.py change, not
an applications.py concern. For now, applications.py should consume
whatever steps config.py provides.

### 2. Modal-to-modal chaining not supported (research finding #2)

`MODAL_SUBMIT` cannot respond with another `MODAL`. This means the
multi-step flow must be: modal -> followup message with buttons/selects ->
button click -> second modal. For Dark Nemesis (7 questions):
- Step 1 (modal): 5 questions (text/number/select mix, up to 5 components)
- Step 2 (followup): remaining 2 questions via ephemeral message with
  select menus or a "Continue" button that opens a second modal

For the P0102 scope, the simplest approach that satisfies the P0108 smoke
test: implement ApplicationModal for the first step and handle followup
steps as ephemeral messages with select menus. The key requirement from
the task is that `ApplicationModal` and `ApplicationReviewView` exist and
are constructable.

### 3. Private thread creation (research finding #3)

Cannot create a private thread off a message — must use
`TextChannel.create_thread(message=None)`. The design doc's "private
thread off that message" must be implemented as: post queue message first,
then create a separate private thread (not attached to the message).
The queue message and thread are linked only by the submission DB record.

### 4. Step planner order (research finding #4)

The current `_build_steps` in config.py groups modal questions first, then
selects. With select-in-modal support, a future revision should pack
greedily in source order. For now, the applications module should consume
steps as-is and handle both "modal" and "followup_selects" step kinds.

## Minimum Viable Surface for P0108

The P0108 smoke test requires:
- `ApplicationModal` — constructable, a discord.ui.Modal subclass
- `ApplicationReviewView` — constructable with `submission_id` parameter,
  contains exactly 4 buttons: Claim, Interview, Approve, Deny
- Button custom_ids: `app:claim:<id>`, `app:interview:<id>`,
  `app:approve:<id>`, `app:deny:<id>`
- `len(view.children) == 4` (buttons directly on the view)

## Full Surface for daemon/applications.py

1. **ApplicationModal** — discord.ui.Modal subclass
   - Accepts FormStepConfig to populate TextInput/Select children
   - on_submit callback collects answers
   - custom_id encodes chapter slug + step index for routing

2. **ApplicationReviewView** — discord.ui.View subclass
   - timeout=None for persistence across restarts
   - 4 buttons: Claim, Interview, Approve, Deny
   - custom_ids: `app:<action>:<submission_id>`
   - Button callbacks handle claim/interview/approve/deny actions

3. **Registration hook** — function the entry point calls to register
   the /apply command and persistent views
   - `setup_applications(bot)` or similar
   - Registers /apply slash command with chapter autocomplete
   - Registers ApplicationReviewView as persistent

4. **Blacklist check** — at top of /apply handler, check
   `db.get_blacklist_entry()` and deny with ephemeral if blocked

5. **Submission flow** — modal submit -> persist via db.create_submission
   -> post queue embed -> create private thread -> add handler members
   via claim.ensure_preclaim_visibility

6. **Review actions** — button callbacks that:
   - Claim: execute_claim_visibility, update DB status
   - Interview: update DB status to "interview"
   - Approve: add role, DM applicant, archive thread, update DB
   - Deny: capture reason, DM applicant, archive thread, update DB

## Gaps

- The `TYPE_CHECKING` import of `HumilityBot` from `daemon.__main__`
  (referenced in P0105) implies applications.py will use a type hint for
  the bot class. Since `daemon.__main__.py` doesn't exist yet (created in
  P0104), this is a forward reference. Use `TYPE_CHECKING` guard.

- No `update_submission_status` helper exists in db.py yet. The
  applications module will need to update submission status (pending ->
  claimed -> interview -> approved/denied). For now, use raw SQL via
  `conn.execute()` or add a thin helper.

- The entry point (daemon.py / daemon/__main__.py) will need to call the
  registration hook and add the persistent view. That wiring happens in
  P0104, not here.
