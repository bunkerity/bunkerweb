# Plumber

CI/CD security scanning for the GitHub Actions workflows in this repository.
[Plumber](https://getplumber.io) statically analyses `.github/workflows/` for
supply-chain and pipeline misconfigurations: unpinned or unvetted actions,
`secrets: inherit`, missing `permissions:` blocks, dangerous triggers,
template injection, cache poisoning and branch protection gaps.

It complements the existing CodeQL (source code) and OSSF Scorecard
(repository posture) workflows; none of the three overlaps with the others.

## Files

| Path | Purpose |
|---|---|
| `.plumber.yaml` | Root-discovered policy overlay on top of `plumber:default` |
| `.github/plumber/README.md` | This file |
| `.github/workflows/plumber.yml` | Reusable workflow invoked by the `dev` and `release` workflows |

## Running it locally

```bash
plumber config validate
plumber analyze --score
plumber explain ISSUE-801                  # details for a given issue code
```

Install Plumber using the [upstream instructions](https://github.com/getplumber/plumber#installation).
`plumber analyze` scans the local workflows and queries the GitHub API for
branch protection. That last control needs a token with `Administration: read`;
without it, protection findings are incomplete rather than wrong.

## Policy

`.plumber.yaml` extends `plumber:default` and only adds an allowlist of the
third-party actions this repository already relies on. Each entry names an
exact `owner/repo` rather than an owner wildcard, so trust cannot spread to
other or future repositories under those accounts. Every one of them is
pinned by commit SHA in the workflows.

## Gating

The `dev` workflow (push to `dev`) and the `release` workflow (tag push)
invoke Plumber directly, and the reusable workflow also runs weekly. It is
gated at `min-score: B` with
`soft-fail: false`, so scores of C, D or E fail the run. Results land in the
Code Scanning tab.

Every input is set explicitly in `plumber.yml`, including those that match the
action's own defaults, so that an auditor reads the effective configuration
from the workflow alone and never has to diff it against `action.yml` at some
past tag. `verify-attestation: true` keeps the sigstore/SLSA provenance check
on the downloaded binary; `score-push: true` publishes the score used by the
hosted badge service.

Each run also uploads a `plumber-report` artifact holding the JSON report, the
PBOM, the CycloneDX SBOM and the raw SARIF (`upload-artifacts: true`). The
SARIF is redundant with Code Scanning; the PBOM and SBOM are kept as
per-run evidence of what the pipeline consumed.

## Trivy is installed by hand

`container-build.yml` does not use `aquasecurity/trivy-action`. Plumber reads an
action's `action.yml` to look for code fetched at run time, and the runner's
`GITHUB_TOKEN` is refused by the aquasecurity organization's IP allow list (403).
The action then stayed "could not be verified" and Plumber scored it as an attack
path (a run-time download in the job that holds registry credentials), whatever
the action really does. The job now downloads the Trivy release asset itself and
checks it against a sha256 pinned in the workflow (`TRIVY_SHA256`), then runs
`trivy image` with the same `TRIVY_*` settings the action used.

To bump Trivy, change `TRIVY_VERSION` and `TRIVY_SHA256` together. Take the hash
from the release asset digest (`gh release view vX.Y.Z -R aquasecurity/trivy --json assets`),
download the archive and confirm it with
`gh attestation verify <archive> -R aquasecurity/trivy`. Dependabot does not track it.

If another action in an organization with an IP allow list shows up as "could not
verify", the alternative is a `PLUMBER_METADATA_TOKEN` secret (a token with
public-repository read) passed to the Plumber action as `metadata-token`.

Note that `container-build.yml` and `linux-build.yml` cannot simply declare
`packages: write`: a reusable workflow may only maintain or reduce the
caller's token scope, and those two are called both by workflows that grant
`packages: write` and push images, and by workflows that grant neither.
