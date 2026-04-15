# NOTES.md - agent-maintained log of discovered facts

Last updated: 2026-04-15

## Guild

- Name: Humility
- ID: `900000000000000001`
- Owner: `nestharus` (user id `900000000000000002`)
- Created: 2022-04-04
- Member count during the original sweep: 83
- Premium tier: 1

## Ticketing

- `ticketsbot.net` was discontinued on `2025-03-05`.
- `panel.ticketsbot.net` returned `404` for the user during this investigation.
- `#support` contains a `2023-12-22` HumilityTicketBot embed titled `Click to open a ticket`.
- `#panels` contains a `2022-04-04` HumilityTicketBot embed titled `General Support`.
- `#ticket-logs` contains only a small number of historical tickets, including ticket `3` on `2025-04-11` opened by `nestharus`.
- `#templates` was empty during the sweep.

## Bot Activity Audit

- Hydra (`547905866255433758`): zero visible messages across the scanned channels.
- Gather (`868195275464900618`): zero visible messages across the scanned channels.
- Apollo (`475744554910351370`): zero visible messages across the scanned channels.
- sesh (`616754792965865495`): 2 visible messages, both in `#moderation-commands`, both promotional/premium notices.
- Zira (`275813801792634880`): 15 visible messages, all in `#admin-chat`, consisting of old setup actions and premium notices.

## Roles and Structure

- The staff stack starts with `Administrator`, `Moderator`, `Staff`, and `Trial Mod`.
- The chapter stack includes `Chapter Officer`, `Chapter Member`, `Chapter Guild War`, `Chapter Applicant`, `Chapter`, and `Chapter Public`.
- There are two separate `Robots` roles; one functions as the effective permissions container for bots and one is used as a hoisted visual separator.

## Chapter Scaffolding

- The `GUILD TEMPLATE` category is hidden from `@everyone` and exposed to chapter roles such as `Chapter Officer`.
- The category contains structure for chapter operations, but the template channels are empty.
- No evidence was found that real chapter applications or populated chapter spaces have ever been used.

## Working Conclusions

- The user wants bot-consolidation planning but does not want to rotate the bot token right now.
- `Hydra`, `Apollo`, and `sesh` appear unused from Discord-visible evidence.
- `Gather` has no Discord-visible activity, but it may still have external dashboard configuration.
- A first-party applications subsystem should replace Gather only after the flow is designed and tested.

## Library Facts

- `discord.py` 2.7.x exposes `Message.components` as a read-only list of `discord.Component` subclasses; classic ticket panels are typically `ActionRow -> Button/SelectMenu`, but 2.6+ also allows v2 top-level components such as `SectionComponent` and `Container`.
