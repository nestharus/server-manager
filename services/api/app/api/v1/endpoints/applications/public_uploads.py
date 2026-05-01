from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from app.contracts.applications import (
    FileUploadUrlRequest,
    FileUploadUrlResponse,
    FormDefinitionNotFoundError,
)
from app.repositories.db import PostgresDatabase
from app.services import file_upload
from app.services.applicant_discord_auth import (
    DiscordIdentity,
    verify_applicant_receipt,
)
from app.services.applications import _APPLICATION_FORM_FIELD_ADAPTER
from app.services.authorization import authorize_public_intake
from app.services.form_visibility import evaluate_visibility

from ._shared import get_db, raise_known_application_error


router = APIRouter(prefix="/api/v1/public/applications")


def _get_current_form_by_id(
    db: PostgresDatabase,
    form_definition_id: Any,
) -> dict[str, Any] | None:
    with db.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id,
                   scope_kind,
                   scope_id,
                   version,
                   name,
                   target_type,
                   fields,
                   routing_rules,
                   status,
                   published_by_kind,
                   published_by_id,
                   published_at,
                   archived_at,
                   created_at
            FROM form_definitions
            WHERE id = %s
              AND status = 'current'
            LIMIT 1
            """,
            (form_definition_id,),
        ).fetchone()


@router.post(
    "/upload-url",
    response_model=FileUploadUrlResponse,
    status_code=HTTPStatus.OK,
)
async def request_upload_url_endpoint(
    body: FileUploadUrlRequest,
    identity: DiscordIdentity = Depends(verify_applicant_receipt),
    db: PostgresDatabase = Depends(get_db),
    _authz: None = Depends(authorize_public_intake),
) -> FileUploadUrlResponse:
    del identity
    try:
        form_row = _get_current_form_by_id(db, body.form_definition_id)
        if form_row is None:
            raise FormDefinitionNotFoundError(form_definition_id=body.form_definition_id)
        fields = [
            _APPLICATION_FORM_FIELD_ADAPTER.validate_python(raw)
            for raw in form_row["fields"]
        ]
        visibility = evaluate_visibility(fields, {})
        _field, application_id = file_upload.validate_upload_request(
            fields=fields,
            request=body,
            visibility=visibility,
        )
        object_key = file_upload.build_object_key(application_id, body.field_id)
        upload_url, expires_at = file_upload.generate_presigned_put_url(
            object_key=object_key,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    except Exception as error:
        raise_known_application_error(error)
    return FileUploadUrlResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_at=expires_at,
    )
