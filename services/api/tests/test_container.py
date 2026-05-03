import pytest

from app.core.container import ApiContainer
from app.core.factory import create_api_app
from dependency_injector import providers


NAMED_PROVIDER_PATHS = (
    "settings",
    "core.settings",
    "core.db",
    "infra.cedar_authorizer",
    "infra.ocr_provider",
    "repos.claim",
    "repos.activity",
    "repos.application_messages",
    "repos.applications",
    "repos.archive_queries",
    "repos.archive_runs",
    "repos.audit",
    "repos.authority",
    "repos.chapter_roles",
    "repos.chapter_templates",
    "repos.chapter_transitions",
    "repos.chapters",
    "repos.compliance",
    "repos.deferred_effects",
    "repos.forms",
    "repos.members",
    "repos.mutations",
    "repos.notification_events",
    "repos.notifications",
    "repos.permissions",
    "repos.policies",
    "repos.public_chapters",
    "repos.read_models",
    "repos.roster",
    "repos.scheduler",
    "repos.ticket_categories",
    "repos.ticket_messages",
    "repos.ticket_sla",
    "repos.tickets",
    "repos.trust",
    "repos.web",
    "services.applicant_discord_auth",
    "services.application_messages",
    "services.application_public_submit_notifications",
    "services.application_transcript",
    "services.applications",
    "services.audit",
    "services.audit_overrides",
    "services.audit_queries",
    "services.authority",
    "services.authorization",
    "services.chapter_roles",
    "services.chapter_templates",
    "services.chapters",
    "services.compliance",
    "services.compliance_corrections",
    "services.compliance_extraction",
    "services.compliance_review",
    "services.deferred_effects",
    "services.file_upload",
    "services.form_visibility",
    "services.forms",
    "services.leadership_handoff_applications",
    "services.leadership_handoff_tickets",
    "services.members",
    "services.mutations",
    "services.notification_events",
    "services.notifications",
    "services.notifications_delivery",
    "services.notifications_materialize",
    "services.permission_reconciliation",
    "services.permissions",
    "services.policies",
    "services.public_chapters",
    "services.read_models",
    "services.roster",
    "services.scheduler",
    "services.ticket_categories",
    "services.ticket_messages",
    "services.ticket_sla",
    "services.tickets",
    "services.trust",
    "services.web",
    "tasks.archive",
    "tasks.compliance",
    "tasks.notifications_deliver",
    "tasks.notifications_materialize",
    "tasks.permission_expiry",
    "tasks.read_models",
    "tasks.ticket_sla",
    "tasks.scheduler_loop",
    "tasks.configure_task_runtime",
)


def _resolve_path(container: ApiContainer, path: str):
    value = container
    for part in path.split("."):
        value = getattr(value, part)
    return value()


def test_container_resolves_every_named_provider(test_settings):
    """Object providers prove declaration plus module import, not constructor wiring.

    Constructor wiring lands when 142b/c replace module Object providers with
    Factory/Singleton providers for real repository and service classes.
    """
    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        unresolved = []
        for path in NAMED_PROVIDER_PATHS:
            try:
                value = _resolve_path(container, path)
            except Exception as exc:
                unresolved.append((path, exc))
            else:
                if value is None:
                    unresolved.append((path, AssertionError("resolved to None")))
        assert unresolved == []
    finally:
        container.shutdown_resources()


def test_container_db_override_replaces_resolution(test_settings):
    sentinel = object()
    container = ApiContainer(settings=test_settings)
    container.core.db.override(providers.Object(sentinel))
    container.init_resources()
    try:
        assert container.core.db() is sentinel
    finally:
        container.shutdown_resources()


def test_container_resolves_ticket_factories(test_settings):
    """TG-4: Container resolves ticket repos and services as Factory
    instances (post-142b shape), not as module references.
    """
    from app.repositories.ticket_categories import TicketCategoriesRepository
    from app.repositories.ticket_messages import TicketMessagesRepository
    from app.repositories.ticket_sla import TicketSlaRepository
    from app.repositories.tickets import TicketsRepository
    from app.services.ticket_messages import TicketMessagesService
    from app.services.ticket_sla import TicketSlaService
    from app.services.tickets import TicketsService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        assert isinstance(container.repos.tickets(), TicketsRepository)
        assert isinstance(
            container.repos.ticket_categories(),
            TicketCategoriesRepository,
        )
        assert isinstance(container.repos.ticket_messages(), TicketMessagesRepository)
        assert isinstance(container.repos.ticket_sla(), TicketSlaRepository)
        assert isinstance(container.services.tickets(), TicketsService)
        assert isinstance(container.services.ticket_messages(), TicketMessagesService)
        assert isinstance(container.services.ticket_sla(), TicketSlaService)
    finally:
        container.shutdown_resources()


def test_container_missing_settings_raises():
    with pytest.raises(Exception, match=r"Dependency|defined"):
        ApiContainer().core.settings()


def test_container_shutdown_clean_after_override(test_settings):
    class CloseTracker:
        closed = False

        def close(self):
            self.closed = True

    sentinel = CloseTracker()
    container = ApiContainer(settings=test_settings)
    container.core.db.override(providers.Object(sentinel))
    container.init_resources()
    container.shutdown_resources()

    assert sentinel.closed is False


def test_factory_app_state_aligns_with_container(test_settings):
    app = create_api_app(settings=test_settings)
    container = app.state.container
    try:
        assert container is not None
        assert app.state.db is container.core.db()
        assert app.state.scheduler_loop is container.tasks.scheduler_loop()
        assert app.state.cedar_authorizer is container.infra.cedar_authorizer()
        assert app.state.ocr_provider is container.infra.ocr_provider()
        assert app.state.settings is container.core.settings()
    finally:
        container.shutdown_resources()
