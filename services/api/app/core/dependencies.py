"""Dependency providers for API layers."""

from __future__ import annotations

from fastapi import Depends, Request

from app.repositories.chapter_repository import AbstractChapterRepository
from app.services.chapter_service import AuditService, ChapterService


def get_chapter_repository(request: Request) -> AbstractChapterRepository:
    return request.app.state.chapter_repository


def get_audit_service(request: Request) -> AuditService:
    return request.app.state.audit_service


def get_chapter_service(
    repository: AbstractChapterRepository = Depends(get_chapter_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> ChapterService:
    return ChapterService(repository=repository, audit_service=audit_service)
