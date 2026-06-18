#!/bin/sh
set -eu

# ------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------
log()  { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
err()  { echo "[ERROR] $*" >&2; exit 1; }

# ------------------------------------------------------------
# OS check
# ------------------------------------------------------------
[ "$(uname -s)" = "FreeBSD" ] || err "This script must be run on FreeBSD"

# ------------------------------------------------------------
# Parallelism settings
# ------------------------------------------------------------
cpu_count() {
  if command -v nproc >/dev/null 2>&1; then
    nproc
    return 0
  fi

  if command -v sysctl >/dev/null 2>&1; then
    sysctl -n hw.ncpu 2>/dev/null || true
    return 0
  fi

  echo 1
}

NCPU="$(cpu_count)"
case "$NCPU" in
  ''|*[!0-9]*|0) NCPU=1 ;;
esac

# Keep build tools aligned on the same parallelism level.
export NTASK="$NCPU"
export MAKEFLAGS="-j$NCPU"
export CMAKE_BUILD_PARALLEL_LEVEL="$NCPU"
export CARGO_BUILD_JOBS="$NCPU"
log "Using $NCPU parallel build job(s)"

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

STAGEDIR="/tmp/bunkerweb-stage"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT}"
KEEP_STAGE=0
TAR_WRAP_DIR=""
DEPS_WORKDIR=""
HOST_BW_BACKUP=""
HOST_BW_LINK_CREATED=0

if [ -n "${FPM_DEBUG:-}" ]; then
  KEEP_STAGE=1
fi

cleanup() {
  if [ "$HOST_BW_LINK_CREATED" -eq 1 ] && [ -L /usr/share/bunkerweb ]; then
    rm -f /usr/share/bunkerweb
  fi
  if [ -n "$HOST_BW_BACKUP" ] && [ -e "$HOST_BW_BACKUP" ]; then
    mv "$HOST_BW_BACKUP" /usr/share/bunkerweb
  fi
  [ -n "$DEPS_WORKDIR" ] && rm -rf "$DEPS_WORKDIR"
  if [ "$KEEP_STAGE" -eq 1 ]; then
    log "Keeping staging directory for debugging: $STAGEDIR"
    return 0
  fi
  [ -n "$TAR_WRAP_DIR" ] && rm -rf "$TAR_WRAP_DIR"
  rm -rf "$STAGEDIR"
}
trap cleanup EXIT

# ------------------------------------------------------------
# Package metadata
# ------------------------------------------------------------
PKG_NAME="bunkerweb"
WWW="https://www.bunkerweb.io"
MAINTAINER="Bunkerity <contact at bunkerity dot com>"
LICENSE="AGPLv3"
VERSION="$(tr -d '\n' < "$REPO_ROOT/src/VERSION")"
ARCH="$(uname -m)"
ABI="$(pkg config abi)"
OSVER_CURRENT="$(echo "$ABI" | awk -F: '{print $2}')"
FREEBSD_OSVERSION="${FREEBSD_OSVERSION:-$OSVER_CURRENT}"
if [ "$FREEBSD_OSVERSION" != "$OSVER_CURRENT" ]; then
  err "FREEBSD_OSVERSION=$FREEBSD_OSVERSION does not match current ABI ($OSVER_CURRENT). Build on the target OS version."
fi

# Runtime dependencies (FreeBSD-native)
# These are the ONLY packages required on a production firewall.
# No compilers, debuggers, or development tools may appear here.
PKG_DEPS="
bash
nginx
python311
py311-sqlite3
curl
libxml2
yajl
libgd
sudo
lsof
libmaxminddb
libffi
openssl
sqlite3
unzip
pcre2
lmdb
ssdeep
"

# Build-only dependencies (never shipped in the package)
BUILD_DEPS="
ruby
rubygem-fpm
gtar
pigz
rust
py311-pip
py311-setuptools
py311-wheel
postgresql18-client
git
wget
gmake
autoconf
automake
libtool
pkgconf
"

# ------------------------------------------------------------
# Ensure runtime deps exist on builder
# ------------------------------------------------------------
log "Ensuring runtime dependencies are installed..."
for p in $PKG_DEPS; do
  pkg info -e "$p" >/dev/null 2>&1 || pkg install -y "$p"
done

log "Ensuring build dependencies are installed..."
for p in $BUILD_DEPS; do
  pkg info -e "$p" >/dev/null 2>&1 || pkg install -y "$p"
done

# ------------------------------------------------------------
# Prepare staging tree
# ------------------------------------------------------------
log "Preparing staging tree..."
rm -rf "$STAGEDIR"
mkdir -p \
  "$STAGEDIR/usr/share/bunkerweb" \
  "$STAGEDIR/usr/share/bunkerweb/scripts" \
  "$STAGEDIR/usr/share/bunkerweb/rc.d" \
  "$STAGEDIR/usr/bin" \
  "$STAGEDIR/etc/newsyslog.conf.d"

BW_DIR="$STAGEDIR/usr/share/bunkerweb"

# ------------------------------------------------------------
# Build BunkerWeb-managed nginx module stack (staged)
# ------------------------------------------------------------
if [ ! -d "$REPO_ROOT/src/deps/src" ] || [ ! -d "$REPO_ROOT/src/deps/misc" ]; then
  err "Missing src/deps sources. Run: bash src/deps/init_deps.sh"
fi

log "Building BunkerWeb-managed nginx modules and Lua dependencies (staged)..."
DEPS_WORKDIR="/tmp/bunkerweb"
rm -rf "$DEPS_WORKDIR"
mkdir -p "$DEPS_WORKDIR/deps"
cp -r "$REPO_ROOT/src/deps/src" "$DEPS_WORKDIR/deps/"
cp -r "$REPO_ROOT/src/deps/misc" "$DEPS_WORKDIR/deps/"
cp "$REPO_ROOT/src/deps/install-freebsd.sh" "$DEPS_WORKDIR/deps/install-freebsd.sh"
chmod +x "$DEPS_WORKDIR/deps/install-freebsd.sh"

if [ -e /usr/share/bunkerweb ] || [ -L /usr/share/bunkerweb ]; then
  HOST_BW_BACKUP="$(mktemp -d /tmp/bunkerweb-host-prefix.XXXXXX)"
  rmdir "$HOST_BW_BACKUP"
  mv /usr/share/bunkerweb "$HOST_BW_BACKUP"
fi
mkdir -p /usr/share
ln -s "$BW_DIR" /usr/share/bunkerweb
HOST_BW_LINK_CREATED=1

/usr/local/bin/bash "$DEPS_WORKDIR/deps/install-freebsd.sh"

rm -f /usr/share/bunkerweb
HOST_BW_LINK_CREATED=0
if [ -n "$HOST_BW_BACKUP" ] && [ -e "$HOST_BW_BACKUP" ]; then
  mv "$HOST_BW_BACKUP" /usr/share/bunkerweb
  HOST_BW_BACKUP=""
fi

# ------------------------------------------------------------
# Python dependencies (staged into deps/python)
# ------------------------------------------------------------
log "Installing Python dependencies (staged)..."
PY_DEPS="$BW_DIR/deps/python"
mkdir -p "$PY_DEPS"

python3.11 -m pip install --no-cache-dir --require-hashes --break-system-packages -r "$REPO_ROOT/src/deps/requirements.txt"
python3.11 -m pip install --no-cache-dir --require-hashes --target "$PY_DEPS" \
  -r "$REPO_ROOT/src/scheduler/requirements.txt" \
  -r "$REPO_ROOT/src/ui/requirements.txt" \
  -r "$REPO_ROOT/src/api/requirements.txt" \
  -r "$REPO_ROOT/src/common/gen/requirements.txt" \
  -r "$REPO_ROOT/src/common/db/requirements.arm.txt"

log "Compressing staged dependencies (inside stage)..."
(
  cd "$BW_DIR"
  if command -v pigz >/dev/null 2>&1; then
    tar -cf deps.tar deps
    pigz -1 -p "$NCPU" deps.tar
  else
    tar -czf deps.tar.gz deps
  fi
  rm -rf deps
)

# ------------------------------------------------------------
# Copy BunkerWeb sources
# ------------------------------------------------------------
log "Copying BunkerWeb files into stage..."

cp -r "$REPO_ROOT/src/bw/loading" "$BW_DIR/"
cp -r "$REPO_ROOT/src/bw/lua" "$BW_DIR/"
cp -r "$REPO_ROOT/src/bw/misc" "$BW_DIR/"

cp -r "$REPO_ROOT/src/common/api" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/cli" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/confs" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/core" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/db" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/gen" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/helpers" "$BW_DIR/"
cp -r "$REPO_ROOT/src/common/utils" "$BW_DIR/"
cp "$REPO_ROOT/src/common/settings.json" "$BW_DIR/"

cp -r "$REPO_ROOT/src/scheduler" "$BW_DIR/"
cp -r "$REPO_ROOT/src/ui" "$BW_DIR/"
cp -r "$REPO_ROOT/src/api" "$BW_DIR/"
cp "$REPO_ROOT/src/VERSION" "$BW_DIR/"

# rc.d scripts
if [ -d "$REPO_ROOT/src/linux/rc.d" ]; then
  cp -r "$REPO_ROOT/src/linux/rc.d/." "$BW_DIR/rc.d/"
fi

# pkg lifecycle scripts
cp "$SCRIPT_DIR/scripts/beforeInstallFreeBSD.sh" "$BW_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/postinstall-freebsd.sh" "$BW_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/afterRemoveFreeBSD.sh" "$BW_DIR/scripts/" 2>/dev/null || true

# runtime service scripts required by rc.d units
cp "$SCRIPT_DIR/scripts/start.sh" "$BW_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/bunkerweb-scheduler.sh" "$BW_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/bunkerweb-ui.sh" "$BW_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/bunkerweb-api.sh" "$BW_DIR/scripts/" 2>/dev/null || true

# ------------------------------------------------------------
# bwcli wrapper (NO symlink)
# ------------------------------------------------------------
log "Creating bwcli wrapper..."
cat >"$STAGEDIR/usr/bin/bwcli" <<'EOF'
#!/bin/sh
exec /usr/local/bin/python3.11 /usr/share/bunkerweb/cli/main.py "$@"
EOF
chmod 0755 "$STAGEDIR/usr/bin/bwcli"

# ------------------------------------------------------------
# newsyslog config
# ------------------------------------------------------------
if [ -f "$SCRIPT_DIR/bunkerweb.newsyslog.conf" ]; then
  cp "$SCRIPT_DIR/bunkerweb.newsyslog.conf" \
     "$STAGEDIR/etc/newsyslog.conf.d/bunkerweb.conf"
fi

# ------------------------------------------------------------
# fpm scripts
# ------------------------------------------------------------
# Build package with fpm
# ------------------------------------------------------------
log "Creating package with fpm..."
mkdir -p "$OUTPUT_DIR"
FPM_OUTPUT="${OUTPUT_DIR}/${PKG_NAME}-${VERSION}.pkg"
rm -f "$FPM_OUTPUT"

if [ -n "${FPM_DEBUG:-}" ]; then
  log "FPM_DEBUG enabled: running tar preflight and enabling verbose fpm logging"
  FPM_DEBUG_ENABLED=1
  TAR_TEST="$(mktemp /tmp/bunkerweb-tar-test.XXXXXX.txz)"
  if ! tar -Jcf "$TAR_TEST" -C "$STAGEDIR" .; then
    err "tar preflight failed; see error above"
  fi
  rm -f "$TAR_TEST"
else
  FPM_DEBUG_ENABLED=0
fi

if command -v gtar >/dev/null 2>&1; then
  TAR_WRAP_DIR="$(mktemp -d /tmp/bunkerweb-tar-wrap.XXXXXX)"
  cat >"$TAR_WRAP_DIR/tar" <<'EOF'
#!/bin/sh
exec gtar "$@"
EOF
  chmod 0755 "$TAR_WRAP_DIR/tar"
else
  err "gtar is required for fpm FreeBSD packaging (BSD tar lacks --transform)"
fi

FPM_OSVERSION_OPT=""
FPM_BIN="${FPM_BIN:-}"

resolve_fpm_bin() {
  if [ -n "$FPM_BIN" ] && [ -x "$FPM_BIN" ]; then
    return 0
  fi

  gem_bindir="$(ruby -e 'require "rubygems"; puts Gem.bindir' 2>/dev/null || true)"
  if [ -n "$gem_bindir" ] && [ -x "$gem_bindir/fpm" ]; then
    FPM_BIN="$gem_bindir/fpm"
    return 0
  fi

  FPM_BIN="$(command -v fpm || true)"
}

fpm_supports_osversion() {
  "$FPM_BIN" --help 2>&1 | grep -q -- '--freebsd-osversion'
}

resolve_fpm_bin
if [ -z "$FPM_BIN" ] || [ ! -x "$FPM_BIN" ]; then
  err "fpm not found on PATH"
fi

if ! fpm_supports_osversion; then
  log "Upgrading fpm to a version that supports --freebsd-osversion..."
  gem install -N fpm
  resolve_fpm_bin
fi

if fpm_supports_osversion; then
  FPM_OSVERSION_OPT="--freebsd-osversion"
else
  if [ "$FREEBSD_OSVERSION" != "13" ]; then
    err "fpm does not support --freebsd-osversion after upgrade; cannot build for FreeBSD $FREEBSD_OSVERSION"
  fi
  warn "fpm does not support --freebsd-osversion; proceeding with default (FreeBSD 13)"
fi

check_script() {
  script="$1"
  [ -f "$script" ] || return 0

  if ! sh -n "$script"; then
    err "Shell syntax check failed: $script"
  fi

  if [ -n "$(LC_ALL=C tr -d '\t\n\r -~' < "$script")" ]; then
    err "Non-ASCII characters found in: $script"
  fi
}

check_script "$BW_DIR/scripts/beforeInstallFreeBSD.sh"
check_script "$BW_DIR/scripts/postinstall-freebsd.sh"
check_script "$BW_DIR/scripts/afterRemoveFreeBSD.sh"

build_deps_json() {
  python3.11 - "$1" <<'PY'
import json
import subprocess
import sys

deps = {}
raw_deps = sys.argv[1] if len(sys.argv) > 1 else ""
for dep in raw_deps.split():
    try:
        out = subprocess.check_output(["pkg", "query", "%n\t%o\t%v", dep], text=True).strip()
    except subprocess.CalledProcessError:
        continue
    if not out:
        continue
    name, origin, version = out.split("\t")
    deps[name] = {"origin": origin, "version": version}

print(json.dumps(deps, separators=(",", ":")))
PY
}

augment_pkg_manifest() {
  package_path="$1"
  deps_json="$2"
  edit_dir="$(mktemp -d /tmp/bunkerweb-pkg-edit.XXXXXX)"

  tar -xJf "$package_path" -C "$edit_dir"
  python3.11 - "$edit_dir/+MANIFEST" "$edit_dir/+COMPACT_MANIFEST" "$deps_json" <<'PY'
import json
import sys

manifest_path = sys.argv[1]
compact_manifest_path = sys.argv[2]
deps = json.loads(sys.argv[3] or "{}")

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

manifest["deps"] = deps

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, separators=(",", ":"))

with open(compact_manifest_path, "r", encoding="utf-8") as f:
    compact_manifest = json.load(f)

compact_manifest["deps"] = deps

with open(compact_manifest_path, "w", encoding="utf-8") as f:
    json.dump(compact_manifest, f, separators=(",", ":"))
PY

  (
    cd "$edit_dir"
    find etc usr \( -type f -o -type l \) | LC_ALL=C sort > .pkg-filelist
    gtar -Jcf "$package_path" --transform='s|^[^+]|/&|' +COMPACT_MANIFEST +MANIFEST -T .pkg-filelist
    rm -f .pkg-filelist
  )
  rm -rf "$edit_dir"
}

(
  cd "$STAGEDIR"
  export PATH="$TAR_WRAP_DIR:$PATH"
  set -- -s dir -t freebsd \
    -n "$PKG_NAME" \
    -v "$VERSION" \
    --architecture "$ARCH" \
    --license "$LICENSE" \
    --url "$WWW" \
    --maintainer "$MAINTAINER" \
    --description "BunkerWeb ${VERSION} for FreeBSD"

  if [ "$FPM_DEBUG_ENABLED" -eq 1 ]; then
    set -- "$@" --verbose --log debug --debug-workspace
  fi

  if [ -n "$FPM_OSVERSION_OPT" ]; then
    set -- "$@" "$FPM_OSVERSION_OPT" "$FREEBSD_OSVERSION"
  fi

  for dep in $PKG_DEPS; do
    set -- "$@" --depends "$dep"
  done

  if [ -f "$BW_DIR/scripts/beforeInstallFreeBSD.sh" ]; then
    set -- "$@" --before-install "$BW_DIR/scripts/beforeInstallFreeBSD.sh"
  fi
  if [ -f "$BW_DIR/scripts/postinstall-freebsd.sh" ]; then
    set -- "$@" --after-install "$BW_DIR/scripts/postinstall-freebsd.sh"
  fi
  if [ -f "$BW_DIR/scripts/afterRemoveFreeBSD.sh" ]; then
    set -- "$@" --after-remove "$BW_DIR/scripts/afterRemoveFreeBSD.sh"
  fi

  set -- "$@" -p "$FPM_OUTPUT" .

  "$FPM_BIN" "$@"
)

[ -f "$FPM_OUTPUT" ] || err "Package built but output file not found"

DEPS_JSON="$(build_deps_json "$PKG_DEPS")"
augment_pkg_manifest "$FPM_OUTPUT" "$DEPS_JSON"

log "Package built successfully:"
log "  $FPM_OUTPUT"
log "Install with:"
log "  pkg install -y \"$FPM_OUTPUT\""
