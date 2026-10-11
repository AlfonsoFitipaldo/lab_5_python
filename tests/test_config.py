from unittest.mock import patch

import pytest

from registry_client import ConfigurationError, ModelRegistryClient, RegistryConfig
from registry_client.config import DEFAULT_TIMEOUT_SECONDS

from .conftest import TEST_BASE_URL, TEST_TOKEN


@pytest.mark.usefixtures("valid_env")
def test_from_env_reads_url_and_token_with_default_timeout() -> None:
    config = RegistryConfig.from_env()

    assert config.base_url == TEST_BASE_URL
    assert config.token == TEST_TOKEN
    assert config.timeout == DEFAULT_TIMEOUT_SECONDS


@pytest.mark.usefixtures("valid_env")
def test_from_env_reads_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_TIMEOUT", "2.5")

    assert RegistryConfig.from_env().timeout == 2.5


@pytest.mark.usefixtures("valid_env")
def test_trailing_slash_is_stripped_from_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_URL", TEST_BASE_URL + "/")

    assert RegistryConfig.from_env().base_url == TEST_BASE_URL


@pytest.mark.usefixtures("valid_env")
@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_base_url_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("MODEL_REGISTRY_URL")
    else:
        monkeypatch.setenv("MODEL_REGISTRY_URL", value)

    with pytest.raises(ConfigurationError, match="MODEL_REGISTRY_URL"):
        RegistryConfig.from_env()


@pytest.mark.usefixtures("valid_env")
@pytest.mark.parametrize("value", [None, ""])
def test_missing_token_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("MODEL_REGISTRY_TOKEN")
    else:
        monkeypatch.setenv("MODEL_REGISTRY_TOKEN", value)

    with pytest.raises(ConfigurationError, match="MODEL_REGISTRY_TOKEN"):
        RegistryConfig.from_env()


@pytest.mark.usefixtures("valid_env")
@pytest.mark.parametrize("value", ["abc", "0", "-1", "nan", "inf"])
def test_invalid_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("MODEL_REGISTRY_TIMEOUT", value)

    with pytest.raises(ConfigurationError, match="MODEL_REGISTRY_TIMEOUT"):
        RegistryConfig.from_env()


def test_base_url_must_be_http() -> None:
    with pytest.raises(ConfigurationError, match="MODEL_REGISTRY_URL"):
        RegistryConfig(base_url="registry.example.test", token=TEST_TOKEN)


def test_repr_never_contains_token(config: RegistryConfig) -> None:
    assert TEST_TOKEN not in repr(config)
    assert TEST_TOKEN not in str(config)
    assert TEST_TOKEN not in repr(ModelRegistryClient(config=config))


def test_config_is_immutable(config: RegistryConfig) -> None:
    with pytest.raises(AttributeError):
        config.token = "other"  # type: ignore[misc]


def test_client_construction_fails_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_REGISTRY_URL", raising=False)
    monkeypatch.setenv("MODEL_REGISTRY_TOKEN", TEST_TOKEN)

    with (
        patch("registry_client.client.requests.Session") as session_cls,
        pytest.raises(ConfigurationError, match="MODEL_REGISTRY_URL"),
    ):
        ModelRegistryClient()

    session_cls.return_value.get.assert_not_called()
