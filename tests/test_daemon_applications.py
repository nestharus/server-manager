import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


APPLICATIONS_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "daemon" / "applications.py"
)
SAMPLE_FORM_PATH = Path(__file__).resolve().parents[1] / "forms" / "dark-nemesis.yaml"
TEXT_QUESTION_TYPES = {"short", "long", "number"}


def import_applications_module():
    if not APPLICATIONS_MODULE_PATH.exists():
        pytest.fail(
            "Could not import daemon.applications: "
            f"{APPLICATIONS_MODULE_PATH} does not exist"
        )
    try:
        return importlib.import_module("daemon.applications")
    except Exception as exc:  # pragma: no cover - import failures should fail loudly
        pytest.fail(f"Could not import daemon.applications: {exc!r}")


@pytest.fixture
def applications_module():
    return import_applications_module()


@pytest.fixture
def modal_contract_inputs():
    payload = yaml.safe_load(SAMPLE_FORM_PATH.read_text(encoding="utf-8"))

    questions = []
    for source_index, raw_question in enumerate(payload["questions"]):
        if raw_question["type"] not in TEXT_QUESTION_TYPES:
            continue
        questions.append(
            SimpleNamespace(
                id=raw_question["id"],
                type=raw_question["type"],
                label=raw_question["label"],
                required=raw_question["required"],
                max_length=raw_question.get("max_length"),
                options=tuple(raw_question.get("options", ())),
                source_index=source_index,
            )
        )

    step = SimpleNamespace(index=0, kind="modal", questions=tuple(questions))
    form = SimpleNamespace(
        source_path=SAMPLE_FORM_PATH,
        id=payload["id"],
        title=payload["title"],
        questions=tuple(questions),
        steps=(step,),
    )
    chapter = SimpleNamespace(slug=payload["id"], display_name="Dark Nemesis")
    bot = SimpleNamespace(conn=object(), config=object(), guild_id=900000000000000001)

    return bot, chapter, form, step


def test_application_modal_constructs_with_valid_inputs_and_bounded_ids(
    applications_module, modal_contract_inputs
):
    bot, chapter, form, _ = modal_contract_inputs

    modal = applications_module.ApplicationModal(
        bot=bot,
        chapter=chapter,
        form=form,
        step_index=0,
    )

    assert isinstance(modal.title, str)
    assert form.title in modal.title
    assert len(modal.title) < 45

    assert isinstance(modal.custom_id, str)
    assert chapter.slug in modal.custom_id
    assert "0" in modal.custom_id
    assert len(modal.custom_id) < 100


def test_application_modal_children_match_the_selected_step_questions(
    applications_module, modal_contract_inputs
):
    bot, chapter, form, step = modal_contract_inputs

    modal = applications_module.ApplicationModal(
        bot=bot,
        chapter=chapter,
        form=form,
        step_index=0,
    )

    assert len(modal.children) == len(step.questions)
    assert [child.label for child in modal.children] == [
        question.label for question in step.questions
    ]


def test_application_review_view_constructs_for_submission_id_42(applications_module):
    view = applications_module.ApplicationReviewView(42)

    assert view is not None


def test_application_review_view_has_exactly_four_button_children(applications_module):
    view = applications_module.ApplicationReviewView(42)

    assert len(view.children) == 4


def test_application_review_view_buttons_have_expected_labels_in_order(
    applications_module,
):
    view = applications_module.ApplicationReviewView(42)

    assert [child.label for child in view.children] == [
        "Claim",
        "Interview",
        "Approve",
        "Deny",
    ]


def test_application_review_view_buttons_have_expected_custom_ids(applications_module):
    view = applications_module.ApplicationReviewView(42)

    assert [child.custom_id for child in view.children] == [
        "app:claim:42",
        "app:interview:42",
        "app:approve:42",
        "app:deny:42",
    ]


def test_application_review_view_is_persistent(applications_module):
    view = applications_module.ApplicationReviewView(42)

    assert view.timeout is None


def test_setup_applications_is_async(applications_module):
    assert inspect.iscoroutinefunction(applications_module.setup_applications)
