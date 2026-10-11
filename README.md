# Lab 05: Model Registry Client

A small client for the internal model registry that reads its configuration
from the environment, puts a timeout on every request, and fails clearly:
a missing model, a rejected request, a broken service, and a request that
never came back each produce a different, readable outcome.

This is a standalone implementation of Lab 05 from the Python AI Foundations
course (`labs/lab_05_model_registry_client/README.md` in the course repository).

## Setup

Requires Python 3.12 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env   # then put a real local token in .env; never commit it
```

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `MODEL_REGISTRY_URL` | yes | Base URL of the models collection, e.g. `https://example.invalid/models` |
| `MODEL_REGISTRY_TOKEN` | yes | Bearer token sent in the `Authorization` header |
| `MODEL_REGISTRY_TIMEOUT` | no | Seconds to wait for each request (default `5`) |
| `LOG_LEVEL` | no | Log level for the CLI (default `INFO`) |

A missing or invalid variable raises `ConfigurationError` naming the variable
when the client is constructed, before any request is made. The CLI loads a
local `.env` with `python-dotenv`; the library itself only reads `os.environ`.

## Usage

```bash
python -m registry_client model-small
```

```
INFO    fetching model model-small
INFO    registry returned 200 for model-small

model-small
  context window: 8192
  status:         available
  deprecated:     False
```

```
INFO    fetching model does-not-exist
WARNING registry returned 404 for does-not-exist

Model 'does-not-exist' is not in the registry.
```

From Python:

```python
from registry_client import ModelNotFoundError, ModelRegistryClient

with ModelRegistryClient() as client:  # reads the environment
    try:
        model = client.get_model("model-small")
    except ModelNotFoundError:
        ...
```

A model is requested with `GET {MODEL_REGISTRY_URL}/{model_id}` (the id is
URL-escaped) and the response is expected to be one object shaped like the
entries in [fixtures/api/models.json](fixtures/api/models.json):
`id`, `context_window`, `status`, and an optional `pricing` object.
`deprecated` is derived from `status == "deprecated"`, because the fixture
has no separate `deprecated` field.

## Failure modes and exit codes

| Situation | Exception | Log level | CLI exit code |
|---|---|---|---|
| Success (2xx) | none | INFO | 0 |
| 404 | `ModelNotFoundError` | WARNING | 1 |
| Missing or invalid configuration | `ConfigurationError` | ERROR | 2 (argparse usage errors also exit 2) |
| Other 4xx (401/403 suggest checking the token) | `RegistryClientError` | WARNING | 3 |
| 5xx | `RegistryServerError` | ERROR | 4 |
| Timeout | `RegistryTimeoutError` | ERROR | 5 |
| Cannot connect (DNS, refused) | `RegistryConnectionError` | ERROR | 5 |
| 2xx with invalid JSON or the wrong shape | `RegistryResponseError` | ERROR | 6 |

Every exception derives from `RegistryError`, so callers can catch everything
at once or one case at a time.

## Tests and checks

```bash
python -m pytest            # tests only
python scripts/check_all.py # lint, format, tests, content and link checks, CLI smoke
```

No test touches the network. HTTP is mocked with `unittest.mock`, following
the course's `capstone/starter/tests/test_api.py`, and an autouse fixture in
[tests/conftest.py](tests/conftest.py) replaces `socket.getaddrinfo`,
`socket.create_connection`, and `socket.socket.connect` so any real request
fails the test immediately.

## Layout

```
src/registry_client/   config.py, errors.py, client.py, cli.py, __main__.py
tests/                 conftest.py, test_config.py, test_client.py, test_cli.py
fixtures/api/          offline registry response used by the tests
scripts/               check_all.py, check_content.py, check_links.py
```

## Files taken from the course repository

| File here | Source in the course repository | Changes |
|---|---|---|
| `fixtures/api/models.json` | `capstone/fixtures/api/models.json` | none |
| `.env.example` | `.env.example` | added the optional `MODEL_REGISTRY_TIMEOUT` |
| `scripts/check_content.py` | `scripts/check_content.py` | none |
| `scripts/check_links.py` | `scripts/check_links.py` | none |
| `scripts/check_all.py` | `scripts/check_all.py` | `smoke_demos.py` (runs `lessons/*/demo/*.py`, which do not exist here) replaced by a `--help` smoke run of the CLI |
| `pyproject.toml` | `pyproject.toml` | same dependencies, ruff and pytest settings; package and test paths adapted |
| `.gitignore`, `.editorconfig`, `.python-version` | same names | instructor-only entries dropped from `.gitignore` |
