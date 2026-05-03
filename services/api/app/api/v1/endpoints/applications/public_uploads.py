from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request

from app.contracts.applications import (
    FileUploadUrlRequest,
    FileUploadUrlResponse,
    FormDefinitionNotFoundError,
)
from app.core.container import ApiContainer
from app.core.settings import Settings
from app.infrastructure.authz import CedarAuthorizationClient
from app.services.applicant_discord_auth import verify_applicant_receipt
from app.services.applications import _APPLICATION_FORM_FIELD_ADAPTER
from app.services.authorization import authorize_public_intake
from app.services.file_upload import FileUploadService, build_object_key
from app.services.form_visibility import evaluate_visibility
from app.services.forms import FormsService

from ._shared import raise_known_application_error


router = APIRouter(prefix="/api/v1/public/applications")


@router.post(
    "/upload-url",
    response_model=FileUploadUrlResponse,
    status_code=HTTPStatus.OK,
)
@inject
async def request_upload_url_endpoint(
    body: FileUploadUrlRequest,
    request: Request,
    settings: Settings = Depends(Provide[ApiContainer.core.settings]),
    cedar_authorizer: CedarAuthorizationClient = Depends(
        Provide[ApiContainer.infra.cedar_authorizer]
    ),
    forms_service: FormsService = Depends(Provide[ApiContainer.services.forms]),
    file_upload_service: FileUploadService = Depends(
        Provide[ApiContainer.services.file_upload]
    ),
) -> FileUploadUrlResponse:
    identity = verify_applicant_receipt(
        request,
        signing_key=settings.applicant_receipt_signing_key.get_secret_value(),
    )
    await authorize_public_intake(request, cedar_authorizer, settings)
    del identity
    try:
        form_row = forms_service.get_form_by_id(body.form_definition_id)
        if form_row is None:
            raise FormDefinitionNotFoundError(form_definition_id=body.form_definition_id)
        fields = [
            _APPLICATION_FORM_FIELD_ADAPTER.validate_python(raw)
            for raw in form_row["fields"]
        ]
        visibility = evaluate_visibility(fields, {})
        _field, application_id = file_upload_service.validate_upload_request(
            fields=fields,
            request=body,
            visibility=visibility,
        )
        object_key = build_object_key(application_id, body.field_id)
        upload_url, expires_at = file_upload_service.generate_presigned_put_url(
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
