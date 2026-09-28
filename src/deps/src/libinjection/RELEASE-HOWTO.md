# libinjection release howto

Comments and improvements welcome.

## Prerequisites

- GNU autotools (`autoconf`, `automake`, `libtool`)
- `clang-format` (for code formatting checks)
- `cppcheck` (for static analysis)
- `valgrind` (optional, for memory checks)

## Update the version fallback

In `src/libinjection_sqli.c`, update the default version used by embedders:

```c
#ifndef LIBINJECTION_VERSION
#define LIBINJECTION_VERSION "X.Y.Z"
#endif
```

The autotools build overrides this via `-DLIBINJECTION_VERSION=...` using
the version derived from git tags by `build-aux/git-version-gen`. This
fallback only affects users who copy the source files directly.

## Update libtool library version

In `configure.ac`, update the libtool version info (`LT_CURRENT`, `LT_REVISION`,
`LT_AGE`) following the [libtool versioning rules](https://www.gnu.org/software/libtool/manual/html_node/Updating-version-info.html):

- **Interfaces removed or changed (breaking):** increment `LT_CURRENT`, reset `LT_REVISION` and `LT_AGE` to 0
- **Interfaces added (backward-compatible):** increment `LT_CURRENT` and `LT_AGE`, reset `LT_REVISION` to 0
- **Implementation-only changes:** increment `LT_REVISION`

## Update the CHANGELOG.md file

Replace `TBD` with the release date. Make sure it looks good in markdown.

## Run the full test suite

```sh
./autogen.sh
./configure
make ci
```

This runs unit tests, static analysis, and format checks.

## Commit and tag

```sh
git add -A
git commit -m 'Release vX.Y.Z'
git tag -a vX.Y.Z -m 'vX.Y.Z'
git push origin main --tags
```

The version string is derived from the git tag by `build-aux/git-version-gen`.

## Create a GitHub release

Use the GitHub UI or CLI to create a release from the tag:

```sh
gh release create vX.Y.Z --title "vX.Y.Z" --notes "See CHANGELOG.md for details."
```

Consider attaching a source tarball (`make dist` generates one).
