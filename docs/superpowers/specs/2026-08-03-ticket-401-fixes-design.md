# Ticket #401 remediation design

Origin: WHMCS #401 (#RNU-582487), Intercom Solutions. On 2026-08-01 both of the customer's
BunkerWeb WAF workers returned HTTP 500 on every request and HAProxy removed the whole pool.

## 1. Root cause

Three stacked defects, all ours.

**D1. The PRO `ui_sso` NGINX fragment had no enable gate.** `dev/ui_sso/confs/server-http/sso-connecting-ip.conf`
and `dev/ui_sso/confs/default-server-http/sso-connecting-ip.conf` were byte-identical three-line files
containing a bare `require("ui_sso.lib.sso_headers").rewrite()` inside `server_rewrite_by_lua_block`,
with no `{% if USE_UI_SSO %}`. `USE_UI_SSO` defaults to `no`. Every sibling PRO plugin gates its
fragment (`prometheus_exporter`, `antiddos`, `acme`); `ui_sso` was the only outlier. A disabled
feature therefore executed unguarded Lua on every request to every vhost and the default server.

**D2. The instance-side push handler replaces directories non-atomically.**
`src/bw/lua/bunkerweb/api.lua:315-328`, shared by `/confs`, `/cache`, `/custom_configs`, `/plugins`
and `/pro_plugins` via `api.lua:350`, runs:

```
rm -rf <destination>/* && cp -R <staging>/. <destination>/
```

on a live worker via `os.execute`. For `/pro_plugins` the destination is `/etc/bunkerweb/pro/plugins`,
which is on `lua_package_path` (`src/common/confs/http.conf:57`). For the duration of the copy,
`ui_sso/lib/sso_headers.lua` does not exist. Byte-identical at v1.6.11, v1.6.12, v1.6.13 and dev HEAD.

**D3. The push is unconditional.** The checksum at `src/scheduler/main.py:390-392` is scheduler-local
(it only skips re-extraction on the scheduler). The send at `main.py:432-434` is gated only on
`if send and SCHEDULER and SCHEDULER.apis`, with no change comparison, and `SCHEDULER.apis` is
populated from the database at `main.py:867-869` before `check_plugin_changes` runs. Every scheduler
start therefore re-wipes and re-copies the workers' plugin tree even when nothing changed.

`server_rewrite_by_lua` runs before `NGX_HTTP_FIND_CONFIG_PHASE`, so an aborted Lua thread there
returns 500 (`ngx_http_lua_util.c:1620-1621`) before any location is selected. The scheduler fans
pushes out to all instances in parallel (`src/common/utils/ApiCaller.py:48`), so both workers entered
the window simultaneously and no healthy node remained.

Amplifier, not a cause: `apt-daily-upgrade.timer` (Ubuntu default 06:00 with up to 60 minutes of
jitter) restarts the BunkerWeb units. In the customer's own scheduler log, 43 of 91 scheduler starts
between 2026-01-24 and 2026-07-10 fell in the 06:00-07:59 window, on 43 distinct mornings.

## 2. Scope and release split

Decision taken: outage chain ships in 1.6.14~rc4, hardening and adjacent defects in 1.6.15.

| Item | Repo | Release |
| --- | --- | --- |
| D1 `USE_UI_SSO` gate + fail-closed require guard | PRO | rc4 (**done**, commit `7e5d546`) |
| D2 entry-wise atomic swap in the push handler | OSS | rc4 |
| D3 no-op push fast path | OSS | rc4 |
| Per-request staging and trash paths | OSS | 1.6.15 |
| Move blocking extraction off the worker event loop | OSS | 1.6.15 |
| `default-server-cert.py` certificate/key match validation | OSS | 1.6.15 |
| `Database.py` method-mismatch stranding PRO plugin rows | OSS | 1.6.15 |
| Split `_topn_*` trackers out of the `monitoring_metrics` shdict | PRO | 1.6.15 |
| `monitoring/CLAUDE.md` documents whitespace separator as comma | PRO | 1.6.15 |

## 3. D2 design: entry-wise atomic swap

### 3.1 Why the destination directory itself is never renamed

The obvious "rename the destination aside, rename the new tree in" is unsafe here. `/data` is a
declared `VOLUME` in `src/{scheduler,ui,api,autoconf,all-in-one}/Dockerfile` and a named volume in
`misc/dev/docker-compose.ui.api.yml`, and it is a push destination (`api.lua:268-269`). Renaming a
mount point fails `EBUSY`. `/var/cache/bunkerweb` and `/etc/bunkerweb` may also be mounted in some
deployments.

Staging must also live **inside** the destination rather than beside it. A sibling `/data.staging`
would sit on the root filesystem while `/data` is the volume, so `rename(2)` between them fails
`EXDEV`. Placing staging inside the destination guarantees the same filesystem by construction.

### 3.2 Algorithm

```
1. extract archive     -> <destination>/.bw-staging-<token>/
2. for each top-level entry e in staging:
     dest/e absent     -> rename(staging/e, dest/e)
     otherwise         -> rename(dest/e, trash/e) ; rename(staging/e, dest/e)
3. for each top-level entry in dest that is not in staging and is not one of ours:
                       -> rename(dest/e, trash/e)
4. rm -rf trash, staging
```

Step 1 is non-destructive: the destination is fully intact while the archive extracts. The window in
which a given entry is absent collapses from a full `cp -R` of the tree to two adjacent `rename`
syscalls.

### 3.3 Rollback

`trash/` replaces the current `cp -R <dest>/. <backup>/` full backup. Because trash is inside the
destination, restoring is a rename rather than a second full copy, so the push performs roughly half
the I/O it does today. On any failure in steps 2 or 3, rename everything in trash back.

### 3.4 Reserved names

Staging, trash and the applied-hash marker live inside the destination and must be invisible to
consumers. Dot-prefixed names are not matched by Python's `Path.glob("*")` (leading dots are special)
nor by nginx `include *.conf`. Step 3 must exclude these reserved entries or it will delete its own
bookkeeping.

**Open implementation check:** verify against the real `include` directives rendered into `/etc/nginx`
that no pattern picks up a dot-prefixed directory before relying on this.

## 4. D3 design: no-op push fast path

### 4.1 This is not a wire-protocol change

`create_plugin_tar_gz` (`src/common/utils/common_utils.py:320`) is already deterministic by design:
it builds an uncompressed tar, then compresses with `GzipFile(..., mtime=0)`. Its docstring states
"the same directory content always produces identical bytes (and therefore the same SHA-256 checksum)".

`ApiCaller.send_files` (`src/common/utils/ApiCaller.py:77`) is not. It uses
`tar_open(mode="w:gz", fileobj=tgz, compresslevel=3)`, which writes the current time into the gzip
header, and `tf.add(realpath(path), arcname=".")`, which preserves each file's real mtime, uid and gid.
Two pushes of identical content therefore produce different bytes today.

### 4.2 Change

- **Scheduler:** make `send_files` deterministic, mirroring the existing `create_plugin_tar_gz`
  precedent: normalise member metadata (`mtime=0`, `uid=0`, `gid=0`, `uname`/`gname` fixed) and set
  the gzip `mtime=0`.
- **Instance:** after writing the uploaded archive to its temp path, take its SHA-256. Compare against
  `<destination>/.bw-applied`. If equal, delete the temp file, return success, and touch nothing at
  all. Otherwise perform the swap in section 3 and write the new hash on success.

### 4.3 Why this is safe across versions

No handshake and no negotiated field. An old scheduler pushing non-deterministic archives simply
never produces a matching hash, so a new instance always falls through to the full swap. A new
scheduler talking to an old instance is ignored. Both directions degrade to current behaviour.

### 4.4 Why it matters

The push is unconditional (D3), so in normal operation most pushes rewrite a byte-identical tree.
Today that means a guaranteed multi-second window on every scheduler restart in exchange for nothing.
With the fast path, a no-op push mutates nothing, and the 2026-08-01 outage would not have occurred
even without the D1 gate.

### 4.5 Risk to check during implementation

Normalising member mtimes means files extracted on the instance carry `mtime=0`. Confirm nothing on
the instance side keys off file mtimes under `/var/cache/bunkerweb` or `/etc/nginx`; the job cache
uses database records rather than filesystem mtimes, but this must be verified rather than assumed.
Normalising uid/gid is expected to be inert because extraction runs as the `nginx` user, which cannot
apply ownership from the archive, but confirm this too.

## 5. Blocking extraction

Reframed from the original assessment. Extraction happens before anything destructive, so a slow
`tar` is a latency problem rather than an availability one. It is worth moving off the worker event
loop for `/cache`, which is the largest tree, but it is not on the outage path. Deferred to 1.6.15.

## 6. Verification

`tests/` is deprecated in this repo; verification is done against `misc/dev/docker-compose.ui.api.yml`.

The check that actually matters, and that must fail before the fix and pass after it: hold traffic
against a worker while forcing a `/pro_plugins` push, and assert no request returns 500. A second
check asserts that a repeated identical push performs no filesystem mutation at all.

Also required, per repo convention: `pre-commit run --all-files` for anything touched, and for Lua
the plain `lua` assert-script pattern rather than a new harness, since this repo family has no busted
setup for first-party Lua.

## 7. Outstanding decision, not covered here

`dev/ui_sso/plugin.json` was hand-bumped to `0.65` while the other 17 PRO plugins remain at `0.64`.
`CHANGELOG.md` states versions are bumped in lockstep by `misc/update_version.sh`, and the `versions/`
tree is generated from it. Either revert that line or run the script across all 18. This is a release
decision and is deliberately left open.
