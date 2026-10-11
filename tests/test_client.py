import contextlib
import logging
from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from registry_client import (
    ModelInfo,
    ModelNotFoundError,
    ModelRegistryClient,
    RegistryClientError,
    RegistryConfig,
    RegistryConnectionError,
    RegistryError,
    RegistryResponseError,
    RegistryServerError,
    RegistryTimeoutError,
)

from .conftest import TEST_BASE_URL, TEST_TIMEOUT, TEST_TOKEN, NetworkBlockedError

ResponseFactory = Callable[..., Mock]


def test_success_returns_model_info_from_fixture(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
) -> None:
    session.get.return_value = make_response(200, fixture_models[0])

    model = client.get_model("model-small")

    assert model == ModelInfo(id="model-small", context_window=8192, status="available")
    assert model.deprecated is False


def test_request_uses_url_auth_header_and_timeout(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
) -> None:
    session.get.return_value = make_response(200, fixture_models[1])

    client.get_model("model-large")

    session.get.assert_called_once_with(
        f"{TEST_BASE_URL}/model-large",
        headers={"Authorization": f"Bearer {TEST_TOKEN}", "Accept": "application/json"},
        timeout=TEST_TIMEOUT,
    )


def test_model_id_is_escaped_in_url(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    session.get.return_value = make_response(404)

    with pytest.raises(ModelNotFoundError):
        client.get_model("../admin?x=1")

    assert session.get.call_args.args[0] == f"{TEST_BASE_URL}/..%2Fadmin%3Fx%3D1"


@pytest.mark.parametrize("model_id", ["", "   "])
def test_empty_model_id_is_rejected_without_a_request(
    client: ModelRegistryClient, session: Mock, model_id: str
) -> None:
    with pytest.raises(ValueError, match="model_id"):
        client.get_model(model_id)

    session.get.assert_not_called()


def test_deprecated_status_is_reported(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    body = {"id": "model-old", "context_window": 4096, "status": "deprecated"}
    session.get.return_value = make_response(200, body)

    assert client.get_model("model-old").deprecated is True


def test_404_raises_model_not_found(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    session.get.return_value = make_response(404)

    with pytest.raises(ModelNotFoundError) as excinfo:
        client.get_model("does-not-exist")

    assert excinfo.value.model_id == "does-not-exist"
    assert str(excinfo.value) == "Model 'does-not-exist' is not in the registry."


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429])
def test_other_4xx_raise_client_error(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory, status: int
) -> None:
    session.get.return_value = make_response(status)

    with pytest.raises(RegistryClientError) as excinfo:
        client.get_model("model-small")

    assert excinfo.value.status_code == status
    assert excinfo.value.is_auth_error is (status in (401, 403))
    assert TEST_TOKEN not in str(excinfo.value)


def test_auth_errors_point_at_the_token_variable(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    session.get.return_value = make_response(401)

    with pytest.raises(RegistryClientError, match="MODEL_REGISTRY_TOKEN"):
        client.get_model("model-small")


@pytest.mark.parametrize("status", [500, 502, 503])
def test_5xx_raise_server_error(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory, status: int
) -> None:
    session.get.return_value = make_response(status)

    with pytest.raises(RegistryServerError) as excinfo:
        client.get_model("model-small")

    assert excinfo.value.status_code == status


def test_timeout_raises_timeout_error(client: ModelRegistryClient, session: Mock) -> None:
    session.get.side_effect = requests.Timeout("read timed out")

    with pytest.raises(RegistryTimeoutError) as excinfo:
        client.get_model("model-small")

    assert excinfo.value.timeout == TEST_TIMEOUT
    assert isinstance(excinfo.value.__cause__, requests.Timeout)


def test_connect_timeout_is_a_timeout_not_a_connection_error(
    client: ModelRegistryClient, session: Mock
) -> None:
    # ConnectTimeout subclasses both Timeout and ConnectionError.
    session.get.side_effect = requests.ConnectTimeout("connect timed out")

    with pytest.raises(RegistryTimeoutError):
        client.get_model("model-small")


def test_connection_error_raises_connection_error(
    client: ModelRegistryClient, session: Mock
) -> None:
    session.get.side_effect = requests.ConnectionError("name resolution failed")

    with pytest.raises(RegistryConnectionError) as excinfo:
        client.get_model("model-small")

    assert isinstance(excinfo.value.__cause__, requests.ConnectionError)


def test_other_request_errors_are_still_registry_errors(
    client: ModelRegistryClient, session: Mock
) -> None:
    session.get.side_effect = requests.TooManyRedirects("loop")

    with pytest.raises(RegistryError):
        client.get_model("model-small")


def test_invalid_json_raises_response_error(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    session.get.return_value = make_response(200, json_error=True)

    with pytest.raises(RegistryResponseError, match="not valid JSON"):
        client.get_model("model-small")


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ([{"id": "model-small", "context_window": 8192, "status": "available"}], "JSON object"),
        ({"context_window": 8192, "status": "available"}, "'id'"),
        ({"id": "model-small", "status": "available"}, "'context_window'"),
        ({"id": "model-small", "context_window": "8192", "status": "ok"}, "'context_window'"),
        ({"id": "model-small", "context_window": True, "status": "ok"}, "'context_window'"),
        ({"id": "model-small", "context_window": 8192}, "'status'"),
        ({"id": "model-small", "context_window": 8192, "status": "ok", "pricing": 3}, "'pricing'"),
        ({"id": "model-large", "context_window": 32768, "status": "available"}, "different"),
    ],
)
def test_unexpected_shape_raises_response_error(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    body: object,
    reason: str,
) -> None:
    session.get.return_value = make_response(200, body)

    with pytest.raises(RegistryResponseError, match=reason):
        client.get_model("model-small")


def test_unexpected_non_error_status_raises_response_error(
    client: ModelRegistryClient, session: Mock, make_response: ResponseFactory
) -> None:
    session.get.return_value = make_response(304)

    with pytest.raises(RegistryResponseError, match="304"):
        client.get_model("model-small")


def test_one_client_serves_many_calls(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
) -> None:
    session.get.side_effect = [
        make_response(200, fixture_models[0]),
        make_response(404),
        make_response(200, fixture_models[1]),
    ]

    assert client.get_model("model-small").context_window == 8192
    with pytest.raises(ModelNotFoundError):
        client.get_model("missing")
    assert client.get_model("model-large").context_window == 32768

    assert session.get.call_count == 3
    assert all(call.kwargs["timeout"] == TEST_TIMEOUT for call in session.get.call_args_list)


def test_success_logs_request_and_outcome(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    session.get.return_value = make_response(200, fixture_models[0])

    with caplog.at_level(logging.DEBUG, logger="registry_client"):
        client.get_model("model-small")

    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        ("INFO", "fetching model model-small"),
        ("INFO", "registry returned 200 for model-small"),
    ]
    assert all(r.args for r in caplog.records), "log calls must be parameterized"


@pytest.mark.parametrize(
    ("outcome", "level"),
    [
        (404, "WARNING"),
        (403, "WARNING"),
        (500, "ERROR"),
        (requests.Timeout(), "ERROR"),
        (requests.ConnectionError(), "ERROR"),
    ],
)
def test_failures_log_at_the_right_level(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    caplog: pytest.LogCaptureFixture,
    outcome: int | Exception,
    level: str,
) -> None:
    if isinstance(outcome, int):
        session.get.return_value = make_response(outcome)
    else:
        session.get.side_effect = outcome

    with caplog.at_level(logging.DEBUG, logger="registry_client"), pytest.raises(RegistryError):
        client.get_model("model-small")

    last = caplog.records[-1]
    assert last.levelname == level
    assert "model-small" in last.getMessage()


def test_404_log_matches_example_run(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session.get.return_value = make_response(404)

    with caplog.at_level(logging.INFO, logger="registry_client"), pytest.raises(RegistryError):
        client.get_model("does-not-exist")

    assert caplog.records[-1].getMessage() == "registry returned 404 for does-not-exist"


@pytest.mark.parametrize(
    "outcome",
    [200, 401, 404, 500, requests.Timeout(), requests.ConnectionError(), "bad-json"],
)
def test_token_never_appears_in_logs(
    client: ModelRegistryClient,
    session: Mock,
    make_response: ResponseFactory,
    fixture_models: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
    outcome: object,
) -> None:
    if outcome == 200:
        session.get.return_value = make_response(200, fixture_models[0])
    elif outcome == "bad-json":
        session.get.return_value = make_response(200, json_error=True)
    elif isinstance(outcome, int):
        session.get.return_value = make_response(outcome)
    else:
        session.get.side_effect = outcome

    with caplog.at_level(logging.DEBUG), contextlib.suppress(RegistryError):
        client.get_model("model-small")

    assert caplog.records
    for record in caplog.records:
        assert TEST_TOKEN not in record.getMessage()
        assert all(TEST_TOKEN not in str(arg) for arg in record.args or ())
        assert "Authorization" not in record.getMessage()


def test_context_manager_closes_owned_session(config: RegistryConfig) -> None:
    with ModelRegistryClient(config=config) as client:
        owned = client._session
        owned.close = Mock()  # type: ignore[method-assign]

    owned.close.assert_called_once()


def test_close_leaves_injected_session_open(client: ModelRegistryClient, session: Mock) -> None:
    client.close()

    session.close.assert_not_called()


def test_real_network_is_blocked(config: RegistryConfig) -> None:
    """Without a mocked session, a real request must hit the autouse guard.

    The guard raises a RuntimeError that requests does not wrap, so a test that
    forgets to mock HTTP fails loudly instead of being mistaken for a registry error.
    """
    with ModelRegistryClient(config=config) as client, pytest.raises(NetworkBlockedError):
        client.get_model("model-small")
