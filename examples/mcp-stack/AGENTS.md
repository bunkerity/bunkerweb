# AGENTS.md

Local agent guide for the BunkerWeb MCP stack example in `examples/mcp-stack/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form MCP stack notes: [CLAUDE.md](CLAUDE.md)
- Main docs: [https://docs.bunkerweb.io](https://docs.bunkerweb.io)

## Critical Rules

- This example requires the external API and Celery worker architecture.
- The Worker is required for `jobs_run`; accepted jobs will not execute without it.
- Treat read-only MCP tools and resources differently from mutating or destructive tools.
- Keep API tokens, session secrets, and keys out of commits.
- The example listens on plain HTTP and disables DNS rebinding protection; production deployments must harden those settings.

## Commands

```bash
docker compose up -d
```

## Pitfalls

- Configure assistants with `.mcp.json` after the stack is running.
- Config changes are auto-applied by BunkerWeb; no manual reload is expected.
- Destructive MCP actions such as delete, unban, and stop operations need explicit confirmation.
- Always include an audit-friendly reason when banning IPs.
