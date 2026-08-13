# Draft: replacement README for bunkerity/bunkerweb-tests

Not published from here. Copy this into the external repository when you decide to
archive it, and archive only after a full dev and staging run has passed from the
monorepo, so a rollback to its last state is still possible.

---

# bunkerweb-tests

This framework now lives in the BunkerWeb monorepo, under
[`tests/`](https://github.com/bunkerity/bunkerweb/tree/dev/tests).

It moved so that the product, its test specifications and CI advance at one commit
instead of three repositories coordinating. Everything here was imported as a snapshot at
`23c77b1`: the specs, models, handlers, runners, scripts and workflows. This repository
keeps the history, and nothing was rebased into the monorepo.

Where things went:

| Here | In the monorepo |
| --- | --- |
| `tests/core/*.yml`, `tests/api/*.yml`, `tests/ui/*.yml` | same paths under `tests/` |
| `tests/core.py`, `tests/api.py`, `tests/ui.py` | same paths |
| `tests/scripts/*.sh` | same paths |
| `.github/workflows/tests.yml` | `.github/workflows/integration-tests.yml` |
| `docs/` | folded into `tests/README.md` |

Open issues and pull requests should move to the monorepo. Read
[`tests/README.md`](https://github.com/bunkerity/bunkerweb/blob/dev/tests/README.md)
first: it covers writing a spec, running the suite locally, and what changed for 1.7.
