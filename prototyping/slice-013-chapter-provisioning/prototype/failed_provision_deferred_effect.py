from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from uuid import UUID, uuid4


ChapterState = Literal[
    "proposed",
    "provisioning",
    "active",
    "provisioning_failed",
    "archived",
]


class MockDiscordProvisioningError(Exception):
    def __init__(self, message: str, partial_resources: list[dict[str, Any]]) -> None:
        self.partial_resources = partial_resources
        super().__init__(message)


@dataclass
class ChapterRecord:
    id: str
    state: ChapterState
    version: int
    partial_resources: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DeferredEffectRow:
    id: UUID
    subsystem: str
    effect_type: str
    idempotency_key: str
    consequence_level: Literal["safe", "consequential"]
    precondition_state: Literal["unchecked", "valid", "invalid"]
    status: Literal["queued", "claimed", "completed", "failed", "skipped"]
    payload_json: dict[str, Any]


@dataclass
class StateChangeDraft:
    change_type: str
    payload_json: dict[str, Any]
    diff_json: dict[str, Any]


class InMemoryConnection:
    def __init__(self, db: "InMemoryDatabase") -> None:
        self.db = db
        self.chapters = deepcopy(db.chapters)
        self.deferred_effects = deepcopy(db.deferred_effects)
        self.state_changes = deepcopy(db.state_changes)
        self.connection_id = uuid4()

    def get_chapter_for_update(self, chapter_id: str) -> ChapterRecord:
        return self.chapters[chapter_id]

    def update_chapter_failed(
        self,
        chapter_id: str,
        *,
        partial_resources: list[dict[str, Any]],
    ) -> ChapterRecord:
        chapter = self.chapters[chapter_id]
        chapter.state = "provisioning_failed"
        chapter.partial_resources = partial_resources
        return chapter

    def enqueue_deferred_effect(self, row: DeferredEffectRow) -> None:
        self.deferred_effects.append(row)

    def append_state_change(self, chapter_id: str, draft: StateChangeDraft) -> None:
        self.state_changes.append(
            {
                "chapter_id": chapter_id,
                "change_type": draft.change_type,
                "payload_json": draft.payload_json,
                "diff_json": draft.diff_json,
            }
        )

    def commit(self) -> None:
        self.db.chapters = self.chapters
        self.db.deferred_effects = self.deferred_effects
        self.db.state_changes = self.state_changes


class Transaction:
    def __init__(self, db: "InMemoryDatabase") -> None:
        self.connection = InMemoryConnection(db)

    def __enter__(self) -> InMemoryConnection:
        return self.connection

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.connection.commit()


@dataclass
class InMemoryDatabase:
    chapters: dict[str, ChapterRecord] = field(default_factory=dict)
    deferred_effects: list[DeferredEffectRow] = field(default_factory=list)
    state_changes: list[dict[str, Any]] = field(default_factory=list)

    def transaction(self) -> Transaction:
        return Transaction(self)


def mutate_entity(
    *,
    db: InMemoryDatabase,
    chapter_id: str,
    expected_version: int,
    mutate_projection: Callable[[InMemoryConnection], StateChangeDraft],
) -> int:
    with db.transaction() as connection:
        chapter = connection.get_chapter_for_update(chapter_id)
        if chapter.version != expected_version:
            raise RuntimeError(
                f"stale chapter: expected={expected_version} current={chapter.version}"
            )

        draft = mutate_projection(connection)
        chapter.version += 1
        connection.append_state_change(chapter_id, draft)
        return chapter.version


def discord_provisioning_call() -> None:
    partial_resources = [
        {"kind": "category", "id": 111, "name": "alpha-chapter"},
        {"kind": "role", "id": 222, "name": "alpha-officer"},
    ]
    raise MockDiscordProvisioningError(
        "Discord create_role failed after partial provisioning",
        partial_resources=partial_resources,
    )


def fail_chapter_and_enqueue_cleanup(
    connection: InMemoryConnection,
    *,
    chapter_id: str,
    fail_after_enqueue: bool = False,
) -> StateChangeDraft:
    chapter_before = deepcopy(connection.get_chapter_for_update(chapter_id))
    try:
        discord_provisioning_call()
    except MockDiscordProvisioningError as error:
        row = DeferredEffectRow(
            id=uuid4(),
            subsystem="discord",
            effect_type="chapter_provisioning_cleanup",
            idempotency_key=f"chapter:{chapter_id}:provisioning-cleanup:v{chapter_before.version}",
            consequence_level="consequential",
            precondition_state="unchecked",
            status="queued",
            payload_json={
                "chapter_id": chapter_id,
                "partial_resources": error.partial_resources,
            },
        )
        connection.enqueue_deferred_effect(row)

        if fail_after_enqueue:
            raise RuntimeError("simulated crash after effect insert before commit")

        chapter_after = connection.update_chapter_failed(
            chapter_id,
            partial_resources=error.partial_resources,
        )
        return StateChangeDraft(
            change_type="chapter.provisioning_failed",
            payload_json={
                "id": chapter_after.id,
                "state": chapter_after.state,
                "partial_resources": chapter_after.partial_resources,
            },
            diff_json={
                "state": {
                    "old": chapter_before.state,
                    "new": chapter_after.state,
                },
                "partial_resources": {
                    "old": chapter_before.partial_resources,
                    "new": chapter_after.partial_resources,
                },
            },
        )

    raise RuntimeError("prototype expected Discord provisioning to fail")


def seed_db() -> InMemoryDatabase:
    return InMemoryDatabase(
        chapters={
            "chapter-alpha": ChapterRecord(
                id="chapter-alpha",
                state="provisioning",
                version=7,
            )
        }
    )


def show_successful_atomic_failure_write() -> None:
    db = seed_db()
    print("BEFORE")
    print(db.chapters["chapter-alpha"])
    print(f"deferred_effects={db.deferred_effects}")

    new_version = mutate_entity(
        db=db,
        chapter_id="chapter-alpha",
        expected_version=7,
        mutate_projection=lambda connection: fail_chapter_and_enqueue_cleanup(
            connection,
            chapter_id="chapter-alpha",
        ),
    )

    print("\nAFTER COMMIT")
    print(f"new_version={new_version}")
    print(db.chapters["chapter-alpha"])
    print(db.deferred_effects[0])
    print(db.state_changes[0])


def show_rollback_proof() -> None:
    db = seed_db()
    try:
        mutate_entity(
            db=db,
            chapter_id="chapter-alpha",
            expected_version=7,
            mutate_projection=lambda connection: fail_chapter_and_enqueue_cleanup(
                connection,
                chapter_id="chapter-alpha",
                fail_after_enqueue=True,
            ),
        )
    except RuntimeError as error:
        print("\nROLLBACK PROOF")
        print(error)
        print(db.chapters["chapter-alpha"])
        print(f"deferred_effects={db.deferred_effects}")
        print(f"state_changes={db.state_changes}")


def main() -> None:
    show_successful_atomic_failure_write()
    show_rollback_proof()


if __name__ == "__main__":
    main()
