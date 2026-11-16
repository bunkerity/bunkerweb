# Releasing BunkerWeb

Releases are triggered by pushing a tag. Merging to `master`, `rc` or `beta`
builds nothing and publishes nothing.

## One-time setup

### The `release` environment

Create a `release` **environment** in the repository settings with at least one
required reviewer.

This is not optional. `release.yml` references the environment on its `gate`
job; if the environment does not exist, GitHub creates an unprotected one on
first use and the gate passes without ever stopping. The approval step is the
only thing standing between a tag push and Docker Hub.

### A signing key on your GitHub account

Release tags must be signed, and `prepare` refuses to build otherwise. Upload
your public key under Settings -> SSH and GPG keys, and make sure the email you
sign with is a **verified** email on that same account: GitHub reports
`unverified_email` otherwise and the guard fails.

```bash
git config --global user.signingkey <fingerprint>
git config --global tag.gpgSign true
```

### A tag ruleset on `v*`

Create a ruleset in the repository settings targeting **tags**, pattern `v*`,
enforcement active, with restrict creations, restrict updates and block force
pushes. Bypass only for the maintainers who cut releases. This is what stops a
tag being created or moved by anything holding a push token.

The ruleset rule named "require signed commits" governs the commits being
pushed, not the tag object's own signature, so it does not replace the guard in
`prepare`.

## Cutting a release

1. Set `src/VERSION` to the version you are releasing (`1.7.1`, `1.7.1~rc1`,
   `1.7.1~beta`) and add the matching `## v<version>` section to
   `CHANGELOG.md`. Merge that to the branch you are releasing from.
2. Tag the commit, **signed**, and push it:

   ```bash
   git tag -s v1.7.1-rc1 -m v1.7.1-rc1
   git push origin v1.7.1-rc1
   ```

   `-s`, not `-a`: `git tag -a` is documented as making an _unsigned_ annotated
   tag object, and the signature guard rejects it.

   The tag is `v` plus the version with `~` replaced by `-`. `1.7.1~rc1`
   becomes `v1.7.1-rc1`.

3. The run builds everything and stops at `gate`. Check the Trivy summaries,
   then approve the deployment in the Actions UI.
4. On approval the **draft GitHub release is created first**, before any image
   or package publishes. That draft is what stops a force-pushed tag from
   republishing later, so it has to exist before the artifacts, not after.
5. Wait for `push-images`, `push-packages`, `attest-assets`, and `verify-release`
   to finish. Each pushed multi-architecture index is attested for Docker Hub
   and GHCR; each packagecloud package and each draft asset (PDF, installer,
   installer checksum) gets keyless GitHub build-provenance attestation.
   `verify-release` downloads the published packages and draft assets, checks
   their recorded checksums, and verifies every attestation against this source
   commit and tag. Documentation publication waits for this job.
6. Publish the draft release by hand only after `verify-release` is green.
   An attestation failure can leave already-published images or packages:
   publication is not atomic, and a red run is not safe to announce.

## Channels

The channel is derived from the tag, and one workflow serves all three:

| tag           | Docker tags            | packagecloud | docs alias   | GitHub release   |
| ------------- | ---------------------- | ------------ | ------------ | ---------------- |
| `v1.7.1`      | `:latest`, `:1.7.1`    | `1.7.1`      | `latest`     | draft            |
| `v1.7.1-rc1`  | `:rc`, `:1.7.1-rc1`    | `1.7.1~rc1`  | `rc`, hidden | draft prerelease |
| `v1.7.1-beta` | `:beta`, `:1.7.1-beta` | `1.7.1~beta` | `beta`       | draft prerelease |

## What the guards reject

`prepare` fails in seconds, before any build starts, when:

- the tag does not match `src/VERSION` at the tagged commit;
- the tag is lightweight rather than annotated;
- the tag carries no signature GitHub can verify against a key on the signer's
  account;
- a GitHub release already exists for the tag (no republishing over a
  force-pushed tag);
- `CHANGELOG.md` has no `## v<version>` section.

## Things that will bite you

**Tagging a commit that predates this workflow does nothing.** A tag push runs
the workflows present at the tagged commit. If `release.yml` there still has
`on: push: branches:`, the tag fires no run at all — no error, no output. The
branch you tag from must already carry the tag-triggered `release.yml`.

**An expiring signing key fails the release, not the tag.** `git tag -s`
happily signs with a key that GitHub will then reject, and the run dies in
`prepare` with `expired_key`. Extend the key and **re-upload** the public key to
GitHub: it is stored at upload time and never re-fetched from a keyserver.

**An unapproved run holds the ARM VM.** `create-arm` spins up a Scaleway
instance that `push-images` still needs, so it stays alive while the gate waits
for you. Approve promptly, or cancel the run — cancelling still triggers
`rm-arm`, which has `if: always()`.

**Nothing verifies `1.7` on merge any more.** Pre-tag verification is
`1.7-dev.yml`, `dev.yml` and `staging.yml`. A broken merge is caught when you
tag it, where the Trivy gate still blocks the publish.

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

`dev.yml` runs on `dev`, `1.7-dev.yml` on `1.7`, and `staging.yml` on `staging`
or `fix-cve`. They still build packages for same-run Linux CI artifacts and
publish floating Docker tags (`dev`, `1.7-dev`, and `testing`, respectively).
They no longer publish packages to packagecloud. Only the versioned tag release
calls `push-packagecloud.yml`, which also rejects floating versions.

The Linux installer rejects `dev`, `testing`, `*-dev`, and `*-testing` package
versions, including their RPM underscore equivalents, on fresh installs and
upgrades. Use a published version or the Docker `testing` tag. The installer
attached to the Testing release keeps its bundled version default; Docker
testing requires `--docker --image-tag testing`.

## Attestation identity and first release checks

Attestations live in GitHub's attestation store. They require no signing key
and are separate from BuildKit's embedded image provenance. Image verification
uses the multi-architecture index digest, covering its platform manifests.
Use GitHub CLI `gh attestation verify` with the repository, source tag and
commit, and the appropriate signer workflow. Authenticate to the image registry
before verifying an OCI image; `verify-release` logs in to both registries:

| Subject                            | Signer workflow                                               |
| ---------------------------------- | ------------------------------------------------------------- |
| Docker Hub / GHCR index            | `bunkerity/bunkerweb/.github/workflows/push-docker.yml`       |
| Linux package                      | `bunkerity/bunkerweb/.github/workflows/push-packagecloud.yml` |
| PDF, installer, installer checksum | `bunkerity/bunkerweb/.github/workflows/release.yml`           |

The reusable workflow is the signer for images and packages, not its caller.
The pipeline additionally refuses self-hosted attestation runners. Only the
publisher jobs that attest and the `attest-assets` job receive OIDC and
attestation write permissions; `verify-release` has read permissions.

On the first real tag run, maintainers must check what local parsing cannot prove:

- The release environment still requires approval, and no publication precedes it.
- OIDC issuance and GitHub attestation writes succeed in both reusable workflows.
- All eight image indexes exist with the recorded digest on both Docker Hub and
  GHCR; all four architectures are present. `verify-release` checks 16 image subjects.
- All 20 packages (ten distros, amd64 and arm64) download from their public
  packagecloud URLs, match the uploaded bytes, and pass attestation verification.
- All three draft assets download, match the attested checksums, and verify.
  Linux packages are published to packagecloud, not attached to the draft.
- `verify-release` is green before `push-doc` and before manually publishing the
  draft. A missing or foreign attestation fails the run; never bypass that job.
- A default Linux package installation and upgrade succeed without CI's injected
  API configuration. Static workflow checks do not prove package runtime behavior.

The inventory counts are checked by `tests/unit/integrations/test_release_attestations.py`;
update them together with any future release matrix or asset change.
