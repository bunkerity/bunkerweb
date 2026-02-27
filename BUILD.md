# BUILD Guide (Community)

This guide explains how to build **community** BunkerWeb artifacts from source.

## Scope

This document covers:

- Community container images (`bunkerweb`, `scheduler`, `autoconf`, `ui`, `api`, `all-in-one`)
- Linux packages (`.deb`, `.rpm`)
- FreeBSD package (`.pkg`)

All commands are expected to be run from the repository root.

## Build Standards

- Build from a clean, up-to-date working tree.
- Use the version from `src/VERSION` (packaging scripts read it automatically).
- Keep artifacts reproducible by using the provided scripts and Dockerfiles.
- Run `pre-commit run --all-files` before opening a PR.

## Prerequisites

- For containers and Linux packages:
  - Docker (Buildx recommended)
- For FreeBSD package:
  - A native FreeBSD 14 host or VM

## Artifact Matrix

| Artifact                     | Build path                                        | Main command                              |
| ---------------------------- | ------------------------------------------------- | ----------------------------------------- |
| Community container images   | `src/*/Dockerfile`                                | `docker build -f <Dockerfile> -t <tag> .` |
| Linux packages (`deb`/`rpm`) | `src/linux/Dockerfile-*` + `src/linux/package.sh` | `./src/linux/package.sh <linux> <arch>`   |
| FreeBSD package (`pkg`)      | `src/linux/build-freebsd.sh`                      | `bash src/linux/build-freebsd.sh`         |

## Build Community Container Images

### Image targets

| Image        | Dockerfile                  |
| ------------ | --------------------------- |
| `bunkerweb`  | `src/bw/Dockerfile`         |
| `scheduler`  | `src/scheduler/Dockerfile`  |
| `autoconf`   | `src/autoconf/Dockerfile`   |
| `ui`         | `src/ui/Dockerfile`         |
| `api`        | `src/api/Dockerfile`        |
| `all-in-one` | `src/all-in-one/Dockerfile` |

### Build one image

```sh
docker build -f src/bw/Dockerfile -t local/bunkerweb:dev .
```

### Build all community images

```sh
for image in bunkerweb scheduler autoconf ui api all-in-one; do
  case "$image" in
    bunkerweb) dockerfile="src/bw/Dockerfile" ;;
    scheduler) dockerfile="src/scheduler/Dockerfile" ;;
    autoconf) dockerfile="src/autoconf/Dockerfile" ;;
    ui) dockerfile="src/ui/Dockerfile" ;;
    api) dockerfile="src/api/Dockerfile" ;;
    all-in-one) dockerfile="src/all-in-one/Dockerfile" ;;
  esac
  docker build -f "$dockerfile" -t "local/$image:dev" .
done
```

### Development-only build argument (not for production)

Use this only for local iteration on images that support minification args (`bw`, `ui`, `all-in-one`).
It reduces build time by skipping asset minification, but it does not produce production-grade artifacts.

```sh
docker build -f src/all-in-one/Dockerfile \
  --build-arg SKIP_MINIFY=yes \
  -t local/all-in-one:dev .
```

## Build Linux Packages (`.deb` / `.rpm`)

Linux package generation can be done directly with Docker in 2 steps:

1. Build the package builder image for your distro.
2. Run that image with a host output directory mounted to `/data`.

### Supported distro identifiers

- `ubuntu`
- `ubuntu-jammy`
- `debian-bookworm`
- `debian-trixie`
- `fedora-42`
- `fedora-43`
- `rhel-8`
- `rhel-9`
- `rhel-10`

### Quick local method (recommended)

This is the simplest community workflow for local package builds.
In `-v <host-dir>:/data`, you can choose any host directory you want.
Generated package files are exported by the container into that same host directory.

#### Build a `.deb` (Ubuntu example)

```sh
docker build \
  -t bunkerweb_ubuntu \
  -f src/linux/Dockerfile-ubuntu . && \
docker run --rm \
  -v "$(pwd)/out/deb:/data" \
  bunkerweb_ubuntu
```

Output:

- `<your-chosen-host-dir>/bunkerweb.deb` (for the example above: `$(pwd)/out/deb/bunkerweb.deb`)

#### Build an `.rpm` (Fedora example)

```sh
docker build \
  -t bunkerweb_fedora43 \
  -f src/linux/Dockerfile-fedora-43 . && \
docker run --rm \
  -v "$(pwd)/out/rpm:/data" \
  bunkerweb_fedora43
```

Output:

- `<your-chosen-host-dir>/bunkerweb.rpm` (for the example above: `$(pwd)/out/rpm/bunkerweb.rpm`)

### Development flags (not for production)

Use these only for local development and troubleshooting:

- `SKIP_MINIFY=yes` (`docker build --build-arg`): skips static asset minification to speed up builds; output is less optimized.
- `FPM_DEBUG=yes` (`docker run -e`): enables verbose FPM/debug logs during package creation.
- `FPM_SKIP_COMPRESSION=yes` (`docker run -e`): disables package compression to speed up packaging and simplify inspection; output packages are larger.

Do not use these flags for release artifacts intended for users.

### Development / troubleshooting example

Use this only when debugging package generation (verbose FPM logs, no compression). You can still choose any host directory mounted to `/data`, and artifacts will be written there.

```sh
docker build --build-arg SKIP_MINIFY=yes \
  -t bunkerweb_ubuntu \
  -f src/linux/Dockerfile-ubuntu . && \
docker run --rm \
  -e FPM_DEBUG=yes \
  -e FPM_SKIP_COMPRESSION=yes \
  -v "$(pwd)/out/deb:/data" \
  bunkerweb_ubuntu
```

### Scripted method (`package.sh`)

Use this if you want the repository naming convention in `package-<linux>/`.

### Step 1: build builder image

Example (`ubuntu`):

```sh
docker build -f src/linux/Dockerfile-ubuntu -t local/bunkerweb-ubuntu:latest .
```

### Step 2: build package

```sh
chmod +x src/linux/package.sh
./src/linux/package.sh ubuntu amd64
```

Artifacts are written to `package-<linux>/`.

Examples:

```sh
# Debian/Ubuntu package
docker build -f src/linux/Dockerfile-debian-bookworm -t local/bunkerweb-debian-bookworm:latest .
./src/linux/package.sh debian-bookworm amd64

# RPM package
docker build -f src/linux/Dockerfile-fedora-43 -t local/bunkerweb-fedora-43:latest .
./src/linux/package.sh fedora-43 x86_64
```

Notes:

- For RPM, use Linux arch naming (`x86_64`, `aarch64`, ...).
- For DEB, use Debian arch naming (`amd64`, `arm64`, ...).
- `curl` is a runtime requirement for scheduler ACME integrations (notably ZeroSSL/EAB flows).
- `package.sh` intentionally does not build FreeBSD packages in Docker.
- Dockerfiles for Linux package builders are preconfigured with their package type:
  - Debian/Ubuntu Dockerfiles run `fpm.sh deb`
  - Fedora/RHEL Dockerfiles run `fpm.sh rpm`

## Build FreeBSD Package (`.pkg`)

FreeBSD packages must be built on FreeBSD.

### Preflight requirements

- Use a native FreeBSD 14 host/VM.
- Run the build as `root` (or with equivalent privileges), because the build script installs packages and stages files under system paths.
- Ensure dependency sources are initialized:

```sh
bash src/deps/init_deps.sh
```

- Install build prerequisites:

```sh
pkg bootstrap -f
pkg update -f
pkg install -y bash git wget curl gtar pigz gmake pkgconf autoconf automake libtool \
  rust ruby rubygem-fpm nginx sudo lsof unzip openssl sqlite3 pcre2 lmdb ssdeep \
  libxml2 yajl libgd libmaxminddb libffi python311 py311-pip py311-setuptools \
  py311-wheel py311-sqlite3 postgresql18-client
```

**Security Note**: The final package has **zero runtime dependencies on compiler toolchains**. Only security-relevant libraries (TLS, XML parsing, GeoIP, etc.) are required at runtime, meeting security requirements for production firewall appliances.

### Quick build (recommended)

```sh
bash src/linux/build-freebsd.sh
```

Output:

- `bunkerweb-<VERSION>.pkg` (or `bunkerweb-dev.pkg`, depending on `src/VERSION`) in the repository root

### Installing the package

Before installing the BunkerWeb package on a production system, ensure runtime dependencies are installed:

```sh
pkg install -y bash nginx python311 py311-sqlite3 curl libxml2 yajl libgd \
  sudo lsof libmaxminddb libffi openssl sqlite3 unzip pcre2 lmdb ssdeep
```

**Note**: No compiler packages (gcc, clang, etc.) are required at runtime.

Then install BunkerWeb:

```sh
pkg install -y ./bunkerweb-<VERSION>.pkg
```

## CI Parity (Reference)

If you want local builds to match CI behavior, use these workflow references:

- Container builds: `.github/workflows/container-build.yml`
- Linux package builds: `.github/workflows/linux-build.yml`

## Publish Artifacts

Security baseline:

- Never paste real tokens/passwords directly in command lines or shell history.
- Prefer interactive login prompts for local/manual publishing.
- Use short-lived tokens with minimum required scopes.
- Use CI secret stores for automation.
- Unset sensitive environment variables after publishing.

### Publish Docker images (`docker.io` and `ghcr.io`)

Set your image metadata:

```sh
export VERSION="$(cat src/VERSION)"
export DOCKERHUB_ORG="<dockerhub-org-or-user>"
export GHCR_ORG="<github-org-or-user>"
```

Authenticate registries:

```sh
docker login docker.io
docker login ghcr.io -u "<github-user>"
```

Notes:

- The `docker login` commands above prompt for credentials securely (hidden input).
- For automated pipelines, read credentials from CI secrets and avoid hardcoded values.

Tag and push one image (example: `all-in-one`):

```sh
docker tag local/all-in-one:dev docker.io/$DOCKERHUB_ORG/bunkerweb-all-in-one:$VERSION
docker tag local/all-in-one:dev ghcr.io/$GHCR_ORG/bunkerweb-all-in-one:$VERSION

docker push docker.io/$DOCKERHUB_ORG/bunkerweb-all-in-one:$VERSION
docker push ghcr.io/$GHCR_ORG/bunkerweb-all-in-one:$VERSION
```

Optional rolling tag (`latest`) for stable releases only:

```sh
docker tag local/all-in-one:dev docker.io/$DOCKERHUB_ORG/bunkerweb-all-in-one:latest
docker tag local/all-in-one:dev ghcr.io/$GHCR_ORG/bunkerweb-all-in-one:latest

docker push docker.io/$DOCKERHUB_ORG/bunkerweb-all-in-one:latest
docker push ghcr.io/$GHCR_ORG/bunkerweb-all-in-one:latest
```

### Publish Linux packages to Packagecloud

Install and authenticate the `package_cloud` CLI, then upload generated packages.

Install CLI first:

```sh
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y ruby-full build-essential
sudo gem install package_cloud

# Fedora/RHEL
sudo dnf install -y ruby rubygems gcc make
sudo gem install package_cloud
```

```sh
export PACKAGECLOUD_REPO="<owner>/<repo>"
read -r -s -p "Packagecloud token: " PACKAGECLOUD_TOKEN
echo
export PACKAGECLOUD_TOKEN
```

Examples:

```sh
# Ubuntu/Debian
package_cloud push "$PACKAGECLOUD_REPO/ubuntu/jammy" package-ubuntu/*.deb
package_cloud push "$PACKAGECLOUD_REPO/debian/bookworm" package-debian-bookworm/*.deb

# Fedora/RHEL
package_cloud push "$PACKAGECLOUD_REPO/fedora/43" package-fedora-43/*.rpm
package_cloud push "$PACKAGECLOUD_REPO/el/9" package-rhel-9/*.rpm
```

Notes:

- Use the correct distribution path expected by your Packagecloud repository.
- Upload only release artifacts; avoid development flags (`SKIP_MINIFY`, `FPM_DEBUG`, `FPM_SKIP_COMPRESSION`) for publish builds.
- Verify repository retention, metadata, and signing policy before publishing.
- Run `unset PACKAGECLOUD_TOKEN` once uploads are complete.

## Quick Validation

```sh
# Check generated package files
ls -lh package-*/*.{deb,rpm} 2>/dev/null || true
ls -lh bunkerweb-*.pkg 2>/dev/null || true

# Check local images
docker image ls | grep -E 'local/(bunkerweb|scheduler|autoconf|ui|api|all-in-one)'
```
