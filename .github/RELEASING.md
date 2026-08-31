# Releasing BunkerWeb

Releases are triggered by pushing a tag. Merging to `master`, `rc` or `beta`
builds nothing and publishes nothing.

## One-time setup

Create a `release` **environment** in the repository settings with at least one
required reviewer.

This is not optional. `release.yml` references the environment on its `gate`
job; if the environment does not exist, GitHub creates an unprotected one on
first use and the gate passes without ever stopping. The approval step is the
only thing standing between a tag push and Docker Hub.

## Cutting a release

1. Set `src/VERSION` to the version you are releasing (`1.6.15`, `1.6.15~rc1`,
   `1.6.15~beta`) and add the matching `## v<version>` section to
   `CHANGELOG.md`. Merge that to the branch you are releasing from.
2. Tag the commit, **annotated**, and push it:

   ```bash
   git tag -a v1.6.15-rc1 -m v1.6.15-rc1
   git push origin v1.6.15-rc1
   ```

   The tag is `v` plus the version with `~` replaced by `-`. `1.6.15~rc1`
   becomes `v1.6.15-rc1`.

3. The run builds everything and stops at `gate`. Check the Trivy summaries,
   then approve the deployment in the Actions UI.
4. On approval the **draft GitHub release is created first**, before any image
   or package publishes. That draft is what stops a force-pushed tag from
   republishing later, so it has to exist before the artifacts, not after.
5. Publish the draft release by hand when you are ready.

## Channels

The channel is derived from the tag, and one workflow serves all three:

| tag            | Docker tags             | packagecloud  | docs alias   | GitHub release   |
| -------------- | ----------------------- | ------------- | ------------ | ---------------- |
| `v1.6.15`      | `:latest`, `:1.6.15`    | `1.6.15`      | `latest`     | draft            |
| `v1.6.15-rc1`  | `:rc`, `:1.6.15-rc1`    | `1.6.15~rc1`  | `rc`, hidden | draft prerelease |
| `v1.6.15-beta` | `:beta`, `:1.6.15-beta` | `1.6.15~beta` | `beta`       | draft prerelease |

## What the guards reject

`prepare` fails in seconds, before any build starts, when:

- the tag does not match `src/VERSION` at the tagged commit;
- the tag is lightweight rather than annotated;
- a GitHub release already exists for the tag (no republishing over a
  force-pushed tag);
- `CHANGELOG.md` has no `## v<version>` section.

## Things that will bite you

**Tagging a commit that predates this workflow does nothing.** A tag push runs
the workflows present at the tagged commit. If `release.yml` there still has
`on: push: branches:`, the tag fires no run at all — no error, no output. The
branch you tag from must already carry the tag-triggered `release.yml`.

**An unapproved run holds the ARM VM.** `create-arm` spins up a Scaleway
instance that `push-images` still needs, so it stays alive while the gate waits
for you. Approve promptly, or cancel the run — cancelling still triggers
`rm-arm`, which has `if: always()`.

**Nothing verifies `master` on merge any more.** Pre-tag verification is
`dev.yml` and `staging.yml`. A broken merge is caught when you tag it, where the
Trivy gate still blocks the publish.

## What the approval gate does and does not cover

The gate covers **release artifacts**: images on Docker Hub and GHCR, packages
on packagecloud, the GitHub release, and the published documentation. None of
those move before you approve.

It does not cover the shared build cache. Builds run before the gate and export
layers to `bunkerity/bw-images-cache:*` on Docker Hub as they go
(`container-build.yml`). That repo carries no version tag anyone installs, and
the behaviour predates tag-triggered releases — but "nothing reaches Docker Hub
before approval" would be the wrong thing to claim.

## Rolling channels

`dev.yml` and `staging.yml` are unchanged and still publish on every branch
push, under the literal versions `dev` and `testing`. They never publish a
semantic version, so they cannot be confused with a release.
