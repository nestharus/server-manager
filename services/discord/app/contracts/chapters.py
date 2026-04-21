from __future__ import annotations


class ChapterProvisioningError(Exception):
    def __init__(self, *, step: str, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"{step}: {reason}")


__all__ = [
    "ChapterProvisioningError",
]
