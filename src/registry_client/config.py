"""Load and validate client configuration from environment variables."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .errors import ConfigurationError

BASE_URL_VAR = "MODEL_REGISTRY_URL"
TOKEN_VAR = "MODEL_REGISTRY_TOKEN"
TIMEOUT_VAR = "MODEL_REGISTRY_TIMEOUT"
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class RegistryConfig:
    """Validated, immutable settings for ModelRegistryClient.

    The token is excluded from repr so the config can be logged or printed
    while debugging without leaking the secret.
    """

    base_url: str
    token: str = field(repr=False)
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.base_url or not self.base_url.strip():
            raise ConfigurationError(f"{BASE_URL_VAR} must not be empty")
        if not self.base_url.startswith(("http://", "https://")):
            raise ConfigurationError(f"{BASE_URL_VAR} must start with http:// or https://")
        if not self.token or not self.token.strip():
            raise ConfigurationError(f"{TOKEN_VAR} must not be empty")
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, int | float):
            raise ConfigurationError(f"{TIMEOUT_VAR} must be a number of seconds")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ConfigurationError(f"{TIMEOUT_VAR} must be a positive number of seconds")
        # Frozen dataclass: normalize through object.__setattr__.
        object.__setattr__(self, "base_url", self.base_url.strip().rstrip("/"))
        object.__setattr__(self, "timeout", float(self.timeout))

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "RegistryConfig":
        """Build a config from environment variables.

        Raises ConfigurationError naming the variable that is missing or invalid,
        so the problem surfaces at construction time and not mid-request.
        """
        env = os.environ if environ is None else environ
        base_url = _require(env, BASE_URL_VAR)
        token = _require(env, TOKEN_VAR)
        raw_timeout = env.get(TIMEOUT_VAR, "").strip()
        if not raw_timeout:
            timeout = DEFAULT_TIMEOUT_SECONDS
        else:
            try:
                timeout = float(raw_timeout)
            except ValueError:
                raise ConfigurationError(
                    f"{TIMEOUT_VAR} must be a number of seconds, got {raw_timeout!r}"
                ) from None
        return cls(base_url=base_url, token=token, timeout=timeout)


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"missing required environment variable: {name}")
    return value
