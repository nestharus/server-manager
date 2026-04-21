"""Discord bot slash commands."""

from app.commands.chapters import PROVISION_CHAPTER_COMMAND, register_chapter_commands
from app.commands.registry import InteractionRegistry
from app.commands.tickets import (
    TICKET_OPEN_COMMAND,
    TICKET_TRANSITION_COMMAND,
    register_ticket_commands,
)

__all__ = [
    "InteractionRegistry",
    "PROVISION_CHAPTER_COMMAND",
    "TICKET_OPEN_COMMAND",
    "TICKET_TRANSITION_COMMAND",
    "register_chapter_commands",
    "register_ticket_commands",
]
