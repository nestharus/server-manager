"""Discord bot slash commands."""

from app.commands.application_review import (
    APPLICATION_APPROVE_COMMAND,
    APPLICATION_CLAIM_COMMAND,
    APPLICATION_DENY_COMMAND,
    register_application_review_commands,
)
from app.commands.application_submission import (
    APPLICATION_SUBMIT_COMMAND,
    register_application_submission_commands,
)
from app.commands.chapters import PROVISION_CHAPTER_COMMAND, register_chapter_commands
from app.commands.registry import InteractionRegistry
from app.commands.tickets import (
    TICKET_OPEN_COMMAND,
    TICKET_TRANSITION_COMMAND,
    register_ticket_commands,
)

__all__ = [
    "APPLICATION_APPROVE_COMMAND",
    "APPLICATION_CLAIM_COMMAND",
    "APPLICATION_DENY_COMMAND",
    "APPLICATION_SUBMIT_COMMAND",
    "InteractionRegistry",
    "PROVISION_CHAPTER_COMMAND",
    "TICKET_OPEN_COMMAND",
    "TICKET_TRANSITION_COMMAND",
    "register_application_review_commands",
    "register_application_submission_commands",
    "register_chapter_commands",
    "register_ticket_commands",
]
