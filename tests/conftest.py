"""Shared fixtures. The autouse guard makes any real network access fail loudly."""

import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from registry_client import ModelRegistryClient, RegistryConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "api"

TEST_BASE_URL = "https://registry.example.test/models"
TEST_TOKEN = "test-token-not-a-real-secret"
TEST_TIMEOUT = 3.0


class NetworkBlockedError(RuntimeError):
    """Raised if a test tries to open a real network connection."""


def _blocked(*args: object, **kwargs: object) -> None:
    raise NetworkBlockedError("tests must not touch the network")


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any attempt to resolve a host or open a socket connection."""
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture
def fixture_models() -> list[dict[str, Any]]:
    """The offline registry response copied from the course capstone."""
    return json.loads((FIXTURES_DIR / "models.json").read_text(encoding="utf-8"))


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_URL", TEST_BASE_URL)
    monkeypatch.setenv("MODEL_REGISTRY_TOKEN", TEST_TOKEN)
    monkeypatch.delenv("MODEL_REGISTRY_TIMEOUT", raising=False)


@pytest.fixture
def config() -> RegistryConfig:
    return RegistryConfig(base_url=TEST_BASE_URL, token=TEST_TOKEN, timeout=TEST_TIMEOUT)


@pytest.fixture
def session() -> Mock:
    return Mock(spec=requests.Session)


@pytest.fixture
def client(config: RegistryConfig, session: Mock) -> ModelRegistryClient:
    return ModelRegistryClient(config=config, session=session)


@pytest.fixture
def make_response() -> Callable[..., Mock]:
    """Build a fake requests.Response with a status code and a JSON body."""

    def build(status_code: int = 200, body: object = None, json_error: bool = False) -> Mock:
        response = Mock(spec=requests.Response)
        response.status_code = status_code
        if json_error:
            response.json.side_effect = requests.JSONDecodeError("Expecting value", "<html>", 0)
        else:
            response.json.return_value = body
        return response

    return build
