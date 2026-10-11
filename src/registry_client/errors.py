"""Exception hierarchy for the model registry client.

Every error derives from RegistryError, so a caller can catch everything the
client raises in one place, or catch one specific failure mode and let the
rest propagate.
"""


class RegistryError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(RegistryError):
    """Required configuration is missing or unusable."""


class ModelNotFoundError(RegistryError):
    """The registry answered 404: no model has this id.

    This is a normal answer to a reasonable question, not a broken service.
    """

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        super().__init__(f"Model '{model_id}' is not in the registry.")


class RegistryClientError(RegistryError):
    """The registry rejected the request with a 4xx other than 404."""

    def __init__(self, model_id: str, status_code: int) -> None:
        self.model_id = model_id
        self.status_code = status_code
        if status_code in (401, 403):
            message = (
                f"Registry refused the request for '{model_id}' with {status_code}: "
                "check that MODEL_REGISTRY_TOKEN is set to a valid token."
            )
        else:
            message = f"Registry rejected the request for '{model_id}' with {status_code}."
        super().__init__(message)

    @property
    def is_auth_error(self) -> bool:
        """True for 401 and 403, which usually mean a bad or missing token."""
        return self.status_code in (401, 403)


class RegistryServerError(RegistryError):
    """The registry answered 5xx: the service itself is broken."""

    def __init__(self, model_id: str, status_code: int) -> None:
        self.model_id = model_id
        self.status_code = status_code
        super().__init__(
            f"Registry failed with {status_code} while fetching '{model_id}'. "
            "The service is having problems; try again later."
        )


class RegistryTimeoutError(RegistryError):
    """No response arrived within the timeout, so the outcome is unknown."""

    def __init__(self, model_id: str, timeout: float) -> None:
        self.model_id = model_id
        self.timeout = timeout
        super().__init__(
            f"Registry did not answer within {timeout}s for '{model_id}'. The outcome is unknown."
        )


class RegistryConnectionError(RegistryError):
    """The registry could not be reached at all (DNS failure, refused connection)."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        super().__init__(
            f"Could not connect to the registry while fetching '{model_id}'. "
            "Check MODEL_REGISTRY_URL and your network."
        )


class RegistryResponseError(RegistryError):
    """The registry answered, but the body is not the shape this client expects."""

    def __init__(self, model_id: str, reason: str) -> None:
        self.model_id = model_id
        self.reason = reason
        super().__init__(f"Registry returned an unexpected response for '{model_id}': {reason}.")
