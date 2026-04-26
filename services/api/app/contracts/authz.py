from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProtectedAuthzRead(BaseModel):
    subject: str
    action: str
    resource: str
    decision: Literal["Allow"] = "Allow"


class AuthzErrorDetail(BaseModel):
    code: str
    message: str


class CedarAuthorizationDecision(BaseModel):
    decision: Literal["Allow", "Deny"]
