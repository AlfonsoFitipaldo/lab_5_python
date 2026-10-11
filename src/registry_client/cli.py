"""Command-line interface for the model registry client.

Operational messages go through logging (stderr). The lookup result is the
program's actual output, so it is printed to stdout.
"""

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from dotenv import find_dotenv, load_dotenv

from .client import ModelInfo, ModelRegistryClient
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

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_CONFIG = 2
EXIT_CLIENT_ERROR = 3
EXIT_SERVER_ERROR = 4
EXIT_UNREACHABLE = 5
EXIT_BAD_RESPONSE = 6

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m registry_client",
        description="Look up one model's metadata in the model registry.",
    )
    parser.add_argument("model_id", help="id of the model to look up, e.g. model-small")
    return parser


def format_model(model: ModelInfo) -> str:
    """Render a model the way the lab's example run shows it."""
    lines = [
        model.id,
        f"  context window: {model.context_window}",
        f"  status:         {model.status}",
        f"  deprecated:     {model.deprecated}",
    ]
    if model.pricing is not None:
        lines.append(f"  pricing:        {model.pricing}")
    return "\n".join(lines)


def configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelNamesMapping().get(level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)-7s %(message)s")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(find_dotenv(usecwd=True))
    configure_logging()

    try:
        with ModelRegistryClient() as client:
            model = client.get_model(args.model_id)
    except ConfigurationError as error:
        logger.error("configuration problem: %s", error)
        return EXIT_CONFIG
    except ModelNotFoundError as error:
        _report(str(error), stream=sys.stdout)
        return EXIT_NOT_FOUND
    except RegistryClientError as error:
        _report(str(error))
        return EXIT_CLIENT_ERROR
    except RegistryServerError as error:
        _report(str(error))
        return EXIT_SERVER_ERROR
    except (RegistryTimeoutError, RegistryConnectionError) as error:
        _report(str(error))
        return EXIT_UNREACHABLE
    except (RegistryResponseError, RegistryError) as error:
        _report(str(error))
        return EXIT_BAD_RESPONSE

    _report(format_model(model), stream=sys.stdout)
    return EXIT_OK


def _report(message: str, stream: TextIO | None = None) -> None:
    """Print a user-facing result, separated from the log lines above it."""
    print(f"\n{message}", file=stream if stream is not None else sys.stderr)
