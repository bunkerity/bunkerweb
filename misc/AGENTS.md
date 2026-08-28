# AGENTS.md

Agent guide for development and maintenance tooling in `misc/`. `CLAUDE.md` here is a pointer to this guide.

## What Lives Here

- `dev/` holds local Compose variants, environment examples, and development helpers; `integrations/` holds deployment manifests.
- Installer and update helpers belong at this level. Migration tooling is under `migration/`; read [src/common/db/AGENTS.md](../src/common/db/AGENTS.md) before changing migration behavior.
- `dummy-plugin/` and format helpers are scoped tools, not runtime components.

## Working Rules

- Treat configuration parsing and validation as distinct from starting a stack, installing packages, changing versions, or publishing artifacts; the latter need explicit authorization.
- Keep secrets out of environment examples and manifests. Preserve the Compose variant naming and its matching environment files.
- Validate the affected Compose or manifest files and the narrow helper path; do not use a local convenience stack as deployment proof.
