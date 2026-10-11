"""HTTP client for the internal model registry."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import quote

import requests

from .config import RegistryConfig
from .errors import (
    ModelNotFoundError,
    RegistryClientError,
    RegistryConnectionError,
    RegistryError,
    RegistryResponseError,
    RegistryServerError,
    RegistryTimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for one model, in the shape of fixtures/api/models.json."""

    id: str
    context_window: int
    status: str
    pricing: dict[str, Any] | None = None

    @property
    def deprecated(self) -> bool:
        """True when the registry marks the model as deprecated."""
        return self.status.lower() == "deprecated"

    @classmethod
    def from_dict(cls, payload: object) -> "ModelInfo":
        """Validate a decoded JSON payload and build a ModelInfo.

        Raises ValueError describing the first problem found.
        """
        if not isinstance(payload, dict):
            raise ValueError(f"expected a JSON object, got {type(payload).__name__}")
        model_id = payload.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("field 'id' must be a non-empty string")
        context_window = payload.get("context_window")
        if (
            isinstance(context_window, bool)
            or not isinstance(context_window, int)
            or context_window <= 0
        ):
            raise ValueError("field 'context_window' must be a positive integer")
        status = payload.get("status")
        if not isinstance(status, str) or not status:
            raise ValueError("field 'status' must be a non-empty string")
        pricing = payload.get("pricing")
        if pricing is not None and not isinstance(pricing, dict):
            raise ValueError("field 'pricing' must be an object when present")
        return cls(id=model_id, context_window=context_window, status=status, pricing=pricing)


class ModelRegistryClient:
    """Reads model metadata from the registry, failing clearly on every error path.

    Class attributes hold what is identical for every client and never changes
    (the auth scheme, the media type). Instance attributes hold what belongs to
    one configured client: its config, its HTTP session, and its auth headers.
    That way one client is built once and reused across many calls, and two
    clients pointed at different registries cannot leak settings into each other.
    """

    AUTH_SCHEME = "Bearer"
    ACCEPT = "application/json"

    def __init__(
        self,
        config: RegistryConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Build a client; reads the environment when no config is given.

        Raises ConfigurationError here, at construction time, if configuration
        is missing, rather than halfway through a request. A session can be
        injected for tests; one the client creates itself is closed by close().
        """
        self._config = config if config is not None else RegistryConfig.from_env()
        self._owns_session = session is None
        self._session = session if session is not None else requests.Session()
        self._headers = {
            "Authorization": f"{self.AUTH_SCHEME} {self._config.token}",
            "Accept": self.ACCEPT,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(config={self._config!r})"

    @property
    def config(self) -> RegistryConfig:
        """The configuration this client was built with."""
        return self._config

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the HTTP session if this client created it."""
        if self._owns_session:
            self._session.close()

    def model_url(self, model_id: str) -> str:
        """Return the URL for one model, with the id safely escaped."""
        return f"{self._config.base_url}/{quote(model_id, safe='')}"

    def get_model(self, model_id: str) -> ModelInfo:
        """Return metadata for one model.

        Raises:
            ValueError: model_id is empty.
            ModelNotFoundError: 404, the model does not exist.
            RegistryClientError: any other 4xx (401/403 point at the token).
            RegistryServerError: 5xx, the service is broken.
            RegistryTimeoutError: no answer within the configured timeout.
            RegistryConnectionError: the registry could not be reached.
            RegistryResponseError: the body is not valid JSON or not the expected shape.
        """
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a non-empty string")
        model_id = model_id.strip()

        logger.info("fetching model %s", model_id)
        started = time.perf_counter()
        try:
            response = self._session.get(
                self.model_url(model_id),
                headers=self._headers,
                timeout=self._config.timeout,
            )
        except requests.Timeout as exc:
            logger.error(
                "registry timed out after %.0f ms for %s (timeout %ss)",
                _elapsed_ms(started),
                model_id,
                self._config.timeout,
            )
            raise RegistryTimeoutError(model_id, self._config.timeout) from exc
        except requests.ConnectionError as exc:
            logger.error(
                "could not connect to registry for %s after %.0f ms",
                model_id,
                _elapsed_ms(started),
            )
            raise RegistryConnectionError(model_id) from exc
        except requests.RequestException as exc:
            logger.error("request to registry failed for %s: %s", model_id, type(exc).__name__)
            raise RegistryError(f"Request for '{model_id}' failed: {type(exc).__name__}") from exc

        status = response.status_code
        elapsed = _elapsed_ms(started)
        if status == 404:
            logger.warning("registry returned 404 for %s", model_id)
            raise ModelNotFoundError(model_id)
        if 400 <= status < 500:
            logger.warning("registry returned %s for %s in %.0f ms", status, model_id, elapsed)
            raise RegistryClientError(model_id, status)
        if status >= 500:
            logger.error("registry returned %s for %s in %.0f ms", status, model_id, elapsed)
            raise RegistryServerError(model_id, status)
        if not 200 <= status < 300:
            logger.error("registry returned unexpected %s for %s", status, model_id)
            raise RegistryResponseError(model_id, f"unexpected status {status}")

        logger.info("registry returned %s for %s", status, model_id)
        return self._parse(model_id, response)

    def _parse(self, model_id: str, response: requests.Response) -> ModelInfo:
        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("registry returned a body that is not JSON for %s", model_id)
            raise RegistryResponseError(model_id, "body is not valid JSON") from exc
        try:
            model = ModelInfo.from_dict(payload)
        except ValueError as exc:
            logger.error("registry returned an unexpected shape for %s: %s", model_id, exc)
            raise RegistryResponseError(model_id, str(exc)) from exc
        if model.id != model_id:
            logger.error("registry returned model %s when asked for %s", model.id, model_id)
            raise RegistryResponseError(model_id, f"response is for a different model '{model.id}'")
        return model


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
