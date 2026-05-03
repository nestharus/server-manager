from __future__ import annotations

from collections.abc import Iterator

from dependency_injector import containers, providers

from app.core.settings import Settings
from app.infrastructure.authz import CedarAuthorizationClient
from app.infrastructure.ocr import StubOcrProvider
from app.repositories import _claim as claim_repo
from app.repositories import activity as activity_repo
from app.repositories import audit as audit_repo
from app.repositories import compliance as compliance_repo
from app.repositories import deferred_effects as deferred_effects_repo
from app.repositories import mutations as mutations_repo
from app.repositories import notification_events as notification_events_repo
from app.repositories import notifications as notifications_repo
from app.repositories import read_models as read_models_repo
from app.repositories import scheduler as scheduler_repo
from app.repositories.application_messages import ApplicationMessagesRepository
from app.repositories.applications import ApplicationsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.forms import FormsRepository
from app.repositories.members import MembersRepository
from app.repositories.policies import PoliciesRepository
from app.repositories.public_chapters import PublicChaptersRepository
from app.repositories.roster import RosterRepository
from app.repositories.ticket_categories import TicketCategoriesRepository
from app.repositories.ticket_messages import TicketMessagesRepository
from app.repositories.ticket_sla import TicketSlaRepository
from app.repositories.tickets import TicketsRepository
from app.repositories.permissions import PermissionsRepository
from app.repositories.trust import TrustRepository
from app.repositories import web as web_repo
from app.repositories.archive_queries import ArchiveQueriesRepository
from app.repositories.archive_runs import ArchiveRunsRepository
from app.repositories.chapter_roles import ChapterRolesRepository
from app.repositories.chapter_templates import ChapterTemplatesRepository
from app.repositories.chapter_transitions import ChapterTransitionsRepository
from app.repositories.chapters import ChaptersRepository
from app.repositories.db import PostgresDatabase
from app.services import applicant_discord_auth as applicant_discord_auth_service
from app.services import (
    application_public_submit_notifications as application_public_submit_notifications_service,
)
from app.services import audit as audit_service
from app.services import audit_overrides as audit_overrides_service
from app.services import audit_queries as audit_queries_service
from app.services import authorization as authorization_service
from app.services import compliance as compliance_service
from app.services import compliance_corrections as compliance_corrections_service
from app.services import compliance_extraction as compliance_extraction_service
from app.services import compliance_review as compliance_review_service
from app.services import deferred_effects as deferred_effects_service
from app.services import form_visibility as form_visibility_service
from app.services import mutations as mutations_service
from app.services import notification_events as notification_events_service
from app.services import notifications as notifications_service
from app.services import notifications_delivery as notifications_delivery_service
from app.services import notifications_materialize as notifications_materialize_service
from app.services.application_messages import ApplicationMessagesService
from app.services.application_transcript import ApplicationTranscriptService
from app.services.applications import ApplicationsService
from app.services.authority import AuthorityService
from app.services.chapter_roles import ChapterRolesService
from app.services.chapter_templates import ChapterTemplatesService
from app.services.chapters import ChaptersService
from app.services.file_upload import FileUploadService, build_s3_client
from app.services.forms import FormsService
from app.services.leadership_handoff_applications import LeadershipHandoffApplicationsService
from app.services.leadership_handoff_tickets import LeadershipHandoffTicketsService
from app.services.members import MembersService
from app.services.notifications import emit_application_public_submitted_event
from app.services.permission_reconciliation import PermissionReconciliationService
from app.services.permissions import PermissionsService
from app.services.policies import PoliciesService
from app.services.public_chapters import PublicChaptersService
from app.services import read_models as read_models_service
from app.services.roster import RosterService
from app.services import scheduler as scheduler_service
from app.services import ticket_categories as ticket_categories_service
from app.services.trust import TrustService
from app.services import web as web_service
from app.services.mutations import mutate_entity
from app.services.ticket_messages import TicketMessagesService
from app.services.ticket_sla import TicketSlaService
from app.services.tickets import TicketsService
from app.services.scheduler import build_scheduler_loop
from app.tasks import archive as archive_task_module
from app.tasks import compliance as compliance_task_module
from app.tasks import configure_task_runtime
from app.tasks import notifications_deliver as notifications_deliver_task_module
from app.tasks import notifications_materialize as notifications_materialize_task_module
from app.tasks import permission_expiry as permission_expiry_task_module
from app.tasks import read_models as read_models_task_module
from app.tasks import ticket_sla as ticket_sla_task_module


def _postgres_database_resource(dsn: str) -> Iterator[PostgresDatabase]:
    db = PostgresDatabase(dsn)
    try:
        yield db
    finally:
        db.close()


class CoreContainer(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=Settings)
    db = providers.Resource(
        _postgres_database_resource,
        dsn=settings.provided.supabase_db_url,
    )


class InfraContainer(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=Settings)
    cedar_authorizer = providers.Singleton(
        CedarAuthorizationClient,
        base_url=settings.provided.cedar_authorization_url,
    )
    ocr_provider = providers.Singleton(StubOcrProvider)
    s3_client = providers.Singleton(build_s3_client, settings=settings)


class ReposContainer(containers.DeclarativeContainer):
    db = providers.Dependency()

    claim = providers.Object(claim_repo)
    activity = providers.Object(activity_repo)
    application_messages = providers.Factory(ApplicationMessagesRepository, db=db)
    applications = providers.Factory(ApplicationsRepository, db=db)
    archive_queries = providers.Factory(ArchiveQueriesRepository, db=db)
    archive_runs = providers.Factory(ArchiveRunsRepository, db=db)
    audit = providers.Object(audit_repo)
    authority = providers.Factory(AuthorityRepository, db=db)
    chapter_roles = providers.Factory(ChapterRolesRepository, db=db)
    chapter_templates = providers.Factory(ChapterTemplatesRepository, db=db)
    chapter_transitions = providers.Factory(ChapterTransitionsRepository, db=db)
    chapters = providers.Factory(ChaptersRepository, db=db)
    compliance = providers.Object(compliance_repo)
    deferred_effects = providers.Object(deferred_effects_repo)
    forms = providers.Factory(FormsRepository, db=db)
    members = providers.Factory(MembersRepository, db=db)
    mutations = providers.Object(mutations_repo)
    notification_events = providers.Object(notification_events_repo)
    notifications = providers.Object(notifications_repo)
    permissions = providers.Factory(PermissionsRepository, db=db)
    policies = providers.Factory(PoliciesRepository, db=db)
    public_chapters = providers.Factory(PublicChaptersRepository, db=db)
    read_models = providers.Object(read_models_repo)
    roster = providers.Factory(RosterRepository, db=db)
    scheduler = providers.Object(scheduler_repo)
    ticket_categories = providers.Factory(TicketCategoriesRepository, db=db)
    ticket_messages = providers.Factory(TicketMessagesRepository, db=db)
    ticket_sla = providers.Factory(TicketSlaRepository, db=db)
    tickets = providers.Factory(TicketsRepository, db=db)
    trust = providers.Factory(TrustRepository, db=db)
    web = providers.Object(web_repo)


class ServicesContainer(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()
    infra = providers.DependenciesContainer()
    repos = providers.DependenciesContainer()
    mutations_callable = providers.Dependency()

    applicant_discord_auth = providers.Object(applicant_discord_auth_service)
    application_public_submit_notifications = providers.Object(
        application_public_submit_notifications_service,
    )
    application_notification_emitter = providers.Callable(
        emit_application_public_submitted_event,
        db=core.db,
    )
    file_upload = providers.Factory(
        FileUploadService,
        s3_client=infra.s3_client,
        settings=core.settings,
    )
    forms = providers.Factory(
        FormsService,
        forms_repo=repos.forms,
        mutations_callable=mutations_callable.provider,
    )
    public_chapters = providers.Factory(
        PublicChaptersService,
        public_chapters_repo=repos.public_chapters,
    )
    application_messages = providers.Factory(
        ApplicationMessagesService,
        applications_repo=repos.applications,
        application_messages_repo=repos.application_messages,
        mutations_callable=mutations_callable.provider,
    )
    application_transcript = providers.Factory(
        ApplicationTranscriptService,
        applications_repo=repos.applications,
        application_messages_service=application_messages,
    )
    applications = providers.Factory(
        ApplicationsService,
        applications_repo=repos.applications,
        application_messages_repo=repos.application_messages,
        forms_repo=repos.forms,
        public_chapters_repo=repos.public_chapters,
        members_repo=repos.members,
        file_upload_service=file_upload,
        mutations_callable=mutations_callable.provider,
        notification_emitter=application_notification_emitter.provider,
    )
    audit = providers.Object(audit_service)
    audit_overrides = providers.Object(audit_overrides_service)
    audit_queries = providers.Object(audit_queries_service)
    authority = providers.Factory(
        AuthorityService,
        authority_repo=repos.authority,
        members_repo=repos.members,
        roster_repo=repos.roster,
        chapter_roles_repo=repos.chapter_roles,
        applications_repo=repos.applications,
        tickets_repo=repos.tickets,
        mutations_callable=mutations_callable.provider,
    )
    authorization = providers.Object(authorization_service)
    chapter_roles = providers.Factory(
        ChapterRolesService,
        chapter_roles_repo=repos.chapter_roles,
        mutations_callable=mutations_callable.provider,
    )
    chapter_templates = providers.Factory(
        ChapterTemplatesService,
        chapter_templates_repo=repos.chapter_templates,
        mutations_callable=mutations_callable.provider,
    )
    chapters = providers.Factory(
        ChaptersService,
        chapters_repo=repos.chapters,
        chapter_transitions_repo=repos.chapter_transitions,
        archive_queries_repo=repos.archive_queries,
        archive_runs_repo=repos.archive_runs,
        mutations_callable=mutations_callable.provider,
    )
    compliance = providers.Object(compliance_service)
    compliance_corrections = providers.Object(compliance_corrections_service)
    compliance_extraction = providers.Object(compliance_extraction_service)
    compliance_review = providers.Object(compliance_review_service)
    deferred_effects = providers.Object(deferred_effects_service)
    form_visibility = providers.Object(form_visibility_service)
    members = providers.Factory(
        MembersService,
        members_repo=repos.members,
        mutations_callable=mutations_callable.provider,
    )
    mutations = providers.Object(mutations_service)
    notification_events = providers.Object(notification_events_service)
    notifications = providers.Object(notifications_service)
    notifications_delivery = providers.Object(notifications_delivery_service)
    notifications_materialize = providers.Object(notifications_materialize_service)
    permission_reconciliation = providers.Factory(
        PermissionReconciliationService,
        permissions_repo=repos.permissions,
        mutations_callable=mutations_callable.provider,
    )
    permissions = providers.Factory(
        PermissionsService,
        permissions_repo=repos.permissions,
        mutations_callable=mutations_callable.provider,
    )
    policies = providers.Factory(
        PoliciesService,
        policies_repo=repos.policies,
        mutations_callable=mutations_callable.provider,
    )
    read_models = providers.Object(read_models_service)
    roster = providers.Factory(
        RosterService,
        roster_repo=repos.roster,
        members_repo=repos.members,
        mutations_callable=mutations_callable.provider,
    )
    scheduler = providers.Object(scheduler_service)
    ticket_categories = providers.Object(ticket_categories_service)
    ticket_messages = providers.Factory(
        TicketMessagesService,
        tickets_repo=repos.tickets,
        ticket_messages_repo=repos.ticket_messages,
    )
    tickets = providers.Factory(
        TicketsService,
        tickets_repo=repos.tickets,
        ticket_categories_repo=repos.ticket_categories,
        ticket_messages_repo=repos.ticket_messages,
        ticket_messages_service=ticket_messages,
        mutations_callable=mutations_callable.provider,
    )
    leadership_handoff_applications = providers.Factory(
        LeadershipHandoffApplicationsService,
        applications_service=applications,
        authority_service=authority,
    )
    leadership_handoff_tickets = providers.Factory(
        LeadershipHandoffTicketsService,
        tickets_service=tickets,
        authority_service=authority,
    )
    ticket_sla = providers.Factory(
        TicketSlaService,
        ticket_sla_repo=repos.ticket_sla,
        tickets_service=tickets,
        notification_events_module=providers.Object(notification_events_service),
    )
    trust = providers.Factory(
        TrustService,
        trust_repo=repos.trust,
        members_repo=repos.members,
        policies_repo=repos.policies,
        mutations_callable=mutations_callable.provider,
    )
    web = providers.Object(web_service)


class TasksContainer(containers.DeclarativeContainer):
    db = providers.Dependency()
    archive = providers.Object(archive_task_module)
    compliance = providers.Object(compliance_task_module)
    notifications_deliver = providers.Object(notifications_deliver_task_module)
    notifications_materialize = providers.Object(notifications_materialize_task_module)
    permission_expiry = providers.Object(permission_expiry_task_module)
    read_models = providers.Object(read_models_task_module)
    ticket_sla = providers.Object(ticket_sla_task_module)
    scheduler_loop = providers.Singleton(
        build_scheduler_loop, db, worker_id="api:primary"
    )
    configure_task_runtime = providers.Object(configure_task_runtime)


class ApiContainer(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=Settings)

    core = providers.Container(CoreContainer, settings=settings)
    infra = providers.Container(InfraContainer, settings=settings)
    repos = providers.Container(ReposContainer, db=core.db)
    services = providers.Container(
        ServicesContainer,
        core=core,
        infra=infra,
        repos=repos,
        mutations_callable=providers.Callable(mutate_entity, db=core.db),
    )
    tasks = providers.Container(TasksContainer, db=core.db)
