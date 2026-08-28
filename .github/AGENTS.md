# AGENTS.md

Agent guide for GitHub metadata and automation in `.github/`. `CLAUDE.md` here is a pointer to this guide.

## Workflow Boundaries

- Event and manual orchestrator workflows call local reusable build, test, or publish workflows. Reusable workflows declare `workflow_call` contracts; when one changes, inspect and update every caller.
- Preserve pinned action SHAs and use the smallest permissions each workflow needs.
- Keep secrets inside GitHub expressions and documented workflow interfaces; never place values in YAML, logs, fixtures, or generated artifacts.
- Publishing, release, deployment, labels, comments, and other external writes require explicit authorization, even when a workflow supports them.

## Validation

- Parse and lint workflow YAML without dispatching it. Verify changed reusable-workflow callers and release paths separately.
- Keep issue templates, Dependabot, CodeQL, and Plumber configuration consistent with their GitHub consumers.
