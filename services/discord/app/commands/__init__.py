"""Discord bot slash commands."""

from app.commands.chapters import PROVISION_CHAPTER_COMMAND, register_chapter_commands
from app.commands.registry import InteractionRegistry

__all__ = [
    "InteractionRegistry",
    "PROVISION_CHAPTER_COMMAND",
    "register_chapter_commands",
]
