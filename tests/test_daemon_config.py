import importlib
import shutil
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest
import yaml


OMIT = object()
SAMPLE_FORM_PATH = Path(__file__).resolve().parents[1] / "forms" / "dark-nemesis.yaml"


def import_config_module():
    try:
        return importlib.import_module("daemon.config")
    except Exception as exc:  # pragma: no cover - import failures should fail loudly
        pytest.fail(f"Could not import daemon.config: {exc!r}")


@pytest.fixture
def config_module():
    return import_config_module()


def write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_chapter(slug="dark-nemesis", **overrides):
    chapter = {
        "slug": slug,
        "display_name": "Dark Nemesis",
        "category_id": 101,
        "officer_role_id": 102,
        "member_role_id": 103,
        "applicant_role_id": 104,
        "applications_channel_id": 105,
        "tickets_channel_id": 106,
        "incidents_channel_id": 107,
    }
    chapter.update(overrides)
    return chapter


def make_question(question_id, question_type, **overrides):
    question = {
        "id": question_id,
        "type": question_type,
        "label": f"Label for {question_id}",
        "required": True,
    }
    if question_type in {"short", "long", "number"}:
        question["max_length"] = 100
    else:
        question["options"] = ["Option A", "Option B"]

    for key, value in overrides.items():
        if value is OMIT:
            question.pop(key, None)
        else:
            question[key] = value

    return question


def make_form(*questions, form_id="dark-nemesis", title="Dark Nemesis Form", **overrides):
    form = {
        "id": form_id,
        "title": title,
        "questions": list(questions),
    }
    form.update(overrides)
    return form


def write_project(tmp_path, *, chapters, forms=None):
    write_yaml(tmp_path / "chapters.yaml", {"chapters": chapters})
    for slug, form in (forms or {}).items():
        write_yaml(tmp_path / "forms" / f"{slug}.yaml", form)


def assert_error_context(excinfo, *, path, location=None):
    message = str(excinfo.value)
    assert str(path) in message
    if location is not None:
        assert location in message


def test_public_api_matches_contract(config_module):
    for name in (
        "DaemonConfig",
        "ChapterConfig",
        "FormConfig",
        "QuestionConfig",
        "FormStepConfig",
        "ConfigError",
        "ConfigParseError",
        "ConfigValidationError",
        "load_config",
        "load_form_config",
    ):
        assert hasattr(config_module, name)

    assert is_dataclass(config_module.DaemonConfig)
    assert is_dataclass(config_module.ChapterConfig)
    assert is_dataclass(config_module.FormConfig)
    assert is_dataclass(config_module.QuestionConfig)
    assert is_dataclass(config_module.FormStepConfig)

    assert issubclass(config_module.ConfigParseError, config_module.ConfigError)
    assert issubclass(config_module.ConfigValidationError, config_module.ConfigError)


def test_load_form_config_real_form_builds_immutable_step_plan(config_module):
    form = config_module.load_form_config(SAMPLE_FORM_PATH)

    assert isinstance(form, config_module.FormConfig)
    assert form.source_path == SAMPLE_FORM_PATH
    assert form.id == "dark-nemesis"
    assert form.title == "Dark Nemesis Chapter Application"
    assert isinstance(form.questions, tuple)
    assert isinstance(form.steps, tuple)

    question_ids = [question.id for question in form.questions]
    assert question_ids == [
        "in_game_name",
        "timezone",
        "daily_events",
        "hours_per_day",
        "launch_budget_usd",
        "monthly_budget_usd",
        "pvp_mmorpg_experience",
    ]
    assert [question.source_index for question in form.questions] == list(range(7))

    first_question = form.questions[0]
    assert isinstance(first_question, config_module.QuestionConfig)
    assert first_question.type == "short"
    assert first_question.max_length == 128
    assert first_question.options == ()

    timezone = form.questions[1]
    assert timezone.type == "select"
    assert timezone.max_length is None
    assert isinstance(timezone.options, tuple)
    assert len(timezone.options) == 25
    assert timezone.options[0] == "UTC-11:00"
    assert timezone.options[-1] == "UTC+13:00"

    assert [step.index for step in form.steps] == [0, 1]
    assert [step.kind for step in form.steps] == ["modal", "followup_selects"]
    assert all(isinstance(step.questions, tuple) for step in form.steps)
    assert [[question.id for question in step.questions] for step in form.steps] == [
        [
            "in_game_name",
            "hours_per_day",
            "launch_budget_usd",
            "monthly_budget_usd",
            "pvp_mmorpg_experience",
        ],
        ["timezone", "daily_events"],
    ]

    with pytest.raises(FrozenInstanceError):
        form.title = "Other title"
    with pytest.raises(FrozenInstanceError):
        first_question.label = "Other label"


def test_load_config_allows_empty_chapters(config_module, tmp_path):
    write_project(tmp_path, chapters=[])

    config = config_module.load_config(tmp_path)

    assert isinstance(config, config_module.DaemonConfig)
    assert config.base_path == tmp_path
    assert config.chapters == ()


def test_load_config_resolves_form_path_and_embeds_loaded_form(config_module, tmp_path):
    write_project(tmp_path, chapters=[make_chapter()])
    shutil.copyfile(SAMPLE_FORM_PATH, tmp_path / "forms" / "dark-nemesis.yaml")

    config = config_module.load_config(tmp_path)

    assert isinstance(config.chapters, tuple)
    assert len(config.chapters) == 1

    chapter = config.chapters[0]
    assert isinstance(chapter, config_module.ChapterConfig)
    assert chapter.slug == "dark-nemesis"
    assert chapter.display_name == "Dark Nemesis"
    assert chapter.category_id == 101
    assert chapter.officer_role_id == 102
    assert chapter.member_role_id == 103
    assert chapter.applicant_role_id == 104
    assert chapter.applications_channel_id == 105
    assert chapter.tickets_channel_id == 106
    assert chapter.incidents_channel_id == 107
    assert chapter.form_path == tmp_path / "forms" / "dark-nemesis.yaml"
    assert isinstance(chapter.form, config_module.FormConfig)
    assert chapter.form.source_path == chapter.form_path
    assert chapter.form.id == chapter.slug

    with pytest.raises(FrozenInstanceError):
        chapter.slug = "other-slug"


def test_load_config_missing_chapters_file_raises_clear_error(config_module, tmp_path):
    with pytest.raises(config_module.ConfigError) as excinfo:
        config_module.load_config(tmp_path)

    assert_error_context(excinfo, path=tmp_path / "chapters.yaml")


def test_load_form_config_malformed_yaml_raises_parse_error(config_module, tmp_path):
    form_path = tmp_path / "forms" / "broken.yaml"
    write_text(form_path, "id: [\n")

    with pytest.raises(config_module.ConfigParseError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path)


def test_load_form_config_blank_required_file_is_validation_error(config_module, tmp_path):
    form_path = tmp_path / "forms" / "blank.yaml"
    write_text(form_path, "# comment only\n")

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path)


def test_load_config_rejects_invalid_chapter_slug(config_module, tmp_path):
    invalid_slug = "bad.slug"
    write_project(
        tmp_path,
        chapters=[make_chapter(slug=invalid_slug)],
        forms={
            invalid_slug: make_form(make_question("name", "short"), form_id=invalid_slug),
        },
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_config(tmp_path)

    assert_error_context(
        excinfo,
        path=tmp_path / "chapters.yaml",
        location="chapters[0].slug",
    )


def test_load_config_rejects_unknown_chapter_key(config_module, tmp_path):
    write_project(
        tmp_path,
        chapters=[make_chapter(unexpected=999)],
        forms={"dark-nemesis": make_form(make_question("name", "short"))},
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_config(tmp_path)

    assert_error_context(
        excinfo,
        path=tmp_path / "chapters.yaml",
        location="chapters[0]",
    )


def test_load_config_rejects_missing_referenced_form_file(config_module, tmp_path):
    write_project(tmp_path, chapters=[make_chapter(slug="missing-form")])

    with pytest.raises(config_module.ConfigError) as excinfo:
        config_module.load_config(tmp_path)

    assert_error_context(excinfo, path=tmp_path / "forms" / "missing-form.yaml")


def test_load_config_rejects_form_id_mismatch(config_module, tmp_path):
    write_project(
        tmp_path,
        chapters=[make_chapter()],
        forms={"dark-nemesis": make_form(make_question("name", "short"), form_id="other-id")},
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_config(tmp_path)

    assert_error_context(
        excinfo,
        path=tmp_path / "forms" / "dark-nemesis.yaml",
        location="id",
    )


def test_load_form_config_rejects_unknown_top_level_key(config_module, tmp_path):
    form_path = tmp_path / "forms" / "dark-nemesis.yaml"
    write_yaml(
        form_path,
        make_form(make_question("name", "short"), extra="not allowed"),
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path)


def test_load_form_config_rejects_invalid_question_type(config_module, tmp_path):
    form_path = tmp_path / "forms" / "dark-nemesis.yaml"
    write_yaml(form_path, make_form(make_question("name", "checkbox")))

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path, location="questions[0].type")


@pytest.mark.parametrize("max_length", [0, 4001])
def test_load_form_config_rejects_out_of_range_max_length(config_module, tmp_path, max_length):
    form_path = tmp_path / "forms" / "dark-nemesis.yaml"
    write_yaml(
        form_path,
        make_form(make_question("name", "short", max_length=max_length)),
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path, location="questions[0].max_length")


@pytest.mark.parametrize(
    ("options", "case_id"),
    [
        ([], "empty-options"),
        (["Alpha", "Alpha"], "duplicate-options"),
        ([f"Option {index}" for index in range(26)], "too-many-options"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_load_form_config_rejects_invalid_select_options(config_module, tmp_path, options, case_id):
    form_path = tmp_path / "forms" / "dark-nemesis.yaml"
    write_yaml(
        form_path,
        make_form(make_question("choice", "select", options=options)),
    )

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert case_id
    assert_error_context(excinfo, path=form_path, location="questions[0].options")


@pytest.mark.parametrize(
    ("question", "location"),
    [
        (
            {
                "id": "q1",
                "type": "short",
                "label": "Question 1",
                "required": True,
            },
            "questions[0].max_length",
        ),
        (
            make_question("q1", "select", max_length=12),
            "questions[0].max_length",
        ),
        (
            make_question("q1", "number", options=["Not allowed"]),
            "questions[0].options",
        ),
    ],
    ids=["missing-max-length", "select-has-max-length", "text-question-has-options"],
)
def test_load_form_config_enforces_type_specific_question_fields(
    config_module,
    tmp_path,
    question,
    location,
):
    form_path = tmp_path / "forms" / "dark-nemesis.yaml"
    write_yaml(form_path, make_form(question))

    with pytest.raises(config_module.ConfigValidationError) as excinfo:
        config_module.load_form_config(form_path)

    assert_error_context(excinfo, path=form_path, location=location)


def test_load_form_config_chunks_modal_and_select_questions_in_groups_of_five(
    config_module,
    tmp_path,
):
    questions = []
    for index in range(1, 7):
        questions.append(make_question(f"modal_{index}", "short", max_length=64))
        questions.append(make_question(f"select_{index}", "select", options=[f"Option {index}"]))

    form_path = tmp_path / "forms" / "chunked.yaml"
    write_yaml(form_path, make_form(*questions, form_id="chunked"))

    form = config_module.load_form_config(form_path)

    assert [question.id for question in form.questions] == [
        "modal_1",
        "select_1",
        "modal_2",
        "select_2",
        "modal_3",
        "select_3",
        "modal_4",
        "select_4",
        "modal_5",
        "select_5",
        "modal_6",
        "select_6",
    ]
    assert [step.index for step in form.steps] == [0, 1, 2, 3]
    assert [step.kind for step in form.steps] == [
        "modal",
        "modal",
        "followup_selects",
        "followup_selects",
    ]
    assert [[question.id for question in step.questions] for step in form.steps] == [
        ["modal_1", "modal_2", "modal_3", "modal_4", "modal_5"],
        ["modal_6"],
        ["select_1", "select_2", "select_3", "select_4", "select_5"],
        ["select_6"],
    ]
