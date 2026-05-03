from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from botocore.exceptions import ClientError

from app.contracts.applications import (
    ApplicationFormField,
    FileUploadUrlRequest,
    FormFieldFile,
    InvalidApplicationResponseError,
)
from app.core.settings import Settings


class S3Client(Protocol):
    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str: ...

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...


def build_s3_client(settings: Settings) -> S3Client:
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
    )


class FileUploadService:
    def __init__(self, s3_client: S3Client, settings: Settings) -> None:
        self._s3_client = s3_client
        self._settings = settings

    def _bucket(self) -> str:
        return self._settings.s3_bucket

    def generate_presigned_put_url(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
        expires_in_seconds: int = 600,
    ) -> tuple[str, datetime]:
        upload_url = self._s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket(),
                "Key": object_key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=expires_in_seconds,
        )
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        return upload_url, expires_at

    def head_object(self, object_key: str) -> tuple[int, str]:
        try:
            metadata = self._s3_client.head_object(
                Bucket=self._bucket(),
                Key=object_key,
            )
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", "Unknown"))
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                raise InvalidApplicationResponseError(
                    "file upload object was not found"
                ) from error
            raise InvalidApplicationResponseError(
                f"file upload object head failed: {error_code}"
            ) from error
        try:
            return int(metadata["ContentLength"]), str(metadata["ContentType"])
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidApplicationResponseError(
                "file upload object metadata is invalid"
            ) from error

    def validate_upload_request(
        self,
        *,
        fields: list[ApplicationFormField],
        request: FileUploadUrlRequest,
        visibility: dict[str, bool],
    ) -> tuple[FormFieldFile, UUID]:
        field = next(
            (candidate for candidate in fields if candidate.id == request.field_id),
            None,
        )
        if field is None:
            raise InvalidApplicationResponseError(
                f"{request.field_id} is not a configured field"
            )
        if field.type != "file":
            raise InvalidApplicationResponseError(f"{request.field_id} is not a file field")
        if not visibility.get(request.field_id, False):
            raise InvalidApplicationResponseError(f"{request.field_id} is not visible")
        if request.content_type not in field.accept:
            raise InvalidApplicationResponseError(
                f"{request.field_id} content_type is not accepted"
            )
        if request.size_bytes <= 0 or request.size_bytes > field.max_size_bytes:
            raise InvalidApplicationResponseError(
                f"{request.field_id} size exceeds max_size_bytes"
            )
        return field, reserve_application_id()


def reserve_application_id() -> UUID:
    return uuid4()


def build_object_key(application_id: UUID, field_id: str) -> str:
    return f"applications/{application_id}/{field_id}/{uuid4()}"


def parse_object_key(object_key: str) -> tuple[UUID, str, UUID]:
    parts = object_key.split("/")
    if len(parts) != 4 or parts[0] != "applications":
        raise InvalidApplicationResponseError("file upload object key is malformed")
    try:
        application_id = UUID(parts[1])
        object_id = UUID(parts[3])
    except ValueError as error:
        raise InvalidApplicationResponseError("file upload object key is malformed") from error
    field_id = parts[2]
    if not field_id:
        raise InvalidApplicationResponseError("file upload object key is malformed")
    return application_id, field_id, object_id


__all__ = [
    "build_object_key",
    "build_s3_client",
    "FileUploadService",
    "parse_object_key",
    "reserve_application_id",
    "S3Client",
]
