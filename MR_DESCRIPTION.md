# Lab 05: Model Registry Client

Implements `ModelRegistryClient` for the internal model registry, with
configuration read from the environment, a timeout on every request, a
distinct outcome for each failure mode, parameterized logging, and offline
tests. See [README.md](README.md) for setup and usage.

## Failure modes handled

| Situation | What the client does | Log | CLI exit |
|---|---|---|---|
| 2xx with a valid body | Returns a `ModelInfo` (`id`, `context_window`, `status`, optional `pricing`, derived `deprecated`) | INFO `fetching model %s`, INFO `registry returned %s for %s` | 0 |
| 404 | Raises `ModelNotFoundError(model_id)`: "Model 'x' is not in the registry." This is a normal answer, not a service failure | WARNING `registry returned 404 for %s` | 1 |
| Missing or invalid config | Raises `ConfigurationError` naming the variable, when the client is constructed and before any request | ERROR (CLI) | 2 |
| Other 4xx | Raises `RegistryClientError` with `status_code`. For 401/403 the message points at `MODEL_REGISTRY_TOKEN` without showing it, and `is_auth_error` is true | WARNING, with status and elapsed ms | 3 |
| 5xx | Raises `RegistryServerError` with `status_code`: the service is broken, try later | ERROR, with status and elapsed ms | 4 |
| Timeout (read or connect) | Raises `RegistryTimeoutError`: the outcome is unknown. `ConnectTimeout` is classified as a timeout even though `requests` also makes it a `ConnectionError` | ERROR, with elapsed ms and the timeout | 5 |
| Cannot connect (DNS, refused) | Raises `RegistryConnectionError`, suggesting a check of `MODEL_REGISTRY_URL` and the network | ERROR, with elapsed ms | 5 |
| 2xx but invalid JSON, wrong shape, or a different model's id | Raises `RegistryResponseError` with the reason | ERROR | 6 |

Every exception derives from `RegistryError`, and each wraps the original
`requests` exception with `raise ... from exc`, so the cause stays in the
traceback.

I also ran the CLI against a throwaway server on `127.0.0.1` (not part of
the repo) to watch each path end to end:

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

```
INFO    fetching model slow
ERROR   registry timed out after 1004 ms for slow (timeout 1.0s)

Registry did not answer within 1.0s for 'slow'. The outcome is unknown.
```

## Where the configuration lives, and why

- **A frozen `RegistryConfig` dataclass, validated in `__post_init__`.**
  `RegistryConfig.from_env()` reads `MODEL_REGISTRY_URL`,
  `MODEL_REGISTRY_TOKEN`, and the optional `MODEL_REGISTRY_TIMEOUT` (names
  from the course `.env.example`). A missing or invalid value fails right
  there, naming the variable, so a bad environment never gets as far as a
  half-finished request. The token is excluded from `repr`, so printing the
  config or the client while debugging cannot leak it.
- **Instance versus class (lesson 10).** The config, the `requests.Session`,
  and the auth headers live on the instance, so one client is built once and
  reused across many `get_model` calls, and two clients for different
  registries cannot share settings. Only true constants (`AUTH_SCHEME`,
  `ACCEPT`) are class attributes.
- **The session is injectable.** `ModelRegistryClient(config=..., session=...)`
  lets the tests pass a `Mock(spec=requests.Session)` without patching
  globals. A session the client creates itself is closed by `close()` or the
  `with` block, and an injected one is left to its owner.
- **Only the CLI touches `.env` and logging setup.** The library reads
  `os.environ` and logs through `logging.getLogger(__name__)`. The CLI calls
  `load_dotenv` and `logging.basicConfig`, so importing the package never
  changes the caller's logging or environment.

## Test output

```
$ python -m pytest -q
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 0.10s
```

```
$ python scripts/check_all.py
+ python -m ruff check .
All checks passed!
+ python -m ruff format --check .
15 files already formatted
+ python -m pytest -q
74 passed in 0.10s
+ python scripts/check_content.py
Content safety checks passed.
+ python scripts/check_links.py
Local Markdown links passed.
+ python -m registry_client --help
usage: python -m registry_client [-h] model_id
```

**Nothing touches the network.** Every test uses `unittest.mock`, following
`capstone/starter/tests/test_api.py`, and builds its responses from the
course fixture `models.json`. On top of that, the autouse fixture
`block_network` in `tests/conftest.py` replaces `socket.getaddrinfo`,
`socket.create_connection`, `socket.socket.connect`, and `connect_ex` for
every test. A test that forgot to mock HTTP would fail with
`NetworkBlockedError`, and `test_real_network_is_blocked` proves the guard
works by building a client with a real session and asserting that the
request is stopped.

The tests also check that `timeout=` is passed on every call, that the
`Authorization: Bearer` header is sent, that every log record is
parameterized, and that the token never appears in any log message, log
argument, or exception message.

## Question for the reviewer

Should the client retry 5xx and timeouts with a short backoff, or should
retrying be left to the caller? A retry makes one-off blips invisible, but a
timeout means "we do not know what happened". That is harmless for a
read-only `GET`, and I would not want the same default copied into the
capstone for anything that writes. Where would you draw that line?

## Uso de IA

Este lab fue implementado con asistencia de Claude Code (Anthropic). Revisé el código, los tests y esta descripción, y puedo explicar cada decisión de diseño. Las líneas `Co-Authored-By` se quitaron de los mensajes de commit para mantener el historial limpio; esta sección es la declaración de uso de IA.
