# NOTES.md - agent-maintained log of discovered facts

Last updated: 2026-04-11

## Guild

- Name: Humility
- ID: `900000000000000001`
- Owner: `nestharus` (user id `900000000000000002`)
- Created: 2022-04-04
- Member count during this sweep: 83
- Premium tier: 1

## Bots and Integrations

- 12 bots observed during the sweep.
- HumilityTicketBot matches ticketsbot.net on Discord-side identity: app/bot id `954933581501849610`.
- Redundant bot pairs called out by the original AI:
  - Apollo + sesh for calendar/events
  - Hydra + Zira for reaction-role or form-related automation
- Multiple bot records showed duplicated `Robots` role names in their member-role lists.

## Tickets Investigation

- `#support` contains a `2023-12-22` HumilityTicketBot panel embed titled `Click to open a ticket`.
- `#support` topic is `Create a support ticket here.`
- `#support` had no restrictive overwrite during the sweep; only `@everyone` with `allow: 0` and `deny: 0`.
- `#panels` contains a `2022-04-04` HumilityTicketBot embed titled `General Support`.
- `#templates` was empty during the sweep.
- `#ticket-logs` showed historical tickets including ticket `3` on `2025-04-11`, opened by `nestharus`.
- Ticket `1` had an archive link on `panel.ticketsbot.net`; newer tickets did not, suggesting transcript/archive behavior changed after 2022.

## Gather and First-Party Applications

- Gather is managed through `gather.sh` and is externally controlled via Discord OAuth, not through Discord messages the agent can edit.
- The agent can inspect Gather's Discord-side footprint, but not its internal dashboard configuration.
- A first-party replacement would need an `applications` subsystem in this repo so forms can be defined in-repo and managed through code.
