from pathlib import Path

import pytest
from pytestarch import EvaluableArchitecture, Rule, get_evaluable_architecture

_APP_PATH = str(Path(__file__).parent.parent / "app")


@pytest.fixture(scope="session")
def arch() -> EvaluableArchitecture:
    return get_evaluable_architecture(_APP_PATH, _APP_PATH)


def test_routes_do_not_import_repositories(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.api.routes")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.repositories")
    ).assert_applies(arch)


def test_services_do_not_import_api(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.services")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.api")
    ).assert_applies(arch)


def test_repositories_do_not_import_services(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.repositories")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.services")
    ).assert_applies(arch)


def test_repositories_do_not_import_api(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.repositories")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.api")
    ).assert_applies(arch)


def test_models_do_not_import_repositories(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.repositories")
    ).assert_applies(arch)


def test_models_do_not_import_services(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.services")
    ).assert_applies(arch)


def test_models_do_not_import_api(arch: EvaluableArchitecture) -> None:
    (
        Rule()
        .modules_that()
        .are_sub_modules_of("app.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("app.api")
    ).assert_applies(arch)
