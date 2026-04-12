"""Pydantic contracts (request/response schemas).

These are the API boundary — what the outside world sees. Internal
service/repository types may differ. Contracts use VersionedMixin
for entities that support optimistic locking (from java-interview-setup
pattern).
"""
