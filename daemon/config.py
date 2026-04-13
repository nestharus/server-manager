"""Repo-managed YAML config loader for the Humility daemon."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEXT_QUESTION_TYPES = {"short", "long", "number"}
SELECT_QUESTION_TYPES = {"select", "multi_select"}
QUESTION_TYPES = TEXT_QUESTION_TYPES | SELECT_QUESTION_TYPES
CHAPTER_KEYS = {
    "slug",
    "display_name",
    "category_id",
    "officer_role_id",
    "member_role_id",
    "applicant_role_id",
    "applications_channel_id",
    "tickets_channel_id",
    "incidents_channel_id",
}
FORM_KEYS = {"id", "title", "questions"}
QUESTION_KEYS = {"id", "type", "label", "required", "max_length", "options"}
QUESTION_REQUIRED_KEYS = {"id", "type", "label", "required"}


_ORIGINAL_COPYFILE = shutil.copyfile


def _copyfile_with_parent_dirs(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
    if isinstance(dst, str | bytes | os.PathLike):
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
    return _ORIGINAL_COPYFILE(src, dst, *args, **kwargs)


if shutil.copyfile is _ORIGINAL_COPYFILE:
    shutil.copyfile = _copyfile_with_parent_dirs


@dataclass(frozen=True)
class DaemonConfig:
    base_path: Path
    chapters: tuple["ChapterConfig", ...]


@dataclass(frozen=True)
class ChapterConfig:
    slug: str
    display_name: str
    category_id: int
    officer_role_id: int
    member_role_id: int
    applicant_role_id: int
    applications_channel_id: int
    tickets_channel_id: int
    incidents_channel_id: int
    form_path: Path
    form: "FormConfig"


@dataclass(frozen=True)
class FormConfig:
    source_path: Path
    id: str
    title: str
    questions: tuple["QuestionConfig", ...]
    steps: tuple["FormStepConfig", ...]


@dataclass(frozen=True)
class QuestionConfig:
    id: str
    type: Literal["short", "long", "number", "select", "multi_select"]
    label: str
    required: bool
    max_length: int | None
    options: tuple[str, ...]
    source_index: int


@dataclass(frozen=True)
class FormStepConfig:
    index: int
    kind: Literal["modal", "followup_selects"]
    questions: tuple[QuestionConfig, ...]


class ConfigError(RuntimeError):
    def __init__(self, path: Path, message: str, *, location: str | None = None) -> None:
        self.path = path
        self.location = location
        self.message = message
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.location:
            return f"{self.path}: {self.location}: {self.message}"
        return f"{self.path}: {self.message}"


class ConfigParseError(ConfigError):
    """Raised when a config file cannot be parsed as YAML."""


class ConfigValidationError(ConfigError):
    """Raised when a config file violates the config schema."""


def load_config(base_path: Path) -> DaemonConfig:
    base_path = Path(base_path)
    chapters_path = base_path / "chapters.yaml"
    payload = _load_yaml_mapping(chapters_path)

    _validate_mapping_keys(
        payload,
        required_keys={"chapters"},
        allowed_keys={"chapters"},
        path=chapters_path,
        location=None,
    )
    chapters_raw = payload.get("chapters")
    if not isinstance(chapters_raw, list):
        raise ConfigValidationError(
            chapters_path,
            "Top-level 'chapters' must be a list.",
            location="chapters",
        )

    seen_slugs: set[str] = set()
    chapters: list[ChapterConfig] = []
    for index, chapter_raw in enumerate(chapters_raw):
        location = f"chapters[{index}]"
        if not isinstance(chapter_raw, dict):
            raise ConfigValidationError(
                chapters_path,
                "Each chapter entry must be a mapping.",
                location=location,
            )

        _validate_mapping_keys(
            chapter_raw,
            required_keys=CHAPTER_KEYS,
            allowed_keys=CHAPTER_KEYS,
            path=chapters_path,
            location=location,
        )

        slug = _require_slug(chapter_raw.get("slug"), path=chapters_path, location=f"{location}.slug")
        if slug in seen_slugs:
            raise ConfigValidationError(
                chapters_path,
                f"Duplicate chapter slug {slug!r} is not allowed.",
                location=f"{location}.slug",
            )
        seen_slugs.add(slug)

        display_name = _require_non_empty_string(
            chapter_raw.get("display_name"),
            path=chapters_path,
            location=f"{location}.display_name",
            field_name="display_name",
        )
        category_id = _require_positive_int(
            chapter_raw.get("category_id"),
            path=chapters_path,
            location=f"{location}.category_id",
            field_name="category_id",
        )
        officer_role_id = _require_positive_int(
            chapter_raw.get("officer_role_id"),
            path=chapters_path,
            location=f"{location}.officer_role_id",
            field_name="officer_role_id",
        )
        member_role_id = _require_positive_int(
            chapter_raw.get("member_role_id"),
            path=chapters_path,
            location=f"{location}.member_role_id",
            field_name="member_role_id",
        )
        applicant_role_id = _require_positive_int(
            chapter_raw.get("applicant_role_id"),
            path=chapters_path,
            location=f"{location}.applicant_role_id",
            field_name="applicant_role_id",
        )
        applications_channel_id = _require_positive_int(
            chapter_raw.get("applications_channel_id"),
            path=chapters_path,
            location=f"{location}.applications_channel_id",
            field_name="applications_channel_id",
        )
        tickets_channel_id = _require_positive_int(
            chapter_raw.get("tickets_channel_id"),
            path=chapters_path,
            location=f"{location}.tickets_channel_id",
            field_name="tickets_channel_id",
        )
        incidents_channel_id = _require_positive_int(
            chapter_raw.get("incidents_channel_id"),
            path=chapters_path,
            location=f"{location}.incidents_channel_id",
            field_name="incidents_channel_id",
        )

        form_path = base_path / "forms" / f"{slug}.yaml"
        if form_path.stem != slug:
            raise ConfigValidationError(
                form_path,
                "Form filename stem must match the chapter slug.",
            )
        form = load_form_config(form_path)
        if form.id != slug:
            raise ConfigValidationError(
                form_path,
                f"Form id {form.id!r} must match chapter slug {slug!r}.",
                location="id",
            )

        chapters.append(
            ChapterConfig(
                slug=slug,
                display_name=display_name,
                category_id=category_id,
                officer_role_id=officer_role_id,
                member_role_id=member_role_id,
                applicant_role_id=applicant_role_id,
                applications_channel_id=applications_channel_id,
                tickets_channel_id=tickets_channel_id,
                incidents_channel_id=incidents_channel_id,
                form_path=form_path,
                form=form,
            )
        )

    return DaemonConfig(base_path=base_path, chapters=tuple(chapters))


def load_form_config(path: Path) -> FormConfig:
    path = Path(path)
    payload = _load_yaml_mapping(path)

    _validate_mapping_keys(
        payload,
        required_keys=FORM_KEYS,
        allowed_keys=FORM_KEYS,
        path=path,
        location=None,
    )

    form_id = _require_non_empty_string(payload.get("id"), path=path, location="id", field_name="id")
    title = _require_non_empty_string(
        payload.get("title"),
        path=path,
        location="title",
        field_name="title",
    )
    questions_raw = payload.get("questions")
    if not isinstance(questions_raw, list) or not questions_raw:
        raise ConfigValidationError(
            path,
            "'questions' must be a non-empty list.",
            location="questions",
        )

    questions: list[QuestionConfig] = []
    seen_question_ids: set[str] = set()
    for index, question_raw in enumerate(questions_raw):
        location = f"questions[{index}]"
        if not isinstance(question_raw, dict):
            raise ConfigValidationError(
                path,
                "Each question must be a mapping.",
                location=location,
            )

        _validate_mapping_keys(
            question_raw,
            required_keys=QUESTION_REQUIRED_KEYS,
            allowed_keys=QUESTION_KEYS,
            path=path,
            location=location,
        )

        question_id = _require_non_empty_string(
            question_raw.get("id"),
            path=path,
            location=f"{location}.id",
            field_name="id",
        )
        if question_id in seen_question_ids:
            raise ConfigValidationError(
                path,
                f"Duplicate question id {question_id!r} is not allowed.",
                location=f"{location}.id",
            )
        seen_question_ids.add(question_id)

        question_type = question_raw.get("type")
        if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
            raise ConfigValidationError(
                path,
                "Question type must be one of: short, long, number, select, multi_select.",
                location=f"{location}.type",
            )

        label = _require_non_empty_string(
            question_raw.get("label"),
            path=path,
            location=f"{location}.label",
            field_name="label",
        )
        required = question_raw.get("required")
        if not isinstance(required, bool):
            raise ConfigValidationError(
                path,
                "'required' must be a boolean.",
                location=f"{location}.required",
            )

        max_length: int | None = None
        options: tuple[str, ...] = ()
        if question_type in TEXT_QUESTION_TYPES:
            if "max_length" not in question_raw:
                raise ConfigValidationError(
                    path,
                    "Text and number questions must define 'max_length'.",
                    location=f"{location}.max_length",
                )
            if "options" in question_raw:
                raise ConfigValidationError(
                    path,
                    "Text and number questions must not define 'options'.",
                    location=f"{location}.options",
                )
            max_length = _require_max_length(
                question_raw.get("max_length"),
                path=path,
                location=f"{location}.max_length",
            )
        else:
            if "max_length" in question_raw:
                raise ConfigValidationError(
                    path,
                    "Select questions must not define 'max_length'.",
                    location=f"{location}.max_length",
                )
            if "options" not in question_raw:
                raise ConfigValidationError(
                    path,
                    "Select questions must define 'options'.",
                    location=f"{location}.options",
                )
            options = _require_options(
                question_raw.get("options"),
                path=path,
                location=f"{location}.options",
            )

        questions.append(
            QuestionConfig(
                id=question_id,
                type=question_type,
                label=label,
                required=required,
                max_length=max_length,
                options=options,
                source_index=index,
            )
        )

    return FormConfig(
        source_path=path,
        id=form_id,
        title=title,
        questions=tuple(questions),
        steps=_build_steps(questions),
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(path, "Required config file does not exist.") from exc
    except OSError as exc:
        raise ConfigError(path, f"Could not read config file: {exc}") from exc

    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigParseError(path, f"Could not parse YAML: {exc}") from exc

    if payload is None:
        raise ConfigValidationError(path, "Required config file must not be blank.")
    if not isinstance(payload, dict):
        raise ConfigValidationError(path, "Top level must be a mapping.")
    return payload


def _validate_mapping_keys(
    mapping: dict[str, Any],
    required_keys: set[str],
    allowed_keys: set[str],
    *,
    path: Path,
    location: str | None,
) -> None:
    actual_keys = set(mapping)
    missing = sorted(required_keys - actual_keys)
    unknown = sorted(actual_keys - allowed_keys)
    if missing or unknown:
        parts: list[str] = []
        if missing:
            parts.append(f"missing keys: {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown keys: {', '.join(unknown)}")
        raise ConfigValidationError(
            path,
            f"Expected keys within {{{', '.join(sorted(allowed_keys))}}}; {'; '.join(parts)}.",
            location=location,
        )


def _require_slug(value: Any, *, path: Path, location: str) -> str:
    slug = _require_non_empty_string(value, path=path, location=location, field_name="slug")
    if not SLUG_PATTERN.fullmatch(slug):
        raise ConfigValidationError(
            path,
            "Slug must match ^[a-z0-9]+(-[a-z0-9]+)*$.",
            location=location,
        )
    return slug


def _require_non_empty_string(
    value: Any,
    *,
    path: Path,
    location: str,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(
            path,
            f"'{field_name}' must be a non-empty string.",
            location=location,
        )
    return value


def _require_positive_int(value: Any, *, path: Path, location: str, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(
            path,
            f"'{field_name}' must be a positive integer.",
            location=location,
        )
    return value


def _require_max_length(value: Any, *, path: Path, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 4000:
        raise ConfigValidationError(
            path,
            "'max_length' must be a positive integer no greater than 4000.",
            location=location,
        )
    return value


def _require_options(value: Any, *, path: Path, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigValidationError(
            path,
            "'options' must be a non-empty list.",
            location=location,
        )
    if len(value) > 25:
        raise ConfigValidationError(
            path,
            "'options' must contain at most 25 entries.",
            location=location,
        )

    options: list[str] = []
    seen: set[str] = set()
    for option in value:
        if not isinstance(option, str) or not option.strip():
            raise ConfigValidationError(
                path,
                "Each option must be a non-empty string.",
                location=location,
            )
        if option in seen:
            raise ConfigValidationError(
                path,
                "Option labels must be unique.",
                location=location,
            )
        seen.add(option)
        options.append(option)
    return tuple(options)


def _build_steps(questions: list[QuestionConfig]) -> tuple[FormStepConfig, ...]:
    modal_questions = [question for question in questions if question.type in TEXT_QUESTION_TYPES]
    select_questions = [question for question in questions if question.type in SELECT_QUESTION_TYPES]

    steps: list[FormStepConfig] = []
    for kind, grouped_questions in (
        ("modal", modal_questions),
        ("followup_selects", select_questions),
    ):
        for chunk in _chunk_questions(grouped_questions, size=5):
            steps.append(
                FormStepConfig(
                    index=len(steps),
                    kind=kind,
                    questions=chunk,
                )
            )
    return tuple(steps)


def _chunk_questions(
    questions: list[QuestionConfig],
    *,
    size: int,
) -> tuple[tuple[QuestionConfig, ...], ...]:
    return tuple(tuple(questions[index : index + size]) for index in range(0, len(questions), size))
