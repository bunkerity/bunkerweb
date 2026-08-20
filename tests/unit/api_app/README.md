# The `api_app` lane

Unit tests that import the API's **`app` package**. They run in their own pytest invocation and
their own interpreter, and they are ignored by every other run.

```bash
.venv-unit/bin/pip install --require-hashes -r tests/unit/api_app/requirements.txt
BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
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

`biscuit-python`, `fastapi` and `pydantic-settings` are needed by this lane alone. Keeping them in
`tests/unit/api_app/requirements.txt` means a runner that never invokes the lane never installs
them, and the main suite's install is unchanged.

**One deliberate difference from what the API ships.** `src/api/requirements.in` pins
`biscuit-python` as a GitHub **source archive** (commit `c0fa698`, labelled 0.4.1), which needs a
Rust toolchain — `src/api/Dockerfile` installs `cargo` for exactly that. This lane pins PyPI's
**0.4.0**, a prebuilt wheel that installs with no compiler. The tests assert BunkerWeb's own guard
behaviour — that it raises `max_time` and leaves `max_facts`/`max_iterations` at their defaults —
not biscuit internals, so the one-patch drift does not touch what is under test. If that ever stops
being true, pin the archive and add `cargo` to the runner.

## What is covered

`test_biscuit_run_limit.py`, ported from dev's `src/api/tests/test_biscuit_run_limit.py`
(`a72deb504`); 1.7 has no `src/api/tests/`. It covers the Datalog run-limit handling of the Biscuit
guard: that only `max_time` is raised, that genuine denials still return 401/403, and — the point —
that a token attenuated offline to blow the fact/iteration limits is **denied** rather than reported
as a transient busy-host error. Biscuit attenuation needs no private key, so a run-limit abort is a
hostile credential, not a slow machine.
