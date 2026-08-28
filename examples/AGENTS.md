# AGENTS.md

Agent guide for user-facing deployment recipes in `examples/`. `CLAUDE.md` here is a pointer to this guide.

## Recipe Rules

- Examples are documentation-quality deployment recipes. Keep commands, service names, environment variables, and setup steps reproducible for users.
- Only selected examples are integration fixtures; their descriptors live in [tests/examples/](../tests/examples/), not beside each recipe.
- Use placeholders for credentials, domains, certificates, and tokens. Never turn an example into a source of real secrets.
- Compose parsing and validation are read-only checks; starting stacks, creating infrastructure, or publishing images need explicit authorization.

## Scope

- [mcp-stack/AGENTS.md](mcp-stack/AGENTS.md) is a specialized child guide and overrides this guide for that example.
- Do not add child guides unless the directory has genuinely distinct constraints.
