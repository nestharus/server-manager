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


def test_container_resolves_permission_factories(test_settings):
    """TG-4: Container resolves permission repo and services as Factory
    instances (post-142c shape)."""
    from app.repositories.permissions import PermissionsRepository
    from app.services.permissions import PermissionsService
    from app.services.permission_reconciliation import PermissionReconciliationService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        assert isinstance(container.repos.permissions(), PermissionsRepository)
        assert isinstance(container.services.permissions(), PermissionsService)
        assert isinstance(
            container.services.permission_reconciliation(),
            PermissionReconciliationService,
        )
    finally:
        container.shutdown_resources()


def test_container_resolves_application_factories(test_settings):
    """TG-4: Container resolves application repos and services as
    Factory instances (post-142d shape) plus infra.s3_client and
    application_notification_emitter."""
    from app.repositories.applications import ApplicationsRepository
    from app.repositories.application_messages import ApplicationMessagesRepository
    from app.repositories.forms import FormsRepository
    from app.repositories.public_chapters import PublicChaptersRepository
    from app.services.applications import ApplicationsService
    from app.services.application_messages import ApplicationMessagesService
    from app.services.application_transcript import ApplicationTranscriptService
    from app.services.forms import FormsService
    from app.services.public_chapters import PublicChaptersService
    from app.services.file_upload import FileUploadService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        # 4 repos
        assert isinstance(container.repos.applications(), ApplicationsRepository)
        assert isinstance(
            container.repos.application_messages(),
            ApplicationMessagesRepository,
        )
        assert isinstance(container.repos.forms(), FormsRepository)
        assert isinstance(container.repos.public_chapters(), PublicChaptersRepository)
        # 6 services
        assert isinstance(container.services.applications(), ApplicationsService)
        assert isinstance(
            container.services.application_messages(),
            ApplicationMessagesService,
        )
        assert isinstance(
            container.services.application_transcript(),
            ApplicationTranscriptService,
        )
        assert isinstance(container.services.forms(), FormsService)
        assert isinstance(container.services.public_chapters(), PublicChaptersService)
        assert isinstance(container.services.file_upload(), FileUploadService)
        # infra.s3_client present
        assert container.infra.s3_client() is not None
        # application_notification_emitter callable
        assert callable(container.services.application_notification_emitter)
    finally:
        container.shutdown_resources()


def test_container_resolves_notification_factories(test_settings):
    """TG-3/4/5/6: Container resolves notifications/scheduler/deferred
    repos and services as Factory instances (post-142g shape)."""
    from app.repositories.deferred_effects import DeferredEffectsRepository
    from app.repositories.notification_events import NotificationEventsRepository
    from app.repositories.notifications import NotificationsRepository
    from app.repositories.scheduler import SchedulerRepository
    from app.services.deferred_effects import DeferredEffectsService
    from app.services.notification_events import NotificationEventsService
    from app.services.notifications import NotificationsService
    from app.services.notifications_delivery import NotificationsDeliveryService
    from app.services.notifications_materialize import NotificationsMaterializeService
    from app.services.scheduler import SchedulerService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        # 4 repos
        assert isinstance(container.repos.deferred_effects(), DeferredEffectsRepository)
        assert isinstance(container.repos.notification_events(), NotificationEventsRepository)
        assert isinstance(container.repos.notifications(), NotificationsRepository)
        assert isinstance(container.repos.scheduler(), SchedulerRepository)
        # 6 services
        assert isinstance(container.services.deferred_effects(), DeferredEffectsService)
        assert isinstance(container.services.notification_events(), NotificationEventsService)
        assert isinstance(container.services.notifications(), NotificationsService)
        assert isinstance(container.services.notifications_delivery(), NotificationsDeliveryService)
        assert isinstance(
            container.services.notifications_materialize(),
            NotificationsMaterializeService,
        )
        assert isinstance(container.services.scheduler(), SchedulerService)
        # Bound-method emitter identity
        emitter = container.services.application_notification_emitter()
        assert emitter.__func__ is NotificationsService.emit_application_public_submitted_event
        # Handler registration assertion (HandlerRegistry stays module-level)
        from app.services.scheduler import HandlerRegistry

        assert HandlerRegistry is not None  # populated by task module imports
    finally:
        container.shutdown_resources()


def test_container_resolves_chapter_factories(test_settings):
    """TG-4: Container resolves chapter repos and services as Factory
    instances (post-142e shape)."""
    from app.repositories.chapters import ChaptersRepository
    from app.repositories.chapter_roles import ChapterRolesRepository
    from app.repositories.chapter_templates import ChapterTemplatesRepository
    from app.repositories.chapter_transitions import ChapterTransitionsRepository
    from app.repositories.archive_queries import ArchiveQueriesRepository
    from app.repositories.archive_runs import ArchiveRunsRepository
    from app.services.chapters import ChaptersService
    from app.services.chapter_templates import ChapterTemplatesService
    from app.services.chapter_roles import ChapterRolesService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        # 6 repos
        assert isinstance(container.repos.chapters(), ChaptersRepository)
        assert isinstance(container.repos.chapter_roles(), ChapterRolesRepository)
        assert isinstance(container.repos.chapter_templates(), ChapterTemplatesRepository)
        assert isinstance(
            container.repos.chapter_transitions(),
            ChapterTransitionsRepository,
        )
        assert isinstance(container.repos.archive_queries(), ArchiveQueriesRepository)
        assert isinstance(container.repos.archive_runs(), ArchiveRunsRepository)
        # 3 services
        assert isinstance(container.services.chapters(), ChaptersService)
        assert isinstance(
            container.services.chapter_templates(),
            ChapterTemplatesService,
        )
        assert isinstance(container.services.chapter_roles(), ChapterRolesService)
    finally:
        container.shutdown_resources()


def test_container_resolves_authority_factories(test_settings):
    """TG-4: Container resolves authority/members/policies/trust/
    roster repos and services as Factory instances (post-142f shape)."""
    from app.repositories.authority import AuthorityRepository
    from app.repositories.members import MembersRepository
    from app.repositories.policies import PoliciesRepository
    from app.repositories.roster import RosterRepository
    from app.repositories.trust import TrustRepository
    from app.services.authority import AuthorityService
    from app.services.leadership_handoff_applications import (
        LeadershipHandoffApplicationsService,
    )
    from app.services.leadership_handoff_tickets import (
        LeadershipHandoffTicketsService,
    )
    from app.services.members import MembersService
    from app.services.policies import PoliciesService
    from app.services.roster import RosterService
    from app.services.trust import TrustService

    container = ApiContainer(settings=test_settings)
    container.init_resources()
    try:
        # 5 repos
        assert isinstance(container.repos.authority(), AuthorityRepository)
        assert isinstance(container.repos.members(), MembersRepository)
        assert isinstance(container.repos.policies(), PoliciesRepository)
        assert isinstance(container.repos.roster(), RosterRepository)
        assert isinstance(container.repos.trust(), TrustRepository)
        # 7 services
        assert isinstance(container.services.authority(), AuthorityService)
        assert isinstance(
            container.services.leadership_handoff_applications(),
            LeadershipHandoffApplicationsService,
        )
        assert isinstance(
            container.services.leadership_handoff_tickets(),
            LeadershipHandoffTicketsService,
        )
        assert isinstance(container.services.members(), MembersService)
        assert isinstance(container.services.policies(), PoliciesService)
        assert isinstance(container.services.roster(), RosterService)
        assert isinstance(container.services.trust(), TrustService)
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
