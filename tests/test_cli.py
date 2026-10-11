from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests

from registry_client import cli

ResponseFactory = Callable[..., Mock]


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's local .env out of the tests."""
    monkeypatch.setattr(cli, "load_dotenv", lambda *args, **kwargs: False)


def run_cli(model_id: str, outcome: object) -> int:
    with patch("registry_client.client.requests.Session") as session_cls:
        session = session_cls.return_value
        if isinstance(outcome, Exception):
            session.get.side_effect = outcome
        else:
            session.get.return_value = outcome
        return cli.main([model_id])


@pytest.mark.usefixtures("valid_env")
def test_cli_prints_model_and_exits_zero(
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run_cli("model-small", make_response(200, fixture_models[0]))

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "model-small\n  context window: 8192\n" in out
    assert "  deprecated:     False" in out


@pytest.mark.usefixtures("valid_env")
def test_cli_not_found(make_response: ResponseFactory, capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli("does-not-exist", make_response(404))

    assert code == cli.EXIT_NOT_FOUND
    assert "Model 'does-not-exist' is not in the registry." in capsys.readouterr().out


@pytest.mark.usefixtures("valid_env")
@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, cli.EXIT_CLIENT_ERROR), (422, cli.EXIT_CLIENT_ERROR), (503, cli.EXIT_SERVER_ERROR)],
)
def test_cli_status_exit_codes(make_response: ResponseFactory, status: int, expected: int) -> None:
    assert run_cli("model-small", make_response(status)) == expected


@pytest.mark.usefixtures("valid_env")
@pytest.mark.parametrize("error", [requests.Timeout(), requests.ConnectionError()])
def test_cli_unreachable_exit_code(error: Exception) -> None:
    assert run_cli("model-small", error) == cli.EXIT_UNREACHABLE


@pytest.mark.usefixtures("valid_env")
def test_cli_bad_response_exit_code(make_response: ResponseFactory) -> None:
    assert run_cli("model-small", make_response(200, json_error=True)) == cli.EXIT_BAD_RESPONSE


def test_cli_missing_config_exits_with_config_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_REGISTRY_URL", raising=False)
    monkeypatch.delenv("MODEL_REGISTRY_TOKEN", raising=False)

    assert cli.main(["model-small"]) == cli.EXIT_CONFIG
