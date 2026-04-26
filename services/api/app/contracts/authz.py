from __future__ import annotations

from pydantic import BaseModel, Field


class ProtectedAuthzRead(BaseModel):
    subject: str
    action: str
    resource: str
    decision: str = Field(pattern="^Allow$")


class CedarAuthorizationDecision(BaseModel):
    decision: str

