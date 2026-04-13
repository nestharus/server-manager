"""Discord application flow surface for chapter applications."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import secrets
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands

from daemon import claim, db
from daemon.config import ChapterConfig, FormConfig, FormStepConfig, QuestionConfig

if TYPE_CHECKING:
    from daemon.__main__ import HumilityBot  # noqa: F401


_log = logging.getLogger(__name__)

SESSION_TTL = timedelta(minutes=15)
MAX_MODAL_COMPONENTS = 5
ACTIVE_REVIEW_STATUSES = ("pending", "claimed", "interview")


@dataclass(slots=True)
class ApplicationSessionState:
    session_id: str
    chapter_slug: str
    applicant_id: int
    current_step_index: int
    answers_by_question_id: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _build_modal_title(*, form: FormConfig, step_index: int, total_steps: int) -> str:
    return _truncate(f"{form.title} ({step_index + 1}/{total_steps})", 45)


def _build_modal_custom_id(*, chapter_slug: str, session_id: str, step_index: int) -> str:
    token = session_id[:24]
    return _truncate(f"apply:{chapter_slug}:{step_index}:{token}", 99)


def _require_modal_step(form: FormConfig, step_index: int) -> FormStepConfig:
    try:
        step = form.steps[step_index]
    except IndexError as exc:
        raise ValueError(f"Form step {step_index} is out of range.") from exc

    if step.kind != "modal":
        raise ValueError(f"Form step {step_index} must be a modal step.")
    if len(step.questions) > MAX_MODAL_COMPONENTS:
        raise ValueError(
            f"Modal step {step_index} has {len(step.questions)} questions; "
            f"Discord modals allow at most {MAX_MODAL_COMPONENTS}."
        )
    return step


def _text_style_for_question(question: QuestionConfig) -> discord.TextStyle:
    if question.type == "long":
        return discord.TextStyle.paragraph
    return discord.TextStyle.short


def _build_text_input(question: QuestionConfig) -> discord.ui.TextInput[Any]:
    return discord.ui.TextInput(
        label=_truncate(question.label, 45),
        style=_text_style_for_question(question),
        custom_id=f"question:{question.id}",
        required=question.required,
        max_length=question.max_length,
    )


def _get_sessions(bot: Any) -> dict[str, ApplicationSessionState]:
    sessions = getattr(bot, "_application_sessions", None)
    if sessions is None:
        sessions = {}
        setattr(bot, "_application_sessions", sessions)
    return sessions


def _evict_expired_sessions(bot: Any, *, now: datetime | None = None) -> None:
    current_time = now or _utcnow()
    cutoff = current_time - SESSION_TTL
    sessions = _get_sessions(bot)
    expired_ids = [
        session_id
        for session_id, session in sessions.items()
        if session.updated_at < cutoff
    ]
    for session_id in expired_ids:
        sessions.pop(session_id, None)


def _begin_application_session(*, bot: Any, chapter: ChapterConfig, applicant_id: int) -> ApplicationSessionState:
    _evict_expired_sessions(bot)
    session = ApplicationSessionState(
        session_id=secrets.token_urlsafe(12),
        chapter_slug=chapter.slug,
        applicant_id=applicant_id,
        current_step_index=0,
    )
    _get_sessions(bot)[session.session_id] = session
    return session


def _get_session(bot: Any, session_id: str) -> ApplicationSessionState | None:
    _evict_expired_sessions(bot)
    return _get_sessions(bot).get(session_id)


def _store_step_answers(
    session: ApplicationSessionState,
    *,
    questions: tuple[QuestionConfig, ...],
    values: dict[str, object],
) -> None:
    for question in questions:
        if question.id in values:
            session.answers_by_question_id[question.id] = values[question.id]
    session.updated_at = _utcnow()


def _find_chapter(bot: Any, slug: str) -> ChapterConfig | None:
    config = getattr(bot, "config", None)
    chapters = getattr(config, "chapters", ())
    for chapter in chapters:
        if chapter.slug == slug:
            return chapter
    return None


def _user_has_officer_role(user: Any, officer_role_id: int) -> bool:
    roles = getattr(user, "roles", ())
    return any(getattr(role, "id", None) == officer_role_id for role in roles)


class ApplicationModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        bot: Any,
        chapter: ChapterConfig,
        form: FormConfig,
        step_index: int,
        session_id: str | None = None,
    ) -> None:
        self.bot = bot
        self.chapter = chapter
        self.form = form
        self.step_index = step_index
        self.step = _require_modal_step(form, step_index)
        self.session_id = session_id or secrets.token_urlsafe(12)

        super().__init__(
            title=_build_modal_title(form=form, step_index=step_index, total_steps=len(form.steps)),
            timeout=None,
            custom_id=_build_modal_custom_id(
                chapter_slug=chapter.slug,
                session_id=self.session_id,
                step_index=step_index,
            ),
        )

        for question in self.step.questions:
            self.add_item(_build_text_input(question))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        session = _get_session(self.bot, self.session_id)
        if session is None:
            await interaction.response.send_message(
                "This application session expired. Run `/apply` again.",
                ephemeral=True,
            )
            return

        answers = {
            question.id: child.value
            for question, child in zip(self.step.questions, self.children, strict=True)
        }
        _store_step_answers(session, questions=self.step.questions, values=answers)

        next_step_index = self.step_index + 1
        if next_step_index < len(self.form.steps):
            session.current_step_index = next_step_index
            await interaction.response.send_message(
                "This application step was recorded.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Your application draft was recorded.",
            ephemeral=True,
        )


class _ReviewActionButton(discord.ui.Button["ApplicationReviewView"]):
    def __init__(
        self,
        *,
        label: str,
        action: str,
        submission_id: int,
        style: discord.ButtonStyle,
    ) -> None:
        super().__init__(
            label=label,
            style=style,
            custom_id=f"app:{action}:{submission_id}",
        )
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        await self.view.handle_action(interaction, self.action)


class ApplicationReviewView(discord.ui.View):
    def __init__(self, submission_id: int) -> None:
        super().__init__(timeout=None)
        self.submission_id = submission_id
        self.add_item(
            _ReviewActionButton(
                label="Claim",
                action="claim",
                submission_id=submission_id,
                style=discord.ButtonStyle.secondary,
            )
        )
        self.add_item(
            _ReviewActionButton(
                label="Interview",
                action="interview",
                submission_id=submission_id,
                style=discord.ButtonStyle.primary,
            )
        )
        self.add_item(
            _ReviewActionButton(
                label="Approve",
                action="approve",
                submission_id=submission_id,
                style=discord.ButtonStyle.success,
            )
        )
        self.add_item(
            _ReviewActionButton(
                label="Deny",
                action="deny",
                submission_id=submission_id,
                style=discord.ButtonStyle.danger,
            )
        )

    async def handle_action(self, interaction: discord.Interaction, action: str) -> None:
        bot = interaction.client
        conn = getattr(bot, "conn", None)
        if conn is None:
            await interaction.response.send_message(
                "Application storage is unavailable.",
                ephemeral=True,
            )
            return

        row = db.get_submission_by_id(conn, self.submission_id)
        if row is None:
            await interaction.response.send_message(
                "This application no longer exists.",
                ephemeral=True,
            )
            return

        chapter = _find_chapter(bot, row["chapter_slug"])
        if chapter is None:
            await interaction.response.send_message(
                "This application's chapter configuration is missing.",
                ephemeral=True,
            )
            return

        if not _user_has_officer_role(interaction.user, chapter.officer_role_id):
            await interaction.response.send_message(
                "Only chapter officers can review applications.",
                ephemeral=True,
            )
            return

        if action == "claim":
            transitioned = db.transition_submission_status(
                conn,
                self.submission_id,
                from_status="pending",
                to_status="claimed",
                claimer_id=interaction.user.id,
            )
            if transitioned and row["thread_id"] is not None:
                await self._maybe_apply_claim_visibility(interaction, row)
            message = "Application claimed." if transitioned else "Application could not be claimed."
        elif action == "interview":
            transitioned = db.transition_submission_status(
                conn,
                self.submission_id,
                from_status=("pending", "claimed"),
                to_status="interview",
            )
            message = (
                "Application moved to interview."
                if transitioned
                else "Application could not be moved to interview."
            )
        elif action == "approve":
            transitioned = db.transition_submission_status(
                conn,
                self.submission_id,
                from_status=ACTIVE_REVIEW_STATUSES,
                to_status="approved",
                decided_by=interaction.user.id,
                decided_at=_utcnow().isoformat(),
            )
            message = "Application approved." if transitioned else "Application could not be approved."
        elif action == "deny":
            transitioned = db.transition_submission_status(
                conn,
                self.submission_id,
                from_status=ACTIVE_REVIEW_STATUSES,
                to_status="denied",
                decided_by=interaction.user.id,
                decided_at=_utcnow().isoformat(),
            )
            message = "Application denied." if transitioned else "Application could not be denied."
        else:
            message = "Unknown application action."

        await interaction.response.send_message(message, ephemeral=True)

    async def _maybe_apply_claim_visibility(
        self,
        interaction: discord.Interaction,
        row: Any,
    ) -> None:
        channel = interaction.guild.get_channel(row["thread_id"]) if interaction.guild else None
        if channel is None or not isinstance(channel, discord.Thread):
            return

        requester = interaction.guild.get_member(row["applicant_id"]) if interaction.guild else None
        if requester is None:
            return

        try:
            await claim.execute_claim_visibility(
                channel,
                requester=requester,
                claimer=interaction.user,
            )
        except Exception:
            _log.debug(
                "Failed to apply claim visibility for submission %s",
                self.submission_id,
                exc_info=True,
            )
            return


async def setup_applications(bot: "HumilityBot") -> None:
    _get_sessions(bot)
    setattr(bot, "_application_session_ttl", SESSION_TTL)

    guild = discord.Object(id=bot.guild_id)

    if bot.tree.get_command("apply", guild=guild) is None:

        @app_commands.guilds(guild)
        @app_commands.describe(chapter="The chapter slug to apply to")
        @app_commands.command(name="apply", description="Apply to a Humility chapter")
        async def apply(interaction: discord.Interaction, chapter: str) -> None:
            chapter_config = _find_chapter(bot, chapter)
            if chapter_config is None:
                await interaction.response.send_message(
                    f"Unknown chapter slug: {chapter}",
                    ephemeral=True,
                )
                return

            conn = getattr(bot, "conn", None)
            if conn is None:
                await interaction.response.send_message(
                    "Application storage is unavailable.",
                    ephemeral=True,
                )
                return

            blacklist_entry = db.get_blacklist_entry(conn, chapter_config.slug, interaction.user.id)
            if blacklist_entry is not None:
                await interaction.response.send_message(
                    "You cannot apply to this chapter.",
                    ephemeral=True,
                )
                return

            if db.has_active_submission(conn, interaction.user.id, chapter_config.slug):
                await interaction.response.send_message(
                    "You already have an active application for this chapter.",
                    ephemeral=True,
                )
                return

            if not chapter_config.form.steps:
                await interaction.response.send_message(
                    "This chapter form is not configured.",
                    ephemeral=True,
                )
                return

            first_step = chapter_config.form.steps[0]
            if first_step.kind != "modal":
                await interaction.response.send_message(
                    "This application flow is not available yet.",
                    ephemeral=True,
                )
                return

            session = _begin_application_session(
                bot=bot,
                chapter=chapter_config,
                applicant_id=interaction.user.id,
            )

            await interaction.response.send_modal(
                ApplicationModal(
                    bot=bot,
                    chapter=chapter_config,
                    form=chapter_config.form,
                    step_index=0,
                    session_id=session.session_id,
                )
            )

        bot.tree.add_command(apply, guild=guild, override=True)

    for submission_id in db.load_active_submission_ids(bot.conn):
        bot.add_view(ApplicationReviewView(submission_id=submission_id))


__all__ = [
    "ApplicationModal",
    "ApplicationReviewView",
    "setup_applications",
]
