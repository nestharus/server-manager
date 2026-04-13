"""Long-running Discord daemon package for the Humility guild.

This package holds the long-running Discord daemon implementation for the
Humility guild. It is separate from `discord_cli.py`, which remains the
one-shot CLI for inspection and administrative tasks.

Planned submodules:
- `config` for loading daemon configuration from repo-managed files
- `db` for SQLite schema, migrations, and query helpers
- `claim` for shared claim and visibility logic
- `applications` for application form rendering and submission flow
- `tickets` for ticket lifecycle handling
- `chapters` for chapter provisioning workflows
- `util` for shared helpers
"""
