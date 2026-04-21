from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


ChapterState = Literal[
    "proposed",
    "provisioning",
    "active",
    "provisioning_failed",
    "archived",
]


class InvalidChapterTransitionError(Exception):
    def __init__(self, current: str, next_state: str) -> None:
        self.current = current
        self.next_state = next_state
        super().__init__(
            f"invalid chapter transition: {current!r} -> {next_state!r}"
        )


class Chapter(BaseModel):
    id: str
    state: ChapterState
    version: int = 0


TRANSITIONS: dict[ChapterState, set[ChapterState]] = {
    "proposed": {"provisioning", "archived"},
    "provisioning": {"active", "provisioning_failed"},
    "active": {"archived"},
    "provisioning_failed": {"provisioning", "archived"},
    "archived": set(),
}


def _replace_chapter(chapter: Chapter, *, state: ChapterState) -> Chapter:
    update = {"state": state, "version": chapter.version + 1}
    if hasattr(chapter, "model_copy"):
        return chapter.model_copy(update=update)
    return chapter.copy(update=update)


def transition(current: Chapter, next_state: ChapterState) -> Chapter:
    allowed_next_states = TRANSITIONS[current.state]
    if next_state not in allowed_next_states:
        raise InvalidChapterTransitionError(current.state, next_state)
    return _replace_chapter(current, state=next_state)


def run_valid_path() -> None:
    chapter = Chapter(id="chapter-alpha", state="proposed")
    print("VALID PATH")
    print(chapter)
    for next_state in ("provisioning", "active", "archived"):
        chapter = transition(chapter, next_state)  # type: ignore[arg-type]
        print(chapter)


def run_failure_retry_path() -> None:
    chapter = Chapter(id="chapter-bravo", state="proposed")
    print("\nFAILURE + RETRY PATH")
    for next_state in (
        "provisioning",
        "provisioning_failed",
        "provisioning",
        "active",
    ):
        chapter = transition(chapter, next_state)  # type: ignore[arg-type]
        print(chapter)


def run_invalid_paths() -> None:
    print("\nINVALID PATHS")
    invalid_attempts = [
        (Chapter(id="chapter-charlie", state="active"), "provisioning_failed"),
        (Chapter(id="chapter-delta", state="archived"), "active"),
    ]
    for chapter, next_state in invalid_attempts:
        try:
            transition(chapter, next_state)  # type: ignore[arg-type]
        except InvalidChapterTransitionError as error:
            print(error)


def main() -> None:
    print(f"transition_matrix={TRANSITIONS}")
    run_valid_path()
    run_failure_retry_path()
    run_invalid_paths()


if __name__ == "__main__":
    main()
