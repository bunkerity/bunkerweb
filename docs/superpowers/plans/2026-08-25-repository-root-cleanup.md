# Repository Root Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce BunkerWeb's default-branch root from 31 to 27 entries while restoring Plumber's standard root discovery and preserving every existing workflow and public surface.

**Architecture:** Move only files whose owning tools support the destination natively. Keep root-discovered configuration at root, update every in-repository consumer atomically with its move, and verify static references before broader workflow checks.

**Tech Stack:** GitHub Actions, Plumber, GitHub community health files, MkDocs Material with static i18n, Trivy, pre-commit.

**Spec:** [BunkerWeb Repository Root Cleanup Audit and Migration Map](https://docs.batgregate900.dedyn.io/doc/bunkerweb-repository-root-cleanup-audit-and-migration-map-VWtdIaz5J5)

## Global Constraints

- Never create a Git commit or push, publish, deploy, or update external systems.
- Preserve unrelated staged and unstaged work; target files were clean at the implementation baseline.
- Keep `README.md`, `LICENSE.md`, `AGENTS.md`, `CHANGELOG.md`, `mkdocs.yml`, `mkdocs_print.yml`, and all default-discovered tool configuration at root.
- The Plumber policy filename is exactly `.plumber.yaml`.
- Retain the Monday Plumber schedule, reusable `workflow_call`, score gate `min-score: B`, `soft-fail: false`, artifact upload, SARIF upload, and publish dependencies.
- Do not update BunkerWeb AI Skills, private mirrors, OpenSSF Best Practices, websites, or other repositories in this change.

---

### Task 1: Restore standard Plumber policy discovery

**Files:**
- Move: `.github/plumber/plumber.yaml` to `.plumber.yaml`
- Modify: `.github/workflows/plumber.yml`
- Modify: `.github/plumber/README.md`

**Interfaces:**
- Consumes: the existing overlay extending `plumber:default`
- Produces: a root `.plumber.yaml` available to local, Action, and hosted-scanner discovery

- [x] Move the policy without changing its YAML content.
- [x] Expand sparse checkout to include `.github` and `.plumber.yaml`.
- [x] Point the explicit Action input at `.plumber.yaml` so workflow behavior remains auditable.
- [x] Update the Plumber file inventory and local-use documentation.
- [x] Confirm no reference to `.github/plumber/plumber.yaml` remains.
- [x] Validate the overlay with an available Plumber binary or the official container; record a blocker if neither can run.

### Task 2: Move GitHub community health files

**Files:**
- Move: `CODE_OF_CONDUCT.md` to `.github/CODE_OF_CONDUCT.md`
- Move: `CONTRIBUTING.md` to `.github/CONTRIBUTING.md`
- Move: `SECURITY.md` to `.github/SECURITY.md`
- Modify: `README.md`
- Modify: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Modify: `.github/ISSUE_TEMPLATE/documentation.yml`
- Modify: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Modify: `.github/copilot-instructions.md`
- Modify: `.pre-commit-config.yaml`
- Modify: `src/ui/main.py`

**Interfaces:**
- Consumes: GitHub's supported `.github/` community-file lookup
- Produces: unchanged Community and Security surfaces at new branch-relative paths

- [x] Move all three files without changing policy substance.
- [x] Make the moved contribution guide link back to root `AGENTS.md` correctly.
- [x] Replace release-pinned raw README links with branch-relative community-file links.
- [x] Update all three issue-form Code of Conduct URLs.
- [x] Update Copilot instruction links and the generated `security.txt` Policy URL.
- [x] Update the codespell skip path.
- [x] Confirm no old root community-file URL remains in this repository.

### Task 3: Put the community build guide in documentation

**Files:**
- Move: `BUILD.md` to `docs/building.md`
- Modify: `README.md`
- Modify: `mkdocs.yml`
- Modify: `mkdocs_print.yml`

**Interfaces:**
- Consumes: the existing English build guide and MkDocs navigation structure
- Produces: a discoverable build page included in the web and PDF documentation configurations

- [x] Move the guide without changing its technical or security content.
- [x] Add a branch-relative README link near the Setup entry point.
- [x] Add `Building from source` after `Quickstart guide` in both MkDocs navigation lists.
- [x] Add French, German, Spanish, and Chinese navigation labels.
- [x] Build documentation with the repository environment or official docs container; explicitly inspect localized fallback behavior.

### Task 4: Co-locate the explicit Trivy policy

**Files:**
- Move: `.trivyignore.rego` to `.github/trivy/ignore.rego`
- Modify: `.github/workflows/container-build.yml`
- Modify: `.trivyignore`

**Interfaces:**
- Consumes: explicit `ignore-policy` inputs in container scanning
- Produces: unchanged Rego filtering from the existing `.github/trivy/` policy directory

- [x] Move the Rego policy without changing logic.
- [x] Update both workflow inputs and the root allowlist comment.
- [x] Confirm no reference to `.trivyignore.rego` remains.
- [x] Run the smallest available Trivy policy/config validation; record a blocker if the scanner is unavailable.

### Task 5: Verify the complete root migration

**Files:**
- Verify all files changed in Tasks 1-4
- Verify: repository root tree and Git status

**Interfaces:**
- Consumes: all path migrations and reference updates
- Produces: evidence that the root has 27 entries and no unrelated work was altered

- [x] Count the working-tree root entries and confirm 27.
- [x] Run focused pre-commit checks for every changed tracked file.
- [x] Run whitespace validation and YAML parsing for changed workflow/config files.
- [x] Re-scan all tracked source for old paths and URLs.
- [x] Review the final diff for policy-content drift and unrelated edits.
- [x] Report separately what passed, what could not run locally, and which external follow-ups remain deferred.
