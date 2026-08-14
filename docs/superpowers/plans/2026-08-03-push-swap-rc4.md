# Atomic push swap and no-op fast path (1.6.14~rc4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a scheduler push from emptying a live worker's plugin directory, so a missing Lua module can no longer turn every request into a 500.

**Architecture:** The instance-side upload handler currently does `rm -rf <destination>/* && cp -R <staging>/. <destination>/` on a live worker. Replace it with an entry-wise swap built on `rename(2)`, and add a fast path that skips the swap entirely when the pushed archive is byte-identical to the one already applied. The archive is made reproducible on the scheduler side so that comparison is meaningful. Swap logic moves into a new `bunkerweb.pushswap` module so it is unit-testable without nginx.

**Tech Stack:** Lua 5.1 / LuaJIT under OpenResty, `resty.sha256` and `resty.string` (lua-resty-string v0.19, installed by `src/deps/install.sh:91`), Python 3 `tarfile`/`gzip` on the scheduler side, `unittest` for Python tests, plain `lua` assert scripts for Lua tests.

## Global Constraints

- Scope of this plan is the 1.6.14~rc4 OSS items D2 and D3 only. The 1.6.15 backlog in the spec gets its own plan.
- **Never create a commit.** Every task ends by staging only. The commit command is provided for the human to run.
- Destinations may be mount points. `/data` is a declared `VOLUME` in `src/{scheduler,ui,api,autoconf,all-in-one}/Dockerfile`. Never rename or replace a destination directory itself, only its top-level entries.
- Staging and trash directories must live **inside** the destination. A sibling path can be on a different filesystem, and `rename(2)` across filesystems fails `EXDEV`.
- Reserved bookkeeping entries are dot-prefixed and must never be deleted by the stale-entry sweep.
- Lua: no busted harness exists for first-party BunkerWeb Lua. Use a plain `lua` script with an inline `it()`/`pcall` runner and `os.exit(failures == 0 and 0 or 1)`.
- Python tests use `unittest`, not pytest. flake8 needs `--max-line-length=160 --ignore=E266,E402,E501,E722,W503`.
- Black formats Python at 160 columns. stylua and luacheck (`--std min`) gate Lua.
- No em-dashes in prose. No dates, version numbers, or ticket references in code comments.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/common/utils/ApiCaller.py` (modify) | Build a reproducible archive before sending it |
| `tests/unit/test_apicaller_archive.py` (create) | Prove the archive is byte-stable across mtime changes |
| `src/bw/lua/bunkerweb/pushswap.lua` (create) | Digest, applied-marker, and entry-wise swap. No nginx dependency |
| `src/bw/lua/bunkerweb/tests/test_pushswap.lua` (create) | Unit tests against a real temp directory |
| `src/bw/lua/bunkerweb/api.lua` (modify) | Thin caller: fast path, then swap |

`pushswap.lua` deliberately takes only paths and returns `ok, err`. It requires nothing from `ngx`, which is what makes it testable outside OpenResty.

---

### Task 1: Make the pushed archive reproducible

**Files:**
- Modify: `src/common/utils/ApiCaller.py:77-88`
- Test: `tests/unit/test_apicaller_archive.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ApiCaller._build_archive(path: str) -> BytesIO`, a seeked-to-zero gzip tar whose bytes depend only on file contents and names. Task 4 relies on this being stable.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_apicaller_archive.py`:

```python
import unittest
from os import utime
from pathlib import Path
from sys import path as sys_path
from tempfile import TemporaryDirectory

sys_path.insert(0, "src/common/utils")

from ApiCaller import ApiCaller


class TestBuildArchive(unittest.TestCase):
    def _tree(self, root):
        Path(root, "a.txt").write_text("hello", encoding="utf-8")
        Path(root, "sub").mkdir()
        Path(root, "sub", "b.lua").write_text("return 1", encoding="utf-8")

    def test_identical_content_yields_identical_bytes(self):
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            self._tree(first)
            self._tree(second)
            self.assertEqual(
                ApiCaller._build_archive(first).getvalue(),
                ApiCaller._build_archive(second).getvalue(),
            )

    def test_mtime_change_does_not_change_bytes(self):
        with TemporaryDirectory() as root:
            self._tree(root)
            before = ApiCaller._build_archive(root).getvalue()
            utime(Path(root, "a.txt"), (0, 0))
            utime(Path(root, "sub", "b.lua"), (0, 0))
            self.assertEqual(before, ApiCaller._build_archive(root).getvalue())

    def test_content_change_does_change_bytes(self):
        with TemporaryDirectory() as root:
            self._tree(root)
            before = ApiCaller._build_archive(root).getvalue()
            Path(root, "a.txt").write_text("goodbye", encoding="utf-8")
            self.assertNotEqual(before, ApiCaller._build_archive(root).getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 -m unittest tests.unit.test_apicaller_archive -v`
Expected: FAIL with `AttributeError: type object 'ApiCaller' has no attribute '_build_archive'`.

- [ ] **Step 3: Add the imports**

In `src/common/utils/ApiCaller.py`, alongside the existing imports, add:

```python
from gzip import GzipFile
```

Confirm `BytesIO`, `tar_open` and `realpath` are already imported; the current `send_files` uses all three.

- [ ] **Step 4: Add `_build_archive` as a staticmethod on `ApiCaller`**

```python
    @staticmethod
    def _build_archive(path: str) -> BytesIO:
        """Build a gzip tar whose bytes depend only on file names and contents.

        Member metadata and the gzip header timestamp are normalized, so pushing
        an unchanged directory twice produces the same bytes. Instances compare
        that digest to skip a push that would change nothing. Mirrors
        create_plugin_tar_gz, which normalizes for the same reason.
        """

        def normalize(tarinfo):
            tarinfo.mtime = 0
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = "root"
            tarinfo.gname = "root"
            return tarinfo

        with BytesIO() as raw:
            with tar_open(fileobj=raw, mode="w") as tar:
                # top-level path may itself be a symlink (resolve it); nested symlinks must stay symlinks (no dereference)
                tar.add(realpath(path), arcname=".", filter=normalize)
            raw_bytes = raw.getvalue()

        result = BytesIO()
        with GzipFile(fileobj=result, mode="wb", compresslevel=3, mtime=0) as gz:
            gz.write(raw_bytes)
        result.seek(0)
        return result
```

`TarFile.add` walks directories in sorted order, so member ordering is already deterministic.

- [ ] **Step 5: Rewrite `send_files` to use it**

Replace the body of `send_files` (`src/common/utils/ApiCaller.py:77-88`) with:

```python
    def send_files(self, path: str, url: str, timeout=(5, 10), response: bool = False) -> Union[bool, Tuple[bool, Optional[Dict[str, Any]]]]:
        with self._build_archive(path) as tgz:
            files = {"archive.tar.gz": tgz}
            ret = self.send_to_apis("POST", url, files=files, timeout=timeout, response=response)
            if response:
                return ret[0], ret[1]
            return ret[0]
```

- [ ] **Step 6: Run the tests and the linters**

Run: `python3 -m unittest tests.unit.test_apicaller_archive -v`
Expected: 3 tests, OK.

Run: `black --line-length 160 src/common/utils/ApiCaller.py tests/unit/test_apicaller_archive.py`
Run: `flake8 --max-line-length=160 --ignore=E266,E402,E501,E722,W503 src/common/utils/ApiCaller.py tests/unit/test_apicaller_archive.py`
Expected: no output from flake8.

- [ ] **Step 7: Confirm no consumer depends on preserved mtimes**

Run: `grep -rn "getmtime\|st_mtime\|\.stat()" --include="*.py" src/common/core src/scheduler | grep -iE "cache|nginx|plugin"`
Expected: no hit that reads a file mtime under `/var/cache/bunkerweb`, `/etc/nginx` or the plugin directories. The job cache keys off database records rather than filesystem mtimes. If a hit exists, stop and report it before continuing; it would mean normalizing mtimes changes behaviour.

- [ ] **Step 8: Stage**

```bash
git add src/common/utils/ApiCaller.py tests/unit/test_apicaller_archive.py
```

Suggested message for the human to run:

```
fix(api): build a reproducible archive so an unchanged push can be detected
```

---

### Task 2: `pushswap` digest and applied marker

**Files:**
- Create: `src/bw/lua/bunkerweb/pushswap.lua`
- Test: `src/bw/lua/bunkerweb/tests/test_pushswap.lua`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `pushswap.digest_file(path) -> hex_string|nil, err` — streaming SHA-256, lowercase hex.
  - `pushswap.applied_path(destination) -> string` — path of the marker file.
  - `pushswap.read_applied(destination) -> hex_string|nil` — nil when absent or unreadable.
  - `pushswap.write_applied(destination, hex) -> ok, err`
  - `pushswap.RESERVED_PREFIX = ".bw-"` — Task 3 and Task 4 both use this.

- [ ] **Step 1: Write the failing test**

Create `src/bw/lua/bunkerweb/tests/test_pushswap.lua`:

```lua
-- Plain lua runner. There is no busted harness for first-party BunkerWeb Lua.
local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	if ok then
		print("ok   - " .. name)
	else
		failures = failures + 1
		print("FAIL - " .. name .. ": " .. tostring(err))
	end
end

local here = arg[0]:match("(.*)/[^/]*$")
package.path = here .. "/../../?.lua;" .. package.path

local pushswap = require "bunkerweb.pushswap"

local function tmpdir()
	local path = os.tmpname()
	os.remove(path)
	assert(os.execute("mkdir -p " .. path) == 0 or os.execute("mkdir -p " .. path))
	return path
end

local function write(path, content)
	local fh = assert(io.open(path, "w"))
	fh:write(content)
	fh:close()
end

it("digest_file matches the known sha256 of 'hello'", function()
	local dir = tmpdir()
	write(dir .. "/f", "hello")
	local hex = assert(pushswap.digest_file(dir .. "/f"))
	assert(hex == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "got " .. hex)
	os.execute("rm -rf " .. dir)
end)

it("digest_file returns nil for a missing file", function()
	local hex = pushswap.digest_file("/nonexistent/nope")
	assert(hex == nil)
end)

it("applied marker round-trips", function()
	local dir = tmpdir()
	assert(pushswap.read_applied(dir) == nil)
	assert(pushswap.write_applied(dir, "abc123"))
	assert(pushswap.read_applied(dir) == "abc123")
	os.execute("rm -rf " .. dir)
end)

print("")
print(string.format("%d passed, %d failed", 3 - failures, failures))
os.exit(failures == 0 and 0 or 1)
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Expected: FAIL, `module 'bunkerweb.pushswap' not found`.

- [ ] **Step 3: Create the module**

Create `src/bw/lua/bunkerweb/pushswap.lua`:

```lua
-- Filesystem swap helpers for the instance-side push endpoints.
-- Deliberately free of any ngx dependency so it can be unit tested outside OpenResty.
local sha256 = require "resty.sha256"
local str = require "resty.string"

local to_hex = str.to_hex
local open = io.open

local pushswap = {}

-- Bookkeeping entries live inside the destination so renames stay on one
-- filesystem. They are dot-prefixed so a glob or an nginx include never picks
-- them up, and the stale-entry sweep skips anything carrying this prefix.
pushswap.RESERVED_PREFIX = ".bw-"

local APPLIED = ".bw-applied"
local CHUNK = 65536

function pushswap.digest_file(path)
	local fh = open(path, "rb")
	if not fh then
		return nil, "cannot open " .. path
	end
	local hash = sha256:new()
	while true do
		local chunk = fh:read(CHUNK)
		if not chunk or chunk == "" then
			break
		end
		hash:update(chunk)
	end
	fh:close()
	return to_hex(hash:final())
end

function pushswap.applied_path(destination)
	return destination .. "/" .. APPLIED
end

function pushswap.read_applied(destination)
	local fh = open(pushswap.applied_path(destination), "r")
	if not fh then
		return nil
	end
	local hex = fh:read("*l")
	fh:close()
	if not hex or hex == "" then
		return nil
	end
	return hex
end

function pushswap.write_applied(destination, hex)
	local fh, err = open(pushswap.applied_path(destination), "w")
	if not fh then
		return false, err
	end
	fh:write(hex, "\n")
	fh:close()
	return true
end

return pushswap
```

- [ ] **Step 4: Run the test**

Run: `lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Expected: `3 passed, 0 failed`, exit 0.

If `resty.sha256` is not resolvable from plain `lua`, the module is OpenResty-only. In that case set `package.loaded["resty.sha256"]` and `package.loaded["resty.string"]` to stubs at the top of the test, before the `require`, following the stubbing pattern used by `src/common/core/crowdsec/tests/test_bouncer_cache_namespace.lua`, and assert the digest calls rather than the hash value.

- [ ] **Step 5: Lint**

Run: `stylua src/bw/lua/bunkerweb/pushswap.lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Run: `luacheck --std min src/bw/lua/bunkerweb/pushswap.lua`
Expected: no warnings.

- [ ] **Step 6: Stage**

```bash
git add src/bw/lua/bunkerweb/pushswap.lua src/bw/lua/bunkerweb/tests/test_pushswap.lua
```

Suggested message:

```
feat(api): add pushswap digest and applied-marker helpers
```

---

### Task 3: Entry-wise swap with rollback

**Files:**
- Modify: `src/bw/lua/bunkerweb/pushswap.lua`
- Modify: `src/bw/lua/bunkerweb/tests/test_pushswap.lua`

**Interfaces:**
- Consumes: `pushswap.RESERVED_PREFIX` from Task 2.
- Produces: `pushswap.swap(destination, staging) -> ok, err`. Renames every top-level entry of `staging` into `destination`, removes destination entries that staging does not have, and restores everything on failure. Task 4 calls exactly this.

- [ ] **Step 1: Add the failing tests**

Append to `src/bw/lua/bunkerweb/tests/test_pushswap.lua`, before the summary lines:

```lua
it("swap replaces changed entries and adds new ones", function()
	local dest = tmpdir()
	os.execute("mkdir -p " .. dest .. "/keep " .. dest .. "/change")
	write(dest .. "/keep/f", "same")
	write(dest .. "/change/f", "old")

	local staging = dest .. "/.bw-staging-test"
	os.execute("mkdir -p " .. staging .. "/keep " .. staging .. "/change " .. staging .. "/added")
	write(staging .. "/keep/f", "same")
	write(staging .. "/change/f", "new")
	write(staging .. "/added/f", "brand new")

	assert(pushswap.swap(dest, staging))

	local fh = assert(io.open(dest .. "/change/f"))
	assert(fh:read("*a") == "new")
	fh:close()
	fh = assert(io.open(dest .. "/added/f"))
	assert(fh:read("*a") == "brand new")
	fh:close()
	os.execute("rm -rf " .. dest)
end)

it("swap removes entries that staging does not have", function()
	local dest = tmpdir()
	os.execute("mkdir -p " .. dest .. "/stale")
	write(dest .. "/stale/f", "bye")
	local staging = dest .. "/.bw-staging-test"
	os.execute("mkdir -p " .. staging .. "/fresh")
	write(staging .. "/fresh/f", "hi")

	assert(pushswap.swap(dest, staging))

	assert(io.open(dest .. "/stale/f") == nil, "stale entry survived")
	assert(io.open(dest .. "/fresh/f") ~= nil, "fresh entry missing")
	os.execute("rm -rf " .. dest)
end)

it("swap never deletes reserved bookkeeping entries", function()
	local dest = tmpdir()
	assert(pushswap.write_applied(dest, "deadbeef"))
	local staging = dest .. "/.bw-staging-test"
	os.execute("mkdir -p " .. staging .. "/only")
	write(staging .. "/only/f", "x")

	assert(pushswap.swap(dest, staging))

	assert(pushswap.read_applied(dest) == "deadbeef", "applied marker was swept away")
	os.execute("rm -rf " .. dest)
end)
```

Update the summary line count from `3 - failures` to `6 - failures`.

- [ ] **Step 2: Run to confirm they fail**

Run: `lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Expected: the three new cases FAIL with `attempt to call field 'swap' (a nil value)`.

- [ ] **Step 3: Implement `swap`**

Add to `src/bw/lua/bunkerweb/pushswap.lua`, above `return pushswap`:

```lua
local function list_entries(path)
	local entries = {}
	-- popen is used only for the directory listing; the swap itself is rename(2).
	local pipe = io.popen("ls -A1 '" .. path .. "' 2>/dev/null")
	if not pipe then
		return entries
	end
	for name in pipe:lines() do
		if name ~= "" then
			entries[#entries + 1] = name
		end
	end
	pipe:close()
	return entries
end

local function is_reserved(name)
	return name:sub(1, #pushswap.RESERVED_PREFIX) == pushswap.RESERVED_PREFIX
end

-- Replace the top-level entries of destination with those of staging.
-- The destination directory itself is never renamed: it may be a mount point,
-- and renaming a mount point fails with EBUSY.
function pushswap.swap(destination, staging)
	local trash = destination .. "/" .. pushswap.RESERVED_PREFIX .. "trash"
	os.execute("rm -rf '" .. trash .. "' && mkdir -p '" .. trash .. "'")

	local undo = {}
	local function rollback()
		for i = #undo, 1, -1 do
			os.rename(undo[i].from, undo[i].to)
		end
		os.execute("rm -rf '" .. trash .. "'")
	end

	local incoming = {}
	for _, name in ipairs(list_entries(staging)) do
		incoming[name] = true
		local target = destination .. "/" .. name
		if io.open(target, "r") or os.rename(target, target) then
			local parked = trash .. "/" .. name
			local ok, err = os.rename(target, parked)
			if not ok then
				rollback()
				return false, "cannot park " .. name .. ": " .. tostring(err)
			end
			undo[#undo + 1] = { from = parked, to = target }
		end
		local ok, err = os.rename(staging .. "/" .. name, target)
		if not ok then
			rollback()
			return false, "cannot place " .. name .. ": " .. tostring(err)
		end
	end

	for _, name in ipairs(list_entries(destination)) do
		if not incoming[name] and not is_reserved(name) then
			local ok, err = os.rename(destination .. "/" .. name, trash .. "/" .. name)
			if not ok then
				rollback()
				return false, "cannot sweep " .. name .. ": " .. tostring(err)
			end
			undo[#undo + 1] = { from = trash .. "/" .. name, to = destination .. "/" .. name }
		end
	end

	os.execute("rm -rf '" .. trash .. "' '" .. staging .. "'")
	return true
end
```

Note on the existence probe: `io.open` on a directory returns nil on most systems, so the `os.rename(target, target)` fallback is what detects an existing directory. Renaming a path onto itself succeeds and changes nothing.

- [ ] **Step 4: Run the tests**

Run: `lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Expected: `6 passed, 0 failed`, exit 0.

- [ ] **Step 5: Lint**

Run: `stylua src/bw/lua/bunkerweb/pushswap.lua src/bw/lua/bunkerweb/tests/test_pushswap.lua`
Run: `luacheck --std min src/bw/lua/bunkerweb/pushswap.lua`
Expected: no warnings.

- [ ] **Step 6: Stage**

```bash
git add src/bw/lua/bunkerweb/pushswap.lua src/bw/lua/bunkerweb/tests/test_pushswap.lua
```

Suggested message:

```
feat(api): swap pushed directories entry by entry instead of wiping them
```

---

### Task 4: Wire the handler to the fast path and the swap

**Files:**
- Modify: `src/bw/lua/bunkerweb/api.lua:263-340`

**Interfaces:**
- Consumes: `pushswap.digest_file`, `pushswap.read_applied`, `pushswap.write_applied`, `pushswap.swap`, `pushswap.RESERVED_PREFIX` from Tasks 2 and 3; the reproducible archive from Task 1.
- Produces: no new interface. `POST /confs` and its five aliases keep their existing request and response contract.

- [ ] **Step 1: Add the require**

In the header block of `src/bw/lua/bunkerweb/api.lua`, next to the other `bunkerweb.*` requires, add:

```lua
local pushswap = require "bunkerweb.pushswap"
```

- [ ] **Step 2: Replace the command block**

In `api.global.POST["^/confs$"]`, delete the `local staging` / `local backup` / `local cmds` block and the `for _, cmd in ipairs(cmds)` loop (`api.lua:304-338`), and put in its place:

```lua
	-- An unchanged push is the common case, because the scheduler sends this
	-- directory on every start whether or not anything changed. Skipping it
	-- means a live worker never sees its plugin tree disappear for no reason.
	local digest = pushswap.digest_file(tmp)
	if digest and pushswap.read_applied(destination) == digest then
		os.remove(tmp)
		return self:response(HTTP_OK, "success", "already applied at " .. destination)
	end

	local staging = destination .. "/" .. pushswap.RESERVED_PREFIX .. "staging"
	if execute("rm -rf '" .. staging .. "' && mkdir -p '" .. staging .. "' && tar xzf '" .. tmp .. "' -C '" .. staging .. "'") ~= 0 then
		execute("rm -rf '" .. staging .. "'")
		os.remove(tmp)
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "cannot extract archive")
	end

	local ok, err = pushswap.swap(destination, staging)
	os.remove(tmp)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
	end

	if digest then
		pushswap.write_applied(destination, digest)
	end
	return self:response(HTTP_OK, "success", "saved data at " .. destination)
```

- [ ] **Step 3: Confirm no reserved entry can leak into a config include**

Run: `grep -rn "include" src/common/confs/*.conf | grep -E "\*"`
Expected: every wildcard include targets a suffix such as `*.conf`. A dot-prefixed directory named `.bw-staging` or `.bw-trash` matches none of them, and `.bw-applied` has no `.conf` suffix. If any include is a bare `*`, stop and report it; the reserved names would then be parsed by nginx.

- [ ] **Step 4: Lint**

Run: `stylua src/bw/lua/bunkerweb/api.lua`
Run: `luacheck --std min src/bw/lua/bunkerweb/api.lua`
Expected: no warnings. In particular no unused-local warning for the removed `backup` variable.

- [ ] **Step 5: Stage**

```bash
git add src/bw/lua/bunkerweb/api.lua
```

Suggested message:

```
fix(api): skip an unchanged push and swap directories atomically
```

---

### Task 5: Prove it against the running stack

`tests/` is deprecated in this repo. Verification runs against the dev compose.

**Files:**
- No source changes. This task produces evidence.

- [ ] **Step 1: Build and start the stack**

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml build
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

Check first that nothing else is bound to the `10.20.30.0/24` `bw-universe` subnet; stop any other stack using it.

- [ ] **Step 2: Reproduce the failure on the current code**

Do this on a checkout **without** Tasks 1 to 4 applied, so the run is meaningful. Drive continuous traffic at the instance while forcing a plugin push:

```bash
while true; do curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: www.example.com' http://127.0.0.1/ ; done > /tmp/codes.txt &
docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-scheduler
sleep 60 && kill %1
sort /tmp/codes.txt | uniq -c
```

Expected on unfixed code: a non-zero count of `500`.

- [ ] **Step 3: Apply Tasks 1 to 4 and repeat**

Rebuild all images, no service arguments:

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml build
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

Re-run Step 2's loop.
Expected: zero `500` responses.

- [ ] **Step 4: Prove the fast path does nothing on a repeat push**

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml exec bw-scheduler \
  sh -c 'ls -la --time-style=full-iso /etc/bunkerweb/pro/plugins | head'
docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-scheduler
sleep 45
docker compose -f misc/dev/docker-compose.ui.api.yml exec bw-scheduler \
  sh -c 'ls -la --time-style=full-iso /etc/bunkerweb/pro/plugins | head'
```

Expected: identical inode timestamps across the restart, and the instance log carries `already applied at /etc/bunkerweb/pro/plugins`. Run the same `ls` inside a `bunkerweb` worker container, which is where the swap actually happens.

- [ ] **Step 5: Record the evidence**

Paste the real `uniq -c` counts from Steps 2 and 3 and the log line from Step 4 into the ticket #401 reply draft at
`/tmp/claude-1000/-home-bunkerity-dev-bunkerweb-dev/01235643-f39c-4d46-aae5-0ffd347d1b7c/scratchpad/reply-401-draft.md`.
Do not claim the fix is verified without those numbers.

- [ ] **Step 6: Add the changelog entry**

In `CHANGELOG.md`, under the current `v1.6.14~rc4` heading, add:

```
- [BUGFIX] `api`: a configuration or plugin push no longer empties the target directory on a live instance while it copies the new one in, which made every request fail while the copy ran. Entries are now swapped individually, and a push whose content is unchanged is skipped entirely.
```

- [ ] **Step 7: Stage**

```bash
git add CHANGELOG.md
```

Suggested message:

```
docs: changelog for the atomic push swap
```

---

## Self-Review

**Spec coverage.** Spec section 3 (entry-wise swap, mount-point safety, staging inside the destination, rollback via trash, reserved names) maps to Tasks 2, 3 and 4. Section 4 (deterministic `send_files`, instance-side digest, version-skew safety) maps to Tasks 1 and 4. Section 6 (verification against the dev compose, the hold-traffic-during-push check) maps to Task 5. Section 3.4's open check on nginx includes is Task 4 Step 3. Section 4.5's open check on mtimes is Task 1 Step 7. Sections 5 and 2's 1.6.15 rows are deliberately out of scope and are stated as such in Global Constraints.

**Placeholders.** None. Every code step carries the code. Every run step carries the command and the expected result.

**Type consistency.** `pushswap.digest_file`, `read_applied`, `write_applied`, `applied_path`, `swap` and `RESERVED_PREFIX` are defined in Task 2 or 3 and used under those exact names in Tasks 3 and 4. `ApiCaller._build_archive` is defined and consumed under one name.

**Known soft spot.** Task 3 Step 3 probes for an existing entry with `io.open` plus an `os.rename(target, target)` fallback, because plain Lua has no `stat`. If that proves unreliable during implementation, replace it with a single `ls -A1` of the destination collected once and used as a set, which the module already builds for the sweep.

---

## Execution Handoff

Two execution options:

1. **Subagent-driven (recommended)** - a fresh subagent per task, review between tasks.
2. **Inline execution** - tasks run in this session with checkpoints.
