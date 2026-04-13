# Implement: discord_cli.py — Initial Scaffold

## What to create

Create `/home/nes/discord/discord_cli.py` — a thin CLI around discord.py
for inspecting and managing a guild.

## Requirements

1. **Shebang**: `#!/usr/bin/env python3`
2. **Module docstring**: `discord_cli.py — thin CLI around discord.py for inspecting and managing a guild.`
   - Every subcommand opens a gateway session, runs once, prints JSON to stdout, and exits.
   - Token and guild ID come from `.env`.
3. **Environment**: Read `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` from `/home/nes/discord/.env` using `python-dotenv`.
4. **Dependencies**: `discord.py`, `python-dotenv` (already installed in `.venv`)
5. **Architecture**: Use `argparse` for subcommand dispatch. Each subcommand is a function that:
   - Creates a `discord.Client` with appropriate intents
   - Connects, fetches data, prints JSON to stdout, then disconnects
   - Uses `asyncio.run()` to execute
6. **Intents**: Must enable `members` and `message_content` privileged intents.

## Subcommands to implement

### `overview`
- Fetch guild info: name, id, owner, member count, channel count, role count, boost level, created date
- Print as JSON to stdout

### Stubs for future subcommands
Leave room for (but do NOT implement yet — just add them as argparse subcommands that print "not yet implemented"):
- `bots` — list bot members
- `channels` — list all channels
- `find-channel` — find channel by name
- `read` — read messages from a channel
- `integrations` — list guild integrations

## Pattern

```python
#!/usr/bin/env python3
"""discord_cli.py — thin CLI around discord.py for inspecting and managing a guild.

Every subcommand opens a gateway session, runs once, prints JSON to stdout,
and exits. Token and guild ID come from .env.
"""

import argparse
import asyncio
import json
import os
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))

# ... implement overview and stubs
```

## Output

Write the complete file to `/home/nes/discord/discord_cli.py`. Make sure
it runs correctly with:
```bash
cd /home/nes/discord && .venv/bin/python discord_cli.py overview
```
