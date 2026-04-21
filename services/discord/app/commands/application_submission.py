from __future__ import annotations

from app.handlers.application_submission import handle_application_submit


APPLICATION_SUBMIT_COMMAND = "application_submit"


def register_application_submission_commands(bot) -> None:
    async def _handler(envelope):
        return await handle_application_submit(envelope, api_client=bot.api_client)

    bot.register_interaction_handler(APPLICATION_SUBMIT_COMMAND, _handler)


__all__ = ["APPLICATION_SUBMIT_COMMAND", "register_application_submission_commands"]
