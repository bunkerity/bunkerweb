YAJL is built only for RHEL 10, whose configured repositories lack YAJL.
Other platforms continue using their system library.

## Source and license

- Upstream: <https://github.com/lloyd/yajl>, commit `5e3a7856e643b4d6410ddc3f84bc2f38174f2872` (unreleased 2.1.1 snapshot).
- Source archive: <https://codeload.github.com/lloyd/yajl/tar.gz/5e3a7856e643b4d6410ddc3f84bc2f38174f2872>.
- Archive SHA-256: `1523e0923b22fb9e6256083fb3372f90553646c281829d0b213c9b76dcbe4f67`.
- ISC license: `src/deps/src/yajl/COPYING`; installed as `deps/licenses/yajl.LICENSE`.

## Security patches

All three patches are copied without modification from the official Debian
`yajl_2.1.0-7.debian.tar.xz` source archive:
<https://deb.debian.org/debian/pool/main/y/yajl/yajl_2.1.0-7.debian.tar.xz>.
Archive SHA-256: `9196bd56b2a806d1b9794892dc47e994e5d76feee7a8208ee11d541b7421be78`,
matching the `Checksums-Sha256` entry in
<https://deb.debian.org/debian/pool/main/y/yajl/yajl_2.1.0-7.dsc>.
Patch headers retain upstream origins and Debian bug links.

| Patch                       | Change                                                             | SHA-256                                                            |
| --------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `yajl-CVE-2017-16516.patch` | Bound surrogate lookahead before reading string bytes.             | `dcb6f0097f46b67bc38254c706ca572f2d062f4d827b8f6dfd8335c31728dbb0` |
| `yajl-CVE-2022-24795.patch` | Check size addition and buffer doubling for overflow.              | `0ce576a63d7b9d2a66b9527bfe5ff49e62eca67551b629e5124ea952d2dbca79` |
| `yajl-CVE-2023-33460.patch` | Free pending keys, stack values and root after tree-parser errors. | `c2651de7a6cfad741c82755f0188215c62d3a9e734d9db25c05a1519ee376747` |

`deps.json` applies these patches with zero fuzz after fetching the pinned
upstream commit. The vendored tree already contains them. Do not replace it
with unpatched upstream 2.1.0 or master.

## Linkage

`install.sh` builds upstream `yajl_s` with position-independent code, exposes it
as `libyajl.a` in a private build prefix, and requires YAJL when configuring
ModSecurity. Only the archive exists in that prefix, so linking incorporates
YAJL into `libmodsecurity.so`; no YAJL shared library or build prefix is needed
on the installed host. The package's existing dependency archive includes the
ISC license. A missing header/library or failed build stops installation.
