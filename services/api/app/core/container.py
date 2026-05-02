from __future__ import annotations

from collections.abc import Iterator

from dependency_injector import containers, providers

from app.core.settings import Settings
from app.infrastructure.authz import CedarAuthorizationClient
from app.infrastructure.ocr import StubOcrProvider
from app.repositories import _claim as claim_repo
from app.repositories import activity as activity_repo
from app.repositories import application_messages as application_messages_repo
from app.repositories import applications as applications_repo
from app.repositories import archive_queries as archive_queries_repo
from app.repositories import archive_runs as archive_runs_repo
from app.repositories import audit as audit_repo
from app.repositories import authority as authority_repo
from app.repositories import chapter_roles as chapter_roles_repo
from app.repositories import chapter_templates as chapter_templates_repo
from app.repositories import chapter_transitions as chapter_transitions_repo
from app.repositories import chapters as chapters_repo
from app.repositories import compliance as compliance_repo
from app.repositories import deferred_effects as deferred_effects_repo
from app.repositories import forms as forms_repo
from app.repositories import members as members_repo
from app.repositories import mutations as mutations_repo
from app.repositories import notification_events as notification_events_repo
from app.repositories import notifications as notifications_repo
from app.repositories import permissions as permissions_repo
from app.repositories import policies as policies_repo
from app.repositories import public_chapters as public_chapters_repo
from app.repositories import read_models as read_models_repo
from app.repositories import roster as roster_repo
from app.repositories import scheduler as scheduler_repo
from app.repositories import ticket_categories as ticket_categories_repo
from app.repositories import ticket_messages as ticket_messages_repo
from app.repositories import ticket_sla as ticket_sla_repo
from app.repositories import tickets as tickets_repo
from app.repositories import trust as trust_repo
from app.repositories import web as web_repo
from app.repositories.db import PostgresDatabase
from app.services import applicant_discord_auth as applicant_discord_auth_service
from app.services import application_messages as application_messages_service
from app.services import (
    application_public_submit_notifications
    as application_public_submit_notifications_service,
)
from app.services import application_transcript as application_transcript_service
from app.services import applications as applications_service
from app.services import audit as audit_service
from app.services import audit_overrides as audit_overrides_service
from app.services import audit_queries as audit_queries_service
from app.services import authority as authority_service
from app.services import authorization as authorization_service
from app.services import chapter_roles as chapter_roles_service
from app.services import chapter_templates as chapter_templates_service
from app.services import chapters as chapters_service
from app.services import compliance as compliance_service
from app.services import compliance_corrections as compliance_corrections_service
from app.services import compliance_extraction as compliance_extraction_service
from app.services import compliance_review as compliance_review_service
from app.services import deferred_effects as deferred_effects_service
from app.services import file_upload as file_upload_service
from app.services import form_visibility as form_visibility_service
from app.services import forms as forms_service
from app.services import (
    leadership_handoff_applications as leadership_handoff_applications_service,
)
from app.services import leadership_handoff_tickets as leadership_handoff_tickets_service
from app.services import members as members_service
from app.services import mutations as mutations_service
from app.services import notification_events as notification_events_service
from app.services import notifications as notifications_service
from app.services import notifications_delivery as notifications_delivery_service
from app.services import notifications_materialize as notifications_materialize_service
from app.services import permission_reconciliation as permission_reconciliation_service
from app.services import permissions as permissions_service
from app.services import policies as policies_service
from app.services import public_chapters as public_chapters_service
from app.services import read_models as read_models_service
from app.services import roster as roster_service
from app.services import scheduler as scheduler_service
from app.services import ticket_categories as ticket_categories_service
from app.services import ticket_messages as ticket_messages_service
from app.services import ticket_sla as ticket_sla_service
from app.services import tickets as tickets_service
from app.services import trust as trust_service
from app.services import web as web_service
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


class ReposContainer(containers.DeclarativeContainer):
    claim = providers.Object(claim_repo)
    activity = providers.Object(activity_repo)
    application_messages = providers.Object(application_messages_repo)
    applications = providers.Object(applications_repo)
    archive_queries = providers.Object(archive_queries_repo)
    archive_runs = providers.Object(archive_runs_repo)
    audit = providers.Object(audit_repo)
    authority = providers.Object(authority_repo)
    chapter_roles = providers.Object(chapter_roles_repo)
    chapter_templates = providers.Object(chapter_templates_repo)
    chapter_transitions = providers.Object(chapter_transitions_repo)
    chapters = providers.Object(chapters_repo)
    compliance = providers.Object(compliance_repo)
    deferred_effects = providers.Object(deferred_effects_repo)
    forms = providers.Object(forms_repo)
    members = providers.Object(members_repo)
    mutations = providers.Object(mutations_repo)
    notification_events = providers.Object(notification_events_repo)
    notifications = providers.Object(notifications_repo)
    permissions = providers.Object(permissions_repo)
    policies = providers.Object(policies_repo)
    public_chapters = providers.Object(public_chapters_repo)
    read_models = providers.Object(read_models_repo)
    roster = providers.Object(roster_repo)
    scheduler = providers.Object(scheduler_repo)
    ticket_categories = providers.Object(ticket_categories_repo)
    ticket_messages = providers.Object(ticket_messages_repo)
    ticket_sla = providers.Object(ticket_sla_repo)
    tickets = providers.Object(tickets_repo)
    trust = providers.Object(trust_repo)
    web = providers.Object(web_repo)


class ServicesContainer(containers.DeclarativeContainer):
    applicant_discord_auth = providers.Object(applicant_discord_auth_service)
    application_messages = providers.Object(application_messages_service)
    application_public_submit_notifications = providers.Object(
        application_public_submit_notifications_service,
    )
    application_transcript = providers.Object(application_transcript_service)
    applications = providers.Object(applications_service)
    audit = providers.Object(audit_service)
    audit_overrides = providers.Object(audit_overrides_service)
    audit_queries = providers.Object(audit_queries_service)
    authority = providers.Object(authority_service)
    authorization = providers.Object(authorization_service)
    chapter_roles = providers.Object(chapter_roles_service)
    chapter_templates = providers.Object(chapter_templates_service)
    chapters = providers.Object(chapters_service)
    compliance = providers.Object(compliance_service)
    compliance_corrections = providers.Object(compliance_corrections_service)
    compliance_extraction = providers.Object(compliance_extraction_service)
    compliance_review = providers.Object(compliance_review_service)
    deferred_effects = providers.Object(deferred_effects_service)
    file_upload = providers.Object(file_upload_service)
    form_visibility = providers.Object(form_visibility_service)
    forms = providers.Object(forms_service)
    leadership_handoff_applications = providers.Object(
        leadership_handoff_applications_service,
    )
    leadership_handoff_tickets = providers.Object(leadership_handoff_tickets_service)
    members = providers.Object(members_service)
    mutations = providers.Object(mutations_service)
    notification_events = providers.Object(notification_events_service)
    notifications = providers.Object(notifications_service)
    notifications_delivery = providers.Object(notifications_delivery_service)
    notifications_materialize = providers.Object(notifications_materialize_service)
    permission_reconciliation = providers.Object(permission_reconciliation_service)
    permissions = providers.Object(permissions_service)
    policies = providers.Object(policies_service)
    public_chapters = providers.Object(public_chapters_service)
    read_models = providers.Object(read_models_service)
    roster = providers.Object(roster_service)
    scheduler = providers.Object(scheduler_service)
    ticket_categories = providers.Object(ticket_categories_service)
    ticket_messages = providers.Object(ticket_messages_service)
    ticket_sla = providers.Object(ticket_sla_service)
    tickets = providers.Object(tickets_service)
    trust = providers.Object(trust_service)
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
    scheduler_loop = providers.Singleton(build_scheduler_loop, db, worker_id="api:primary")
    configure_task_runtime = providers.Object(configure_task_runtime)


class ApiContainer(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=Settings)

    core = providers.Container(CoreContainer, settings=settings)
    infra = providers.Container(InfraContainer, settings=settings)
    repos = providers.Container(ReposContainer)
    services = providers.Container(ServicesContainer)
    tasks = providers.Container(TasksContainer, db=core.db)
