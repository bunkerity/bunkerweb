# The `api_app` lane

Unit tests that import the API's **`app` package**. They run in their own pytest invocation and
their own interpreter, and they are ignored by every other run.

```bash
uv pip install -p .venv-unit/bin/python --require-hashes -r tests/unit/api_app/requirements.txt
timeout -k 30 300 env BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
```

Without `BW_API_APP_LANE=1` the directory is ignored — even when you name it on the command line,
you get `no tests ran`. That is deliberate.

## Why a separate lane

`tests/unit/ui/conftest.py` states the invariant the whole unit suite rests on:

> Only the UI imports `app` (API tests recompose without it), so `import app` resolves uniquely to
> `src/ui/app`.

`tests/unit/api/conftest.py` honours it by recomposing `APIDatabase` out of `src/api/app/models`
rather than importing the package. That works only because the API's DB mixins use **absolute**
imports.

It does not generalise. `src/api/app/auth/biscuit.py` imports `..config`, `..utils` and `.common`
**relatively**, so it can only be imported as part of its package, with `src/api` on `sys.path` as
`app`. Two `app` packages in one interpreter means whichever is imported first wins and the other
silently resolves to the wrong module — no error, just the wrong code under test.

A separate interpreter is the honest answer. `tests/unit/conftest.py` enforces it with
`collect_ignore_glob`, so accidental collection is impossible rather than merely discouraged.

## Why the dependencies are pinned here and not in `tests/unit/requirements.in`

`biscuit-python`, `fastapi`, `pydantic-settings` and `python-multipart` (FastAPI refuses to build a route with a `Form`/`File` parameter without it) are needed by this lane alone. Keeping them in
`tests/unit/api_app/requirements.txt` means a runner that never invokes the lane never installs
them, and the main suite's install is unchanged.

Pins match `src/api/requirements.in`, including the `biscuit-python` GitHub **source archive**
(commit `c0fa698`, labelled 0.4.1). Building it needs a Rust toolchain when no cached wheel exists
(`src/api/Dockerfile` installs `cargo` for that).

## What is covered

`test_api_response_compression.py` checks the API's response compression.

`test_biscuit_run_limit.py` covers the Datalog run-limit handling of the Biscuit guard: that only
`max_time` is raised, that genuine denials still return 401/403, and that a token attenuated
offline to blow the fact/iteration limits is **denied** rather than reported as a transient
busy-host error.

`test_configs_move_authz.py` proves that moving a custom config requires permission on the
destination service or global scope.

## dev (1.6.x) differences

Ported from 1.7. Two test doubles follow dev's API surface, assertions unchanged:
`make_request()` carries a `state` namespace (dev's guard records the verified token on
`request.state`), and the upload variant awaits dev's async `update_config_upload` with a fake
`request.form()` and `UploadFile.read()`. Not ported, because they test 1.7-only API surface:
`test_attachments_authz.py`, `test_bans_unban_authz.py`, `test_certificate_plugin_authz.py`
and `test_openapi_schema.py`.
