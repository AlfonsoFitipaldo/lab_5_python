"""Client for the internal model registry service."""

from .client import ModelInfo, ModelRegistryClient
from .config import RegistryConfig
from .errors import (
    ConfigurationError,
    ModelNotFoundError,
    RegistryClientError,
    RegistryConnectionError,
    RegistryError,
    RegistryResponseError,
    RegistryServerError,
    RegistryTimeoutError,
)

__all__ = [
    "ConfigurationError",
    "ModelInfo",
    "ModelNotFoundError",
    "ModelRegistryClient",
    "RegistryClientError",
    "RegistryConfig",
    "RegistryConnectionError",
    "RegistryError",
    "RegistryResponseError",
    "RegistryServerError",
    "RegistryTimeoutError",
]
