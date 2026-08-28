# AGENTS.md

Agent guide for vendored build dependencies in `src/deps/`. `CLAUDE.md` here is a pointer to this guide.

## Dependency Boundary

- `src/` is vendored third-party source: do not edit it directly. Keep durable BunkerWeb changes as patches under `misc/`, wired through the existing manifests and update flow.
- Keep dependency versions and pins in the existing manifests (`deps.json`, requirements files, and package manifests), not in copied source.
- Use the existing update scripts instead of ad-hoc vendor refreshes.

## Validation

- A dependency update requires the relevant component or image build validation. Lockfile or manifest consistency alone is not enough.
- Preserve hashes and reproducible pinning. Do not publish, push, or otherwise write dependency artifacts externally without explicit authorization.
