#!/bin/bash

# BunkerWeb Easy Install Script
# Automatically installs BunkerWeb on supported Linux distributions

set -e

# Skip debconf prompts; fatal under --quiet/CI. Ignored on dnf/pkg/rc.d.
export DEBIAN_FRONTEND=noninteractive

# Registry of 0600 secret tempfiles wiped on every exit path (DB option files, PGPASSFILE, etc.).
declare -a _BW_SECRET_TMPFILES=()
_bw_register_secret_tmpfile() {
    _BW_SECRET_TMPFILES+=("$1")
}
_bw_wipe_secret_tmpfiles() {
    local _f
    for _f in "${_BW_SECRET_TMPFILES[@]:-}"; do
        [ -n "$_f" ] || continue
        if [ -e "$_f" ]; then
            shred -u "$_f" 2>/dev/null || rm -f "$_f"
        fi
    done
    _BW_SECRET_TMPFILES=()
}

# EXIT hook — runs on every exit path (normal, error, signal). Keep callees idempotent.
_bw_install_cleanup() {
    # Wipe plaintext credential tempfiles first.
    _bw_wipe_secret_tmpfiles
    # _gum_cleanup defined later; guard against early-exit.
    if declare -F _gum_cleanup >/dev/null 2>&1; then
        _gum_cleanup
    fi
}
trap _bw_install_cleanup EXIT

# Graceful Ctrl+C / SIGTERM handler — prints one ack line, exits 128+sig so wrappers can detect cause.
# Clear handlers FIRST to prevent re-entry on a second Ctrl+C between warning and exit.
_bw_install_interrupt() {
    local signal="${1:-INT}"
    trap - INT TERM HUP QUIT
    # Move past any half-rendered TUI line.
    printf '\n' >&2
    if declare -F print_warning >/dev/null 2>&1; then
        if [ -f "${_BW_STATE_FILE:-}" ]; then
            print_warning "Installation aborted (SIG${signal}). Progress was saved — re-run the installer and it will offer to resume."
        else
            print_warning "Installation aborted (SIG${signal}). Partial state may remain — re-run the installer to start over."
        fi
    else
        printf 'Installation aborted (SIG%s).\n' "$signal" >&2
    fi
    # EXIT trap still runs after this exit and wipes secret tempfiles.
    case "$signal" in
        INT)  exit 130 ;;
        TERM) exit 143 ;;
        HUP)  exit 129 ;;
        QUIT) exit 131 ;;
        *)    exit 1   ;;
    esac
}
# Reset inherited "ignore" disposition (nohup/setsid/CI runners) so our handler installs.
trap - INT TERM HUP QUIT 2>/dev/null || true
trap '_bw_install_interrupt INT'  INT
trap '_bw_install_interrupt TERM' TERM
# SIGHUP: SSH disconnect — without handler some shells skip EXIT trap, leaking tempfiles.
trap '_bw_install_interrupt HUP'  HUP
trap '_bw_install_interrupt QUIT' QUIT
# Ignore SIGPIPE — benign when downstream closes stdin (e.g. `... | head`).
trap '' PIPE 2>/dev/null || true

# Colors — suppressed when neither stdout/stderr is a TTY, or NO_COLOR is set (https://no-color.org/).
# Single source of truth for all print_* / TUI plain-text helpers.
if { [ ! -t 1 ] && [ ! -t 2 ]; } || [ -n "${NO_COLOR:-}" ]; then
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    BOLD=''
    NC=''
else
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
fi

# Default values
# Hardcoded default version (immutable reference)
DEFAULT_BUNKERWEB_VERSION="1.6.11"
# Mutable effective version (can be overridden by --version)
BUNKERWEB_VERSION="$DEFAULT_BUNKERWEB_VERSION"
NGINX_VERSION=""
ENABLE_WIZARD=""
FORCE_INSTALL="no"
FORCE_TYPE_CHANGE="no"
DRY_RUN="no"
QUIET_MODE="no"
INTERACTIVE_MODE="yes"
CROWDSEC_INSTALL="no"
CROWDSEC_APPSEC_INSTALL="no"
CROWDSEC_API_KEY=""
REDIS_INSTALL="no"
REDIS_HOST_INPUT=""
REDIS_PORT_INPUT=""
REDIS_DATABASE_INPUT=""
REDIS_USERNAME_INPUT=""
REDIS_PASSWORD_INPUT=""
REDIS_SSL_INPUT=""
REDIS_SSL_VERIFY_INPUT=""
REDIS_BIND_INPUT=""
REDIS_AUTOPASS="yes"
REDIS_REQUIREPASS_LOCAL=""
REDIS_PASSWORD_GENERATED=""   # set to the value only when auto-generated (controls end-of-install print)
REDIS_FLAVOR=""               # "redis" | "valkey" — wire-compatible
REDIS_MAXMEMORY_MB=""         # 0 = unlimited; >0 = applied as <N>mb
REDIS_MAXMEMORY_POLICY="volatile-lru" # TTL-only eviction: protects permanent bans, evicts transient counters first
DB_INSTALL=""
DB_NAME_INPUT="bw_db"
DB_USER_INPUT="bunkerweb"
DB_PASSWORD_INPUT=""
DB_PASSWORD_GENERATED=""
DB_DSN_GENERATED=""
# External existing-DB inputs (DB_INSTALL=external). Engine: mariadb|mysql|postgresql.
DB_EXTERNAL_ENGINE=""
DB_HOST_INPUT=""
DB_PORT_INPUT=""
DB_SSL_INPUT=""
DB_SSL_VERIFY_INPUT=""
# yes = skip connectivity probe (DB only reachable from scheduler, not installer host).
DB_SKIP_PROBE="no"
UI_ADMIN_USERNAME_INPUT=""
UI_ADMIN_PASSWORD_INPUT=""
UI_ADMIN_PASSWORD_GENERATED=""
UI_ADMIN_CREATE=""
UI_SELFSIGNED_INPUT=""
MANAGER_UI_DEFERRED=""
FULL_API_DEFERRED=""
INSTALL_TYPE=""
BUNKERWEB_INSTANCES_INPUT=""
MANAGER_IP_INPUT=""
SERVER_IP_INPUT=""
RESOLVED_SERVER_IP=""
DNS_RESOLVERS_INPUT=""
API_LISTEN_HTTPS_INPUT=""
UPGRADE_SCENARIO="no"
BACKUP_DIRECTORY=""
AUTO_BACKUP="yes"
SYSTEM_ARCH=""
INSTALL_EPEL="auto"
# TUI mode: auto (gum→whiptail→read) | yes (hard error if none) | no (read only).
USE_TUI="${BW_INSTALL_TUI:-auto}"

# ---------------------------------------------------------------------------
# Docker deployment platform — when DOCKER_MODE=yes the installer generates a
# docker-compose stack (inspired by docs/quickstart-guide.md and docs/advanced.md)
# in the current working directory and brings it up, instead of installing host
# packages. INSTALL_TYPE keeps its six normal values (full/manager/worker/
# scheduler/ui/api) for BOTH platforms. Docker mode never touches the
# save-state/resume machinery (only the package phases checkpoint), so none of
# these need to be in _BW_STATE_VARS.
# ---------------------------------------------------------------------------
DOCKER_MODE="no"                   # "yes" when the docker-compose deployment path is selected
DOCKER_AUTOCONF=""                 # "yes" | "no" — autoconf integration variant (full only)
DOCKER_IMAGE_TAG=""                # explicit Docker Hub tag; empty = derive from BUNKERWEB_VERSION
DOCKER_PROJECT_DIR=""              # dir that receives docker-compose.yml + .env
DOCKER_COMPOSE_FILE=""             # $DOCKER_PROJECT_DIR/docker-compose.yml
DOCKER_ENV_FILE=""                 # $DOCKER_PROJECT_DIR/.env
DOCKER_OVERWRITE_EXISTING="no"     # --overwrite-compose: back up + overwrite existing files
DOCKER_AUTO_INSTALL=""             # "yes" (--install-docker): install Docker if missing, no prompt
DOCKER_NEED_INSTALL="no"           # "yes" when check_docker_prereqs deferred a Docker install to after the confirm
DOCKER_PULL="yes"                  # --no-pull sets this to "no"
DOCKER_WAIT_TIMEOUT=180            # seconds to wait for the stack to become ready
DOCKER_DB_PASSWORD_GENERATED=""    # MariaDB bunkerweb-user password (operator-set or generated)
DOCKER_TOTP_KEY_GENERATED=""       # TOTP_ENCRYPTION_KEYS value
DOCKER_API_TOKEN_GENERATED=""      # API_TOKEN value (generated for full/ui/api, prompted for manager/worker/scheduler)
DOCKER_FLASK_SECRET_GENERATED=""   # UI FLASK_SECRET value
DOCKER_DATABASE_URI=""             # external DATABASE_URI for scheduler/ui/api docker types
API_USERNAME_INPUT=""              # FastAPI admin username (api docker type)
API_PASSWORD_INPUT=""              # FastAPI admin password (api docker type)
# Host ports published by the generated stack. Defaults match a standalone
# deploy; override (--http-port etc.) so several stacks can co-exist on one
# host (e.g. a manager plus several workers in one test VM, one folder each).
DOCKER_HTTP_PORT="80"              # bunkerweb HTTP      (container 8080)
DOCKER_HTTPS_PORT="443"            # bunkerweb HTTPS+QUIC (container 8443 tcp+udp)
DOCKER_API_PORT="5000"             # worker internal API (container 5000)
DOCKER_UI_PORT="7000"              # manager/ui Web UI   (container 7000)
DOCKER_FASTAPI_PORT="8888"         # api FastAPI service (container 8888)

# ---------------------------------------------------------------------------
# Save-state / resume — checkpoints the fresh-install flow so a crash or Ctrl+C
# can be resumed from the last completed phase instead of restarting from
# scratch. Fresh-install path only; upgrade_only() is short and not checkpointed.
# ---------------------------------------------------------------------------
# State lives in a 0700 root-owned directory, not a bare /var/tmp file: a
# directory an unprivileged user cannot enter closes the entire symlink/TOCTOU
# attack class for every file created inside it. /var/tmp is used (not /run) so
# the state survives a reboot mid-install.
_BW_STATE_DIR="/var/tmp/bunkerweb-install.d"
_BW_STATE_FILE="${_BW_STATE_DIR}/state"
# Not readonly: the state file carries an `_BW_STATE_SCHEMA=` line, so a resume
# `source` re-assigns it — a readonly here would abort the installer.
_BW_STATE_SCHEMA=1
# A state file older than this is treated as a dead install and discarded
# rather than offered for resume (its generated secrets would be stale).
_BW_STATE_MAX_AGE_DAYS=7
RESTART_INSTALL="no"        # --restart-install: discard any saved state, no prompt
_BW_RESUMING="no"
_BW_RESUME_AFTER=""         # last completed phase when resuming
_BW_START_OVER="no"         # explicit "start over": fresh install over an interrupted one
LAST_COMPLETED_PHASE=""     # persisted: "preferences" then each _BW_PHASES entry
# Ordered install phases (the gate phase "preferences" is handled separately).
_BW_PHASES=(nginx crowdsec redis database host_config package configure)
# Installer config globals persisted to the state file so a resumed run does
# not re-prompt. NOTE for maintainers: any new install-affecting global that
# ask_user_preferences/CLI flags can set MUST be added here, or resume will
# silently lose it.
_BW_STATE_VARS=(
    INSTALL_TYPE BUNKERWEB_VERSION NGINX_VERSION ENABLE_WIZARD
    FORCE_INSTALL FORCE_TYPE_CHANGE QUIET_MODE INTERACTIVE_MODE
    CROWDSEC_INSTALL CROWDSEC_APPSEC_INSTALL CROWDSEC_API_KEY
    REDIS_INSTALL REDIS_HOST_INPUT REDIS_PORT_INPUT REDIS_DATABASE_INPUT
    REDIS_USERNAME_INPUT REDIS_PASSWORD_INPUT REDIS_SSL_INPUT
    REDIS_SSL_VERIFY_INPUT REDIS_BIND_INPUT REDIS_AUTOPASS
    REDIS_REQUIREPASS_LOCAL REDIS_PASSWORD_GENERATED REDIS_FLAVOR
    REDIS_MAXMEMORY_MB REDIS_MAXMEMORY_POLICY DB_INSTALL DB_NAME_INPUT
    DB_USER_INPUT DB_PASSWORD_INPUT DB_PASSWORD_GENERATED DB_DSN_GENERATED
    DB_EXTERNAL_ENGINE DB_HOST_INPUT DB_PORT_INPUT DB_SSL_INPUT
    DB_SSL_VERIFY_INPUT DB_SKIP_PROBE UI_ADMIN_USERNAME_INPUT
    UI_ADMIN_PASSWORD_INPUT UI_ADMIN_PASSWORD_GENERATED UI_ADMIN_CREATE
    UI_SELFSIGNED_INPUT MANAGER_UI_DEFERRED FULL_API_DEFERRED
    BUNKERWEB_INSTANCES_INPUT MANAGER_IP_INPUT SERVER_IP_INPUT
    RESOLVED_SERVER_IP DNS_RESOLVERS_INPUT API_LISTEN_HTTPS_INPUT
    BACKUP_DIRECTORY AUTO_BACKUP INSTALL_EPEL SERVICE_API SERVICE_UI
)

# Safe defaults so callers can reference glyphs before tui_init() runs.
TUI_CURSOR_GLYPH="❯"
TUI_SECTION_GLYPH="▸"
# Set by tui_init().
GUM_AVAILABLE="no"
WHIPTAIL_AVAILABLE="no"
TUI_BACKTITLE="BunkerWeb — Powerful Protection, Simplified."
# ---------------------------------------------------------------------------
# gum bootstrap — pinned for supply-chain safety. When bumping GUM_VERSION:
#   1. fetch https://github.com/charmbracelet/gum/releases/download/v$VER/checksums.txt
#   2. update each Linux_/Freebsd_ SHA256 below
# ---------------------------------------------------------------------------
readonly GUM_VERSION="0.17.0"
readonly GUM_GH_RELEASE="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}"
# Pinned against Charm's `checksums.txt`. cosign-verified at runtime when available; pins are the local trust anchor.
readonly GUM_SHA256_LINUX_X86_64="69ee169bd6387331928864e94d47ed01ef649fbfe875baed1bbf27b5377a6fdb"
readonly GUM_SHA256_LINUX_ARM64="b0b9ed95cbf7c8b7073f17b9591811f5c001e33c7cfd066ca83ce8a07c576f9c"
readonly GUM_SHA256_FREEBSD_X86_64="9b155543613a3293558ad01f21b9593d38401613a7398bd14fc115810859f39c"
readonly GUM_SHA256_FREEBSD_ARM64="722c2933c7f91a947463c4d3601f00957ca5313963248ffc133632996bd1e65d"

# Colored output. Under --quiet, status/step go to /dev/null but warning/error
# still surface via saved stderr fd ($_BW_ERR_FD=4) — operator must see fatals.
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    if [ "${QUIET_MODE:-no}" = "yes" ] && [ -n "${_BW_ERR_FD:-}" ]; then
        echo -e "${YELLOW}[WARNING]${NC} $1" >&"$_BW_ERR_FD"
    else
        echo -e "${YELLOW}[WARNING]${NC} $1" >&2
    fi
}

print_error() {
    if [ "${QUIET_MODE:-no}" = "yes" ] && [ -n "${_BW_ERR_FD:-}" ]; then
        echo -e "${RED}[ERROR]${NC} $1" >&"$_BW_ERR_FD"
    else
        echo -e "${RED}[ERROR]${NC} $1" >&2
    fi
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

run_cmd() {
    echo -e "${BLUE}[CMD]${NC} $*"
    if ! "$@"; then
        print_error "Command failed: $*"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Save-state / resume helpers — see the globals block above.
# ---------------------------------------------------------------------------

# stat(1) wrappers — GNU first, BSD fallback. Echo "" when the path is gone.
_bw_stat_owner() {
    stat -c '%u' "$1" 2>/dev/null || stat -f '%u' "$1" 2>/dev/null || echo ""
}
_bw_stat_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || echo ""
}

# Ensure the state directory exists as a directory owned by the current (root)
# user with mode 0700. A 0700 dir an unprivileged attacker cannot enter removes
# the symlink/TOCTOU risk for every file inside it. `mkdir` without `-p` fails
# (EEXIST) if the path was pre-seeded — so an attacker-planted symlink or dir is
# rejected, never adopted. Returns 1 when the directory cannot be trusted.
_bw_state_dir_ensure() {
    local _me
    _me=$(id -u 2>/dev/null || echo "")
    if [ -e "$_BW_STATE_DIR" ] || [ -L "$_BW_STATE_DIR" ]; then
        # Must be a real directory (not a symlink), owned by us, mode 0700.
        if [ -L "$_BW_STATE_DIR" ] || [ ! -d "$_BW_STATE_DIR" ] \
            || [ "$(_bw_stat_owner "$_BW_STATE_DIR")" != "$_me" ] \
            || [ "$(_bw_stat_mode "$_BW_STATE_DIR")" != "700" ]; then
            return 1
        fi
        return 0
    fi
    mkdir -m 0700 "$_BW_STATE_DIR" 2>/dev/null || return 1
    # mkdir's mode can be weakened by a restrictive umask on some shells.
    chmod 0700 "$_BW_STATE_DIR" 2>/dev/null || true
    return 0
}

# Atomically (re)write the state file with the current phase + config snapshot.
# 0600, inside the 0700 state dir. Non-fatal on failure — a read-only /var/tmp
# must not abort an otherwise-fine install. No-op under --dry-run.
_bw_state_save() {
    [ "${DRY_RUN:-no}" = "yes" ] && return 0
    if ! _bw_state_dir_ensure; then
        print_warning "Could not create a secure state directory ($_BW_STATE_DIR); resume will be unavailable."
        return 0
    fi
    local _tmp _v
    # mktemp inside the 0700 dir → unpredictable name, O_EXCL create, no race.
    _tmp=$(mktemp "${_BW_STATE_DIR}/state.XXXXXX" 2>/dev/null) || {
        print_warning "Could not write install state file; resume will be unavailable."
        return 0
    }
    {
        printf '_BW_STATE_SCHEMA=%s\n' "$_BW_STATE_SCHEMA"
        printf 'LAST_COMPLETED_PHASE=%q\n' "${LAST_COMPLETED_PHASE:-}"
        for _v in "${_BW_STATE_VARS[@]}"; do
            printf '%s=%q\n' "$_v" "${!_v-}"
        done
    } >> "$_tmp" 2>/dev/null || {
        print_warning "Could not write install state file; resume will be unavailable."
        rm -f "$_tmp" 2>/dev/null || true
        return 0
    }
    chmod 0600 "$_tmp" 2>/dev/null || true
    mv -f "$_tmp" "$_BW_STATE_FILE" 2>/dev/null || {
        print_warning "Could not finalize install state file; resume will be unavailable."
        rm -f "$_tmp" 2>/dev/null || true
        return 0
    }
}

# Mark a phase complete and persist the snapshot.
_bw_phase_done() {
    LAST_COMPLETED_PHASE="$1"
    _bw_state_save
}

# 1-based index of a phase in _BW_PHASES; "preferences" -> 0; unknown -> -1.
_bw_phase_index() {
    local _p="$1" _i
    [ "$_p" = "preferences" ] && { echo 0; return 0; }
    for _i in "${!_BW_PHASES[@]}"; do
        if [ "${_BW_PHASES[$_i]}" = "$_p" ]; then
            echo $(( _i + 1 ))
            return 0
        fi
    done
    echo -1
}

# Return 0 (run the phase) on a fresh install, or when resuming and the phase
# sits AFTER the last completed phase. Return 1 (skip) otherwise.
_bw_phase_pending() {
    local _p="$1" _want _done
    if [ "$_BW_RESUMING" != "yes" ]; then
        return 0
    fi
    _want=$(_bw_phase_index "$_p")
    _done=$(_bw_phase_index "$_BW_RESUME_AFTER")
    if [ "$_want" -gt "$_done" ]; then
        return 0
    fi
    print_status "Skipping ${_p} phase (already completed in the interrupted run)."
    return 1
}

# Securely remove the state file and its directory. Idempotent. Called on
# success or discard — NOT from the EXIT trap (the file must survive a crash so
# resume can work).
_bw_state_clear() {
    if [ -e "$_BW_STATE_FILE" ]; then
        shred -u "$_BW_STATE_FILE" 2>/dev/null || rm -f "$_BW_STATE_FILE" 2>/dev/null || true
    fi
    # rmdir only succeeds when empty — leaves the dir if a concurrent tempfile exists.
    rmdir "$_BW_STATE_DIR" 2>/dev/null || true
}

# Detect a state file left by an interrupted run and decide what to do with it.
# Sets _BW_RESUMING / _BW_RESUME_AFTER / _BW_START_OVER. Must run before
# check_existing_installation (which would otherwise early-exit "already
# installed" once the package phase had landed).
_bw_state_load_and_prompt() {
    [ -f "$_BW_STATE_FILE" ] || return 0

    # The state dir must itself be a trusted 0700 root-owned directory before we
    # trust anything inside it.
    if ! _bw_state_dir_ensure; then
        print_warning "Ignoring saved install state — $_BW_STATE_DIR is not a secure root-owned 0700 directory."
        return 0
    fi

    # --restart-install: discard the saved state and re-install over the
    # interrupted leftovers (a state file only ever exists mid fresh-install).
    if [ "$RESTART_INSTALL" = "yes" ]; then
        print_status "Discarding saved install state (--restart-install)."
        _bw_state_clear
        _BW_START_OVER="yes"
        return 0
    fi

    # Safety gate before sourcing: a regular file (not a symlink), owned by the
    # current root user, mode 0600.
    if [ -L "$_BW_STATE_FILE" ]; then
        print_warning "Ignoring saved install state at $_BW_STATE_FILE (unexpected symlink)."
        _bw_state_clear
        return 0
    fi
    local _me
    _me=$(id -u 2>/dev/null || echo "")
    if [ "$(_bw_stat_owner "$_BW_STATE_FILE")" != "$_me" ] \
        || [ "$(_bw_stat_mode "$_BW_STATE_FILE")" != "600" ]; then
        print_warning "Ignoring saved install state at $_BW_STATE_FILE (unexpected owner/permissions)."
        _bw_state_clear
        return 0
    fi

    # Staleness: a state file older than _BW_STATE_MAX_AGE_DAYS describes a dead
    # install — do not offer to resume it (its generated secrets are stale).
    if [ -n "$(find "$_BW_STATE_FILE" -maxdepth 0 -mtime "+${_BW_STATE_MAX_AGE_DAYS}" 2>/dev/null)" ]; then
        print_warning "Saved install state is older than ${_BW_STATE_MAX_AGE_DAYS} days — discarding as stale."
        _bw_state_clear
        return 0
    fi

    # Schema check before sourcing — refuse a file from an incompatible script.
    local _schema
    _schema=$(grep -E '^_BW_STATE_SCHEMA=' "$_BW_STATE_FILE" 2>/dev/null | head -1 | cut -d= -f2)
    if [ "$_schema" != "$_BW_STATE_SCHEMA" ]; then
        print_warning "Saved install state has an incompatible schema — discarding."
        _bw_state_clear
        return 0
    fi

    local _choice="resume"
    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        tui_section "🔄 Resume Previous Installation" \
            "A previous BunkerWeb installation was interrupted and can be resumed."
        _choice=$(tui_menu "Resume Installation" \
            "An interrupted BunkerWeb installation was found. What would you like to do?" \
            "resume" \
            "resume" "Resume — continue from where it stopped" \
            "fresh"  "Start over — discard saved state and install from the beginning" \
            "cancel" "Cancel — exit without changing anything") || _choice="cancel"
    else
        print_status "Interrupted installation detected — resuming (pass --restart-install to start over)."
    fi

    case "$_choice" in
        cancel)
            print_status "Installation cancelled. Saved state kept at $_BW_STATE_FILE."
            exit 0
            ;;
        fresh)
            print_status "Discarding saved install state — starting from the beginning."
            _bw_state_clear
            _BW_START_OVER="yes"
            ;;
        resume|*)
            # Root-owned 0600 file written by this script; symlink/owner/mode/schema
            # already validated above.
            # shellcheck disable=SC1090
            . "$_BW_STATE_FILE"
            _BW_RESUMING="yes"
            _BW_RESUME_AFTER="${LAST_COMPLETED_PHASE:-preferences}"
            ;;
    esac
}

# Dump systemd status + recent journal for a failed unit so the real cause
# is visible instead of a bare "[ERROR] Command failed".
# NOTE: only call on units whose secrets live in a config file, not on argv —
# `systemctl status` echoes ExecStart, so a `--requirepass <value>` style unit
# would leak the password to the terminal.
_dump_service_diagnostics() {
    local unit="$1"
    echo
    echo -e "${YELLOW}--- systemctl status ${unit} ---${NC}"
    systemctl status "$unit" --no-pager -l 2>&1 | tail -n 20 || true
    echo -e "${YELLOW}--- journalctl -xeu ${unit} (last 30 lines) ---${NC}"
    journalctl -xeu "$unit" --no-pager -n 30 2>&1 || true
    echo
}

# Enable + start an OPTIONAL systemd unit. Unlike run_cmd this never exits the
# installer: a failed optional daemon (e.g. local Valkey/Redis) must not abort
# the whole BunkerWeb install. Returns non-zero on failure; caller decides.
# Caller is responsible for any prior `systemctl daemon-reload`.
start_optional_service() {
    local unit="$1"
    local label="${2:-$unit}"
    echo -e "${BLUE}[CMD]${NC} systemctl enable --now $unit"
    if systemctl enable --now "$unit"; then
        return 0
    fi
    print_warning "${label} service (${unit}) failed to start."
    _dump_service_diagnostics "$unit"
    return 1
}

# ---------------------------------------------------------------------------
# TUI helper layer — all prompts dispatch gum → whiptail → plain-read.
# tui_init() picks the order once per run.
# ---------------------------------------------------------------------------

# ASCII fallback for non-UTF-8 terminals (e.g. default PuTTY).
_tui_pick_glyphs() {
    local _charmap
    _charmap=$(locale charmap 2>/dev/null || true)
    case "$_charmap" in
        UTF-8|utf-8|UTF8|utf8) ;;   # keep Unicode glyphs (already set above)
        *) TUI_CURSOR_GLYPH=">"; TUI_SECTION_GLYPH=">" ;;
    esac
}

# Map uname to Charm's release-artifact segment (e.g. `Linux_x86_64`).
_detect_gum_arch() {
    local _os _machine
    _os=$(uname -s 2>/dev/null)
    _machine=$(uname -m 2>/dev/null)
    case "$_os/$_machine" in
        Linux/x86_64|Linux/amd64)      echo "Linux_x86_64"   ;;
        Linux/aarch64|Linux/arm64)     echo "Linux_arm64"    ;;
        FreeBSD/x86_64|FreeBSD/amd64)  echo "Freebsd_x86_64" ;;
        FreeBSD/aarch64|FreeBSD/arm64) echo "Freebsd_arm64"  ;;
        *) return 1 ;;
    esac
}

# Ephemeral gum tempdir — wiped at EXIT.
_GUM_EPHEMERAL_DIR=""

# Idempotent EXIT cleanup for ephemeral gum.
_gum_cleanup() {
    if [ -n "${_GUM_EPHEMERAL_DIR:-}" ] && [ -d "$_GUM_EPHEMERAL_DIR" ]; then
        rm -rf "$_GUM_EPHEMERAL_DIR"
        _GUM_EPHEMERAL_DIR=""
    fi
}

# Install gum ephemerally: download → SHA256 + optional cosign → extract → PATH.
# Tempdir wiped at EXIT — no system traces left. Returns 1 on failure (tui_init falls through to whiptail).
install_gum_silent() {
    local _arch _tarball _hash_pin
    if ! _arch=$(_detect_gum_arch); then
        print_warning "Unsupported architecture for gum tarball"
        return 1
    fi
    _tarball="gum_${GUM_VERSION}_${_arch}.tar.gz"
    case "$_arch" in
        Linux_x86_64)   _hash_pin="$GUM_SHA256_LINUX_X86_64"   ;;
        Linux_arm64)    _hash_pin="$GUM_SHA256_LINUX_ARM64"    ;;
        Freebsd_x86_64) _hash_pin="$GUM_SHA256_FREEBSD_X86_64" ;;
        Freebsd_arm64)  _hash_pin="$GUM_SHA256_FREEBSD_ARM64"  ;;
        *) return 1 ;;
    esac

    # Find an exec-capable tempdir. `/tmp` is mounted `noexec` on some
    # hardened systems (Docker hardened images, CIS-aligned servers), in
    # which case the gum binary would chmod fine but `exec` would fail.
    # Try a few standard candidates and verify with a probe.
    local _tmp _cand _probe
    for _cand in /var/tmp /tmp "${XDG_RUNTIME_DIR:-}" "${HOME:-/root}/.cache"; do
        [ -d "$_cand" ] || continue
        _tmp=$(mktemp -d -p "$_cand" bw-gum.XXXXXX 2>/dev/null) || continue
        _probe="$_tmp/.exec-probe"
        printf '#!/bin/sh\nexit 0\n' > "$_probe" 2>/dev/null \
            && chmod +x "$_probe" 2>/dev/null \
            && "$_probe" 2>/dev/null \
            && { rm -f "$_probe"; break; }
        rm -rf "$_tmp"
        _tmp=""
    done
    if [ -z "$_tmp" ] || [ ! -d "$_tmp" ]; then
        print_warning "No exec-capable tempdir found for gum bootstrap"
        return 1
    fi
    # RETURN trap nukes tempdir on any early-return before hand-off to EXIT trap.
    # shellcheck disable=SC2064
    trap "rm -rf '$_tmp'; trap - RETURN" RETURN

    print_status "Fetching gum ${GUM_VERSION} (${_arch}) from GitHub releases..."
    if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
              --connect-timeout 10 --max-time 30 -L \
              -o "$_tmp/$_tarball" "$GUM_GH_RELEASE/$_tarball"; then
        print_warning "gum tarball download failed"
        return 1
    fi

    # Two independent verification layers, both MUST pass when present:
    #   1. Pinned SHA256 (local trust anchor — attacker must compromise both upstream artifact AND this script).
    #   2. cosign verify-blob of upstream `checksums.txt` (defense-in-depth; degrades to layer 1 only if cosign absent).
    local _got
    _got=$(sha256sum "$_tmp/$_tarball" | awk '{print $1}')
    if [ "$_got" != "$_hash_pin" ]; then
        print_error "SHA256 mismatch on $_tarball"
        print_error "  got:    $_got"
        print_error "  expect: $_hash_pin"
        return 1
    fi

    if command -v cosign >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 --fail --silent --show-error --connect-timeout 10 --max-time 30 -L \
             -o "$_tmp/checksums.txt"     "$GUM_GH_RELEASE/checksums.txt"     || return 1
        curl --proto '=https' --tlsv1.2 --fail --silent --show-error --connect-timeout 10 --max-time 30 -L \
             -o "$_tmp/checksums.txt.sig" "$GUM_GH_RELEASE/checksums.txt.sig" || return 1
        curl --proto '=https' --tlsv1.2 --fail --silent --show-error --connect-timeout 10 --max-time 30 -L \
             -o "$_tmp/checksums.txt.pem" "$GUM_GH_RELEASE/checksums.txt.pem" || return 1
        if ! ( cd "$_tmp" && cosign verify-blob \
                  --certificate checksums.txt.pem \
                  --signature checksums.txt.sig \
                  --certificate-identity-regexp '^https://github\.com/charmbracelet/gum/' \
                  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
                  checksums.txt >/dev/null 2>&1 ); then
            print_error "cosign verification of upstream checksums.txt failed"
            return 1
        fi
        # Cross-check: pinned hash must match Charm's cosign-signed checksums.txt (catches desynced pin).
        if ! grep -qE "^${_hash_pin}  ${_tarball}\$" "$_tmp/checksums.txt"; then
            print_error "Pinned SHA256 is not present in cosign-verified checksums.txt for $_tarball"
            print_error "  pinned: $_hash_pin"
            print_error "  upstream values (filtered):"
            grep " ${_tarball}\$" "$_tmp/checksums.txt" | sed 's/^/    /' >&2 || true
            return 1
        fi
    fi

    # Charm tarball nests `gum_${VER}_${arch}/gum` — strip leading dir, restrict to known path.
    if ! tar -xzf "$_tmp/$_tarball" -C "$_tmp" --strip-components=1 \
         "gum_${GUM_VERSION}_${_arch}/gum" 2>/dev/null; then
        # Fallback: full extract + locate, in case Charm changes layout.
        tar -xzf "$_tmp/$_tarball" -C "$_tmp" || return 1
        local _found
        _found=$(find "$_tmp" -maxdepth 3 -name gum -type f 2>/dev/null | head -1)
        if [ -n "$_found" ] && [ "$_found" != "$_tmp/gum" ]; then
            mv "$_found" "$_tmp/gum"
        fi
    fi
    [ -f "$_tmp/gum" ] || { print_warning "gum binary not found in tarball"; return 1; }
    chmod 0755 "$_tmp/gum"

    # Hand tempdir to script-wide EXIT trap; put gum on PATH.
    _GUM_EPHEMERAL_DIR="$_tmp"
    PATH="$_tmp:$PATH"
    export PATH
    trap - RETURN
    return 0
}

# install_newt_silent() removed in 1.6.10~rc6 — installer never installs whiptail.
# Uses pre-existing whiptail when present, otherwise plain-read. Zero-pkgmgr-trace.

# Pick a UTF-8 locale so whiptail/newt render multibyte glyphs (sudo strips LANG).
# Silent give-up on Alpine/busybox where none of the candidates are installed.
_tui_force_utf8_locale() {
    # If we already have a UTF-8 locale, nothing to do.
    case "${LC_ALL:-${LANG:-}}" in
        *.UTF-8|*.utf8|*.UTF8) return 0 ;;
    esac
    local cand have
    have=$(locale -a 2>/dev/null || true)
    for cand in C.UTF-8 C.utf8 en_US.UTF-8 en_US.utf8 en_GB.UTF-8 en_GB.utf8; do
        if printf '%s\n' "$have" | grep -qxiF "$cand"; then
            export LC_ALL="$cand" LANG="$cand"
            return 0
        fi
    done
    return 1
}

# Probe whether the controlling terminal answers control-sequence queries.
# gum (bubbletea) queries the terminal on every prompt — Primary Device
# Attributes / background color — and waits for the reply before drawing.
# Terminals that never answer (some VM consoles, serial links, ssh through
# certain proxies) make each of the installer's ~25 gum prompts stall for the
# query timeout, so the whole TUI feels seconds-slow per screen. whiptail
# issues no such query. Detect the unresponsive case ONCE here (cost: one
# ~1s timeout, only on a terminal that would otherwise stall every prompt)
# so tui_init can skip the gum tier and fall through to whiptail.
# Returns 0 = terminal answered, 1 = no answer / probe unavailable.
_tui_terminal_answers_queries() {
    [ -e /dev/tty ] || return 1
    local _saved _reply="" _da1_end="c"
    _saved=$(stty -g </dev/tty 2>/dev/null) || return 1
    # Raw, no echo — so the DA1 reply lands in `read`, not on screen.
    stty -echo -icanon min 0 time 0 </dev/tty 2>/dev/null || { stty "$_saved" </dev/tty 2>/dev/null; return 1; }
    # ESC[c = Primary Device Attributes request. Any VT100-class terminal
    # answers `ESC[?…c`; bubbletea uses this exact reply as its sync sentinel.
    printf '\033[c' >/dev/tty 2>/dev/null
    IFS= read -r -t 1 -d "$_da1_end" _reply </dev/tty 2>/dev/null
    stty "$_saved" </dev/tty 2>/dev/null
    [ -n "$_reply" ]
}

# Pick TUI mode (gum → whiptail → plain read) and export NEWT_COLORS.
# Must run after detect_os() sets $DISTRO_ID.
tui_init() {
    GUM_AVAILABLE="no"
    WHIPTAIL_AVAILABLE="no"

    # --no-tui or BW_INSTALL_TUI=no — never use any TUI
    if [ "$USE_TUI" = "no" ]; then
        return 0
    fi

    # Non-interactive mode — no prompts, no TUI either
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        return 0
    fi

    # Stdin must be a TTY — otherwise `curl … | bash` silently picks defaults.
    if [ ! -t 0 ]; then
        print_error "No TTY detected on stdin (likely piped install)."
        print_error "Interactive installation cannot proceed."
        print_error "Either re-run from a real terminal, or use:"
        print_error "    $0 --yes [other-flags]"
        print_error "to drive the installer non-interactively from CLI flags/env vars."
        exit 1
    fi

    # TERM=dumb (or unset) — neither gum nor whiptail render well; plain read
    if [ -z "${TERM:-}" ] || [ "$TERM" = "dumb" ]; then
        if [ "$USE_TUI" = "yes" ]; then
            print_error "TERM is '${TERM:-unset}'; no TUI can render. Re-run without --tui."
            exit 1
        fi
        return 0
    fi

    # Tier 1: gum (inline prompts) — PATH or ephemeral GH release fetch.
    # Only on terminals that answer control-sequence queries: gum stalls on
    # every prompt waiting for query replies a silent terminal never sends.
    # Probing first also skips a pointless gum download on such terminals.
    if _tui_terminal_answers_queries; then
        if command -v gum >/dev/null 2>&1; then
            GUM_AVAILABLE="yes"
        elif install_gum_silent; then
            GUM_AVAILABLE="yes"
        fi
    fi

    # Tier 2: whiptail — used only when pre-installed (we don't install it; zero-pkgmgr-trace).
    if command -v whiptail >/dev/null 2>&1; then
        WHIPTAIL_AVAILABLE="yes"
    fi

    if [ "$GUM_AVAILABLE" = "no" ] && [ "$WHIPTAIL_AVAILABLE" = "no" ]; then
        if [ "$USE_TUI" = "yes" ]; then
            print_error "Neither gum nor whiptail could be installed and --tui was requested."
            exit 1
        fi
        print_warning "No TUI available; falling back to plain text prompts."
        return 0
    fi

    # Force UTF-8 — whiptail needs it for multibyte glyphs (sudo strips LANG).
    if ! _tui_force_utf8_locale; then
        # Only warn for whiptail tier; gum degrades to ASCII silently.
        if [ "$GUM_AVAILABLE" = "no" ] && [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
            print_warning "No UTF-8 locale available; whiptail glyphs may render incorrectly."
        fi
    fi
    # Pick cursor / section glyphs after the locale has been (possibly)
    # upgraded so PuTTY-without-Unicode operators still get a legible TUI.
    _tui_pick_glyphs

    # BunkerWeb palette for the whiptail tier — only relevant when gum is
    # unavailable and we fall back to newt. newt only consumes 16 ANSI
    # colors, so brand hexes (#0b354a/#2eac68) map to their closest
    # ANSI equivalents. gum reads hex directly per-call via --foreground etc.
    if [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        export NEWT_COLORS='
root=white,blue
window=white,black
shadow=,black
border=brightblue,black
title=brightcyan,black
button=black,brightgreen
actbutton=white,brightgreen
checkbox=brightblue,black
actcheckbox=black,brightgreen
entry=white,black
disentry=gray,black
label=brightblue,black
listbox=white,black
actlistbox=black,brightgreen
sellistbox=black,brightgreen
actsellistbox=white,brightblue
textbox=white,black
acttextbox=black,brightgreen
helpline=white,blue
roottext=brightblue,white
emptyscale=,black
fullscale=,brightgreen
'
    fi
}

# Normalize a TUI tool's exit code to 0=ok, 1=cancel/no.
# gum exits 130 on Ctrl-C/ESC, whiptail exits 1 on No and 255 on ESC.
# Any other non-zero is treated as cancel + logged as unexpected.
_tui_normalize_rc() {
    case "$1" in
        0)        return 0 ;;
        1|130|255) return 1 ;;
        *) print_warning "TUI helper unexpected exit code: $1"; return 1 ;;
    esac
}

_tui_expand_newlines() {
    local _value="$1"
    printf '%s' "${_value//\\n/$'\n'}"
}

# Echo a one-line scrollback trace for a TUI answer. Stays on stderr so $(...) captures stay clean.
# Args: $1 = label, $2 = answer (caller redacts secrets).
_tui_log_choice() {
    local label="$1" answer="$2"
    # %b expands the \033 escapes baked into BLUE/etc. Brackets+BOLD reinforce color for color-blind operators.
    printf '   %b▸%b %b%s%b %b%b[%s]%b\n' \
        "${BLUE}" "${NC}" \
        "${YELLOW}" "${label}:" "${NC}" \
        "${BOLD}" "${GREEN}" "${answer}" "${NC}" >&2
}

# Render multi-line explanatory text before a tui_yesno/tui_menu. gum confirm crops on narrow terms,
# so we wrap via `fold -s` (gum style doesn't word-wrap on its own).
_tui_explain() {
    local body
    body=$(_tui_expand_newlines "$1")
    # Skip empty body — would render an empty rounded box under gum.
    [ -n "$body" ] || return 0
    local _term_w _box_w _wrap_w
    _term_w=$(tput cols 2>/dev/null || echo 80)
    # Box capped at 78; 6-col safety margin on narrow terms.
    _box_w=$(( _term_w > 84 ? 78 : _term_w - 6 ))
    [ "$_box_w" -lt 40 ] && _box_w=40
    # Wrap = box - 4 (2 border + 2 pad).
    _wrap_w=$(( _box_w - 4 ))
    [ "$_wrap_w" -lt 36 ] && _wrap_w=36

    local _wrapped
    if command -v fold >/dev/null 2>&1; then
        _wrapped=$(printf '%s' "$body" | fold -s -w "$_wrap_w")
    else
        _wrapped="$body"
    fi

    if [ "$GUM_AVAILABLE" = "yes" ] && command -v gum >/dev/null 2>&1; then
        gum style --margin "0 0 1 0" --padding "0 1" \
            --border rounded --border-foreground "#2eac68" \
            --width "$_box_w" \
            "$_wrapped" >&2
    else
        printf '%s\n' "$_wrapped" >&2
    fi
}

# tui_yesno TITLE PROMPT DEFAULT(yes|no) — 0 Yes, 1 No/Cancel/ESC.
tui_yesno() {
    local title="$1" prompt="$2" default="${3:-yes}"
    prompt=$(_tui_expand_newlines "$prompt")
    local _rc=0 _final
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        local _gum_default
        [ "$default" = "no" ] && _gum_default=false || _gum_default=true
        gum confirm "$prompt" --default="$_gum_default" \
            --prompt.foreground "#2eac68" \
            --affirmative "Yes" --negative "No" || _rc=$?
        _tui_normalize_rc "$_rc"; _rc=$?
    elif [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        local defarg=""
        [ "$default" = "no" ] && defarg="--defaultno"
        whiptail --backtitle "$TUI_BACKTITLE" --title "$title" \
                 $defarg --yesno "$prompt" 12 70 || _rc=$?
        _tui_normalize_rc "$_rc"; _rc=$?
    else
        local hint reply
        if [ "$default" = "no" ]; then hint="[y/N]"; else hint="[Y/n]"; fi
        while true; do
            # Prompt on stderr so $(tui_yesno …) captures nothing.
            echo -e "${YELLOW}${prompt} ${hint}:${NC} " >&2
            IFS= read -r reply
            case "${reply:-}" in
                [Yy]*) _rc=0; break ;;
                [Nn]*) _rc=1; break ;;
                "")    [ "$default" = "no" ] && _rc=1 || _rc=0; break ;;
                *)     echo "Please answer yes (y) or no (n)." >&2 ;;
            esac
        done
    fi
    [ "$_rc" -eq 0 ] && _final="Yes" || _final="No"
    _tui_log_choice "$title" "$_final"
    return "$_rc"
}

# tui_input TITLE PROMPT [DEFAULT] — echoes value on stdout, 1 on Cancel.
tui_input() {
    local title="$1" prompt="$2" default="${3:-}"
    prompt=$(_tui_expand_newlines "$prompt")
    local _rc=0 _value=""
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        # --value pre-fills, --placeholder only when no default.
        local _gum_args=(--header "$prompt"
                         --prompt "${TUI_CURSOR_GLYPH} "
                         --prompt.foreground "#2eac68")
        if [ -n "$default" ]; then
            _gum_args+=(--value "$default")
        else
            _gum_args+=(--placeholder "Type here...")
        fi
        _value=$(gum input "${_gum_args[@]}") || _rc=$?
        if ! _tui_normalize_rc "$_rc"; then
            return 1
        fi
    elif [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        _value=$(whiptail --backtitle "$TUI_BACKTITLE" --title "$title" \
                          --inputbox "$prompt" 12 70 "$default" \
                          3>&1 1>&2 2>&3) || _rc=$?
        if ! _tui_normalize_rc "$_rc"; then
            return 1
        fi
    else
        local reply
        if [ -n "$default" ]; then
            echo -e "${YELLOW}${prompt} [${default}]:${NC} " >&2
        else
            echo -e "${YELLOW}${prompt}:${NC} " >&2
        fi
        IFS= read -r reply
        _value=${reply:-$default}
    fi
    _tui_log_choice "$title" "${_value:-<empty>}"
    printf '%s' "$_value"
    return 0
}

# tui_password TITLE PROMPT — echoes password on stdout, 1 on Cancel.
# Security:
#   - gum/whiptail args appear in `ps` — NEVER pass a default password positionally.
#   - Keystrokes fully hidden (bullets on gum 0.17, masked on whiptail). No insecure-display flag.
#   - xtrace disabled inline + restored on every return path. NO `trap … RETURN`:
#     bash 4's RETURN trap fires on every nested return (incl. _tui_normalize_rc),
#     re-enabling xtrace BEFORE `printf '%s' "$_result"` would leak the password.
#   - Caller hygiene: a parent shell with `set -x` still traces `var=$(tui_password …)`.
#     For full secrecy under xtrace, wrap the call site itself in `set +x`/`set -x`.
tui_password() {
    local title="$1" prompt="$2"
    prompt=$(_tui_expand_newlines "$prompt")
    local _had_xtrace=0
    case $- in *x*) _had_xtrace=1; set +x ;; esac
    local _result _rc=0
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        # gum --password: bullets only, never echoes, never argv.
        _result=$(gum input --password \
                            --header "$prompt" \
                            --prompt "${TUI_CURSOR_GLYPH} " \
                            --prompt.foreground "#2eac68") || _rc=$?
    elif [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        _result=$(whiptail --backtitle "$TUI_BACKTITLE" --title "$title" \
                           --passwordbox "$prompt" 12 70 3>&1 1>&2 2>&3) || _rc=$?
    else
        local reply
        echo -e "${YELLOW}${prompt}:${NC} " >&2
        IFS= read -r -s reply
        echo >&2
        _result=$reply
        _rc=0
    fi
    # Inline cancel check (no function call — keeps xtrace disabled across rc eval).
    case "$_rc" in
        0)        : ;;
        1|130|255)
            _result=""
            _tui_log_choice "$title" "<cancelled>"
            [ "$_had_xtrace" -eq 1 ] && set -x
            return 1
            ;;
        *) print_warning "TUI helper unexpected exit code: $_rc"
           _result=""
           [ "$_had_xtrace" -eq 1 ] && set -x
           return 1 ;;
    esac
    # NEVER echo the password — fixed-length mask only.
    if [ -z "$_result" ]; then
        _tui_log_choice "$title" "<empty — auto-generate>"
    else
        _tui_log_choice "$title" "******** (${#_result} chars)"
    fi
    printf '%s' "$_result"
    [ "$_had_xtrace" -eq 1 ] && set -x
    return 0
}

# tui_menu TITLE PROMPT DEFAULT_TAG TAG1 DESC1 [TAG2 DESC2 ...] — echoes tag, 1 on Cancel.
# Fallback: numbered list on stderr (kept out of $(...) captures).
tui_menu() {
    local title="$1" prompt="$2" default_tag="$3"
    prompt=$(_tui_expand_newlines "$prompt")
    shift 3
    # Items come in (tag, desc) pairs — odd count = dropped description (whiptail would silently mis-render).
    if [ $(( $# % 2 )) -ne 0 ]; then
        print_error "tui_menu: odd argument count ($#) — every tag needs a description."
        return 2
    fi
    local i=1 tag desc default_idx=1 default_label="" tags=() descs=()
    while [ $# -ge 2 ]; do
        tag="$1"; desc="$2"; shift 2
        tags+=("$tag"); descs+=("$desc")
        if [ "$tag" = "$default_tag" ]; then
            default_idx=$i
            default_label="$desc"
        fi
        i=$((i + 1))
    done

    if [ "$GUM_AVAILABLE" = "yes" ]; then
        # gum choose returns the label — map back to tag.
        # --selected only when default_label matches an item (gum 0.17 warns on empty match).
        local _gum_args=(
            --header        "$prompt"
            --cursor        "${TUI_CURSOR_GLYPH} "
            --cursor.foreground "#2eac68"
        )
        if [ -n "$default_label" ]; then
            _gum_args+=(--selected "$default_label")
        fi
        local _gum_out _rc=0
        _gum_out=$(gum choose "${_gum_args[@]}" "${descs[@]}") || _rc=$?
        if ! _tui_normalize_rc "$_rc"; then
            return 1
        fi
        local _idx
        for ((_idx=0; _idx<${#descs[@]}; _idx++)); do
            if [ "${descs[$_idx]}" = "$_gum_out" ]; then
                _tui_log_choice "$title" "$_gum_out"
                printf '%s' "${tags[$_idx]}"
                return 0
            fi
        done
        # Hard error on lookup miss — callers must distinguish "picked default" from "gum returned garbage".
        print_warning "tui_menu: gum returned an unrecognised label: $_gum_out"
        return 1
    fi

    if [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        local item_count=${#tags[@]}
        # Rebuild flat (tag desc tag desc ...) array for whiptail
        local _wt_args=() _i
        for ((_i=0; _i<item_count; _i++)); do
            _wt_args+=("${tags[$_i]}" "${descs[$_i]}")
        done
        local _wt_out _rc=0
        _wt_out=$(whiptail --backtitle "$TUI_BACKTITLE" --title "$title" \
                           --default-item "$default_tag" \
                           --menu "$prompt" $((10 + item_count)) 78 "$item_count" \
                           "${_wt_args[@]}" 3>&1 1>&2 2>&3) || _rc=$?
        if ! _tui_normalize_rc "$_rc"; then
            return 1
        fi
        # Tag → desc lookup for scrollback log.
        local _wt_idx _wt_label="$_wt_out"
        for ((_wt_idx=0; _wt_idx<${#tags[@]}; _wt_idx++)); do
            if [ "${tags[$_wt_idx]}" = "$_wt_out" ]; then
                _wt_label="${descs[$_wt_idx]}"
                break
            fi
        done
        _tui_log_choice "$title" "$_wt_label"
        printf '%s' "$_wt_out"
        return 0
    fi
    {
        echo -e "${YELLOW}${prompt}${NC}"
        for ((i=0; i<${#tags[@]}; i++)); do
            printf "  %d) %s\n" "$((i + 1))" "${descs[$i]}"
        done
    } >&2
    local reply
    while true; do
        echo -e "${YELLOW}Select option [${default_idx}]:${NC} " >&2
        IFS= read -r reply
        reply="${reply:-$default_idx}"
        if [[ "$reply" =~ ^[0-9]+$ ]] && [ "$reply" -ge 1 ] && [ "$reply" -le "${#tags[@]}" ]; then
            _tui_log_choice "$title" "${descs[$((reply - 1))]}"
            printf '%s' "${tags[$((reply - 1))]}"
            return 0
        fi
        echo "Invalid option. Please choose a number between 1 and ${#tags[@]}." >&2
    done
}

# tui_msgbox TITLE TEXT [HEIGHT] — blocking ack dialog. Auto-sized height (clamped to term), --scrolltext.
# Fallback: prints + waits for Enter, all output on stderr ($(...) safe).
tui_msgbox() {
    local title="$1" text="$2" height="${3:-}"
    text=$(_tui_expand_newlines "$text")
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        # Rounded box + 1-keystroke wait. Body inherits terminal default — navy collapses on dark themes.
        local _term_w _box_w
        _term_w=$(tput cols 2>/dev/null || echo 80)
        _box_w=$(( _term_w > 84 ? 78 : _term_w - 6 ))
        [ "$_box_w" -lt 40 ] && _box_w=40
        local _bordered_title
        _bordered_title=$(gum style --bold --foreground "#2eac68" "$title")
        gum style \
            --border rounded --padding "0 1" \
            --border-foreground "#2eac68" \
            --width "$_box_w" \
            "$(printf '%s\n\n%s' "$_bordered_title" "$text")"
        gum input --placeholder "Press Enter to continue" \
                  --prompt "" >/dev/null 2>&1 || true
        return 0
    fi
    if [ -z "$height" ]; then
        local _lines _term_h _max_h
        _lines=$(printf '%s' "$text" | awk 'END {print NR}')
        _term_h=$(tput lines 2>/dev/null || echo 24)
        _max_h=$(( _term_h - 2 ))
        [ "$_max_h" -lt 10 ] && _max_h=10
        height=$(( _lines + 7 ))
        [ "$height" -lt 8 ]         && height=8
        [ "$height" -gt "$_max_h" ] && height="$_max_h"
    fi
    if [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        whiptail --backtitle "$TUI_BACKTITLE" --title "$title" \
                 --scrolltext --msgbox "$text" "$height" 78
        return 0
    fi
    print_warning "$title" >&2
    echo "$text" >&2
    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        echo -e "${YELLOW}Press Enter to continue...${NC}" >&2
        IFS= read -r _
    fi
}

# tui_section TITLE [SUBTITLE] — gum: bold green marker; whiptail: no-op; fallback: "===" banner.
# Subtitle pre-wrapped (gum style doesn't word-wrap).
tui_section() {
    local title="$1" subtitle="${2:-}"
    subtitle=$(_tui_expand_newlines "$subtitle")
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        printf '\n' >&2
        gum style --bold --foreground "#2eac68" "${TUI_SECTION_GLYPH} $title" >&2
        if [ -n "$subtitle" ]; then
            local _term_w _sub_w _sub
            _term_w=$(tput cols 2>/dev/null || echo 80)
            _sub_w=$(( _term_w - 4 ))
            [ "$_sub_w" -lt 36 ] && _sub_w=36
            if command -v fold >/dev/null 2>&1; then
                _sub=$(printf '%s' "$subtitle" | fold -s -w "$_sub_w")
            else
                _sub="$subtitle"
            fi
            # Body inherits terminal default (avoid navy collapse on dark themes); 2-sp indent for nesting.
            printf '%s\n' "$_sub" | sed 's/^/  /' | gum style --faint >&2
        fi
        return 0
    fi
    [ "$WHIPTAIL_AVAILABLE" = "yes" ] && return 0
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$title${NC}"
    echo -e "${BLUE}========================================${NC}"
    if [ -n "$subtitle" ]; then
        if command -v fold >/dev/null 2>&1; then
            printf '%s\n' "$subtitle" | fold -s -w "$(($(tput cols 2>/dev/null || echo 80) - 4))"
        else
            echo "$subtitle"
        fi
    fi
}

# tui_infobox TITLE TEXT — non-blocking status line.
tui_infobox() {
    local title="$1" text="$2"
    text=$(_tui_expand_newlines "$text")
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        gum style --foreground "#2eac68" "${TUI_SECTION_GLYPH} $title — $text" >&2
        return 0
    fi
    if [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        whiptail --backtitle "$TUI_BACKTITLE" --title "$title" --infobox "$text" 8 70
        return 0
    fi
    print_status "$title — $text"
}
# ---------------------------------------------------------------------------

set_config_kv() {
    local config_file="$1"
    local key="$2"
    local value="$3"

    # Use ENVIRON[] not `awk -v` — `-v` interprets backslash escapes (`\n`, `\\`) and corrupts
    # values with literal backslashes (e.g. Redis password `my\npass`). ENVIRON passes raw bytes.
    if grep -q "^${key}=" "$config_file"; then
        local tmp
        tmp=$(mktemp "${config_file}.XXXXXX") || return 1
        BW_SCKV_VALUE="$value" awk -v key="$key" '
            BEGIN { pat = "^" key "="; value = ENVIRON["BW_SCKV_VALUE"] }
            $0 ~ pat { print key "=" value; replaced=1; next }
            { print }
        ' "$config_file" > "$tmp" || { rm -f "$tmp"; return 1; }
        # Preserve original mode/owner.
        chmod --reference="$config_file" "$tmp" 2>/dev/null || chmod 660 "$tmp" 2>/dev/null || true
        chown --reference="$config_file" "$tmp" 2>/dev/null || chown root:nginx "$tmp" 2>/dev/null || true
        mv -f "$tmp" "$config_file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$config_file"
    fi
}

ensure_config_file() {
    local config_file="$1"

    if [ ! -d /etc/bunkerweb ]; then
        # 755 dir — world-traversable so nginx group can reach the files.
        mkdir -p /etc/bunkerweb
    fi

    # Atomic restrictive creation: `touch` + `chmod 660` leaves a world-readable window under umask 022.
    # umask 027 subshell creates at 0640 from the first syscall; final mode 0660 root:nginx via chmod below.
    if [ ! -f "$config_file" ]; then
        ( umask 027 && : > "$config_file" )
    fi

    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Docker install mode — compose/.env rendering, stack lifecycle, orchestration.
# Reached only when INSTALL_TYPE=docker; see docker_install_flow().
# ---------------------------------------------------------------------------

# Reject values that cannot live safely in the docker-compose .env file:
# a literal '$' would be taken as interpolation, a "'" breaks any quoting we
# might add later, a trailing '\' is a line continuation in some .env parsers,
# a newline splits the KEY=VALUE line. Returns 0 if safe.
validate_docker_env_value() {
    local v="$1"
    case "$v" in
        *'$'*|*"'"*|*\\*) return 1 ;;
        *$'\n'*)          return 1 ;;
    esac
    return 0
}

# Thin wrapper so every compose call targets the same project. --project-directory
# pins where the .env file is read from, ignoring any stray .env / override file
# or COMPOSE_* env var in the operator's current working directory.
_docker_compose() {
    docker compose --project-directory "$DOCKER_PROJECT_DIR" -f "$DOCKER_COMPOSE_FILE" "$@"
}

# Derive a Compose project name from the compose directory's basename, so each
# folder is an isolated stack (its containers, networks and volumes are all
# prefixed with it). This is what lets a manager and several workers co-exist
# on one host — one folder each. Sanitized to the Compose project-name grammar.
_docker_project_name() {
    local b
    b=$(basename "$DOCKER_PROJECT_DIR" 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-')
    b=${b#-}; b=${b%-}
    [ -z "$b" ] && b="bunkerweb"
    case "$b" in [a-z0-9]*) : ;; *) b="bw-${b}" ;; esac
    printf '%s' "$b"
}

# The Web UI credential + secret block, shared by the full/manager/ui .env.
# stdout — called inside render_docker_env's redirected { } block.
_docker_env_admin_block() {
    printf 'ADMIN_USERNAME=%s\n' "$UI_ADMIN_USERNAME_INPUT"
    printf 'ADMIN_PASSWORD=%s\n' "$UI_ADMIN_PASSWORD_INPUT"
    printf 'FLASK_SECRET=%s\n' "$DOCKER_FLASK_SECRET_GENERATED"
    printf '# TOTP_ENCRYPTION_KEYS encrypts 2FA secrets at rest.\n'
    printf 'TOTP_ENCRYPTION_KEYS=%s\n' "$DOCKER_TOTP_KEY_GENERATED"
    printf '# OVERRIDE_ADMIN_CREDS=yes makes the UI reset the admin password from\n'
    printf '# ADMIN_PASSWORD on every restart. Set it to "no" after first login if\n'
    printf '# you intend to change the admin password from inside the UI.\n'
    printf 'OVERRIDE_ADMIN_CREDS=yes\n'
}

# Write the .env file consumed by docker-compose.yml interpolation. 0600 — it
# holds the DB password / API token / admin password / UI secrets. The key set
# is per-INSTALL_TYPE (worker has no DB; scheduler/ui/api use an external
# DATABASE_URI; etc). Every value is guaranteed '$'-, "'"- and backslash-free
# (generated alnum, or operator input filtered through validate_docker_env_value).
render_docker_env() {
    local tmp
    # API_WHITELIST_IP for the distributed types — broad private ranges, per
    # docs/advanced.md; the API_TOKEN is the real cross-host authentication.
    local _docker_whitelist="127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
    # mktemp always creates with mode 0600 — no world-readable window.
    tmp=$(mktemp "${DOCKER_ENV_FILE}.XXXXXX") || {
        print_error "Cannot create a temporary file in $DOCKER_PROJECT_DIR."
        exit 1
    }
    _bw_register_secret_tmpfile "$tmp"
    {
        printf '# BunkerWeb Docker stack (%s) — generated by install-bunkerweb.sh\n' "$INSTALL_TYPE"
        # shellcheck disable=SC2016  # ${VAR} is literal text written into the .env comment.
        printf '# Docker Compose interpolates ${VAR} in docker-compose.yml from this file.\n'
        printf '# Contains secrets — keep it readable by root only (mode 0600).\n'
        printf '\n'
        printf 'COMPOSE_PROJECT_NAME=%s\n' "$(_docker_project_name)"
        printf 'BW_TAG=%s\n' "$DOCKER_IMAGE_TAG"
        case "$INSTALL_TYPE" in
            full)
                printf 'MARIADB_PASSWORD=%s\n' "$DOCKER_DB_PASSWORD_GENERATED"
                printf 'API_TOKEN=%s\n' "$DOCKER_API_TOKEN_GENERATED"
                printf 'API_WHITELIST_IP=%s\n' "$_docker_whitelist"
                printf 'HTTP_PORT=%s\n' "$DOCKER_HTTP_PORT"
                printf 'HTTPS_PORT=%s\n' "$DOCKER_HTTPS_PORT"
                _docker_env_admin_block
                ;;
            manager)
                printf 'MARIADB_PASSWORD=%s\n' "$DOCKER_DB_PASSWORD_GENERATED"
                printf 'API_TOKEN=%s\n' "$DOCKER_API_TOKEN_GENERATED"
                printf 'API_WHITELIST_IP=%s\n' "$_docker_whitelist"
                printf 'BUNKERWEB_INSTANCES=%s\n' "$BUNKERWEB_INSTANCES_INPUT"
                printf 'UI_PORT=%s\n' "$DOCKER_UI_PORT"
                _docker_env_admin_block
                ;;
            worker)
                printf 'API_TOKEN=%s\n' "$DOCKER_API_TOKEN_GENERATED"
                # Whitelist the manager IP(s) — only they may call the worker API.
                printf 'API_WHITELIST_IP=%s\n' "127.0.0.0/8 ${MANAGER_IP_INPUT}"
                printf 'HTTP_PORT=%s\n' "$DOCKER_HTTP_PORT"
                printf 'HTTPS_PORT=%s\n' "$DOCKER_HTTPS_PORT"
                printf 'API_PORT=%s\n' "$DOCKER_API_PORT"
                ;;
            scheduler)
                printf 'DATABASE_URI=%s\n' "$DOCKER_DATABASE_URI"
                printf 'API_TOKEN=%s\n' "$DOCKER_API_TOKEN_GENERATED"
                printf 'API_WHITELIST_IP=%s\n' "$_docker_whitelist"
                printf 'BUNKERWEB_INSTANCES=%s\n' "$BUNKERWEB_INSTANCES_INPUT"
                ;;
            ui)
                printf 'DATABASE_URI=%s\n' "$DOCKER_DATABASE_URI"
                printf 'UI_PORT=%s\n' "$DOCKER_UI_PORT"
                _docker_env_admin_block
                ;;
            api)
                printf 'DATABASE_URI=%s\n' "$DOCKER_DATABASE_URI"
                printf 'API_USERNAME=%s\n' "$API_USERNAME_INPUT"
                printf 'API_PASSWORD=%s\n' "$API_PASSWORD_INPUT"
                printf 'FASTAPI_PORT=%s\n' "$DOCKER_FASTAPI_PORT"
                ;;
        esac
    } >> "$tmp"
    mv -f "$tmp" "$DOCKER_ENV_FILE"
    chmod 600 "$DOCKER_ENV_FILE" 2>/dev/null || true
    print_status "Wrote $DOCKER_ENV_FILE (mode 0600)."
}

# Standard stack — bunkerweb + scheduler + ui + mariadb + redis.
# Mirrors docs/quickstart-guide.md (Docker tab); image tags and secrets are
# '${VAR}' placeholders resolved by Compose from the sibling .env file.
render_docker_compose_standard() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (standard) — generated by install-bunkerweb.sh.
# Values like ${BW_TAG} are interpolated by Docker Compose from the .env file
# next to this file. Edit .env to rotate secrets, then: docker compose up -d
x-bw-env: &bw-env
  API_WHITELIST_IP: "${API_WHITELIST_IP}"
  API_TOKEN: "${API_TOKEN}"
  DATABASE_URI: "mariadb+pymysql://bunkerweb:${MARIADB_PASSWORD}@bw-db:3306/db"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:${BW_TAG}
    ports:
      - "${HTTP_PORT}:8080/tcp"
      - "${HTTPS_PORT}:8443/tcp"
      - "${HTTPS_PORT}:8443/udp" # QUIC / HTTP3
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BW_TAG}
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "bunkerweb"
      SERVER_NAME: ""
      MULTISITE: "yes"
      UI_HOST: "http://bw-ui:7000"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
    volumes:
      - bw-storage:/data
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-ui:
    image: bunkerity/bunkerweb-ui:${BW_TAG}
    environment:
      <<: *bw-env
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
      OVERRIDE_ADMIN_CREDS: "${OVERRIDE_ADMIN_CREDS}"
      FLASK_SECRET: "${FLASK_SECRET}"
      TOTP_ENCRYPTION_KEYS: "${TOTP_ENCRYPTION_KEYS}"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-db:
    image: mariadb:11
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "${MARIADB_PASSWORD}"
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

  redis:
    image: redis:8-alpine
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy volatile-lru
      --save 60 1000
      --appendonly yes
    volumes:
      - redis-data:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-data:
  bw-storage:
  redis-data:

# Networks are project-scoped (Compose prefixes them with COMPOSE_PROJECT_NAME)
# and use Docker-assigned subnets, so several stacks co-exist on one host.
networks:
  bw-universe:
  bw-services:
  bw-db:
COMPOSE
}

# Autoconf stack — adds bw-autoconf + bw-docker (socket proxy) so containers
# labelled bunkerweb.* are configured automatically. Mirrors the
# "Docker autoconf" tab of docs/quickstart-guide.md.
render_docker_compose_autoconf() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (autoconf) — generated by install-bunkerweb.sh.
# Values like ${BW_TAG} are interpolated by Docker Compose from the .env file
# next to this file. Edit .env to rotate secrets, then: docker compose up -d
x-ui-env: &bw-ui-env
  AUTOCONF_MODE: "yes"
  DATABASE_URI: "mariadb+pymysql://bunkerweb:${MARIADB_PASSWORD}@bw-db:3306/db"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:${BW_TAG}
    ports:
      - "${HTTP_PORT}:8080/tcp"
      - "${HTTPS_PORT}:8443/tcp"
      - "${HTTPS_PORT}:8443/udp" # QUIC / HTTP3
    labels:
      - "bunkerweb.INSTANCE=yes" # Lets bw-autoconf discover this instance.
    environment:
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "${API_WHITELIST_IP}"
      API_TOKEN: "${API_TOKEN}"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BW_TAG}
    environment:
      <<: *bw-ui-env
      BUNKERWEB_INSTANCES: ""
      SERVER_NAME: ""
      API_WHITELIST_IP: "${API_WHITELIST_IP}"
      API_TOKEN: "${API_TOKEN}"
      MULTISITE: "yes"
      UI_HOST: "http://bw-ui:7000"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
    volumes:
      - bw-storage:/data
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:${BW_TAG}
    depends_on:
      - bw-docker
    environment:
      <<: *bw-ui-env
      DOCKER_HOST: "tcp://bw-docker:2375"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: "1"
      LOG_LEVEL: "warning"
    networks:
      - bw-docker

  bw-ui:
    image: bunkerity/bunkerweb-ui:${BW_TAG}
    environment:
      <<: *bw-ui-env
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
      OVERRIDE_ADMIN_CREDS: "${OVERRIDE_ADMIN_CREDS}"
      FLASK_SECRET: "${FLASK_SECRET}"
      TOTP_ENCRYPTION_KEYS: "${TOTP_ENCRYPTION_KEYS}"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-db:
    image: mariadb:11
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "${MARIADB_PASSWORD}"
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

  redis:
    image: redis:8-alpine
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy volatile-lru
      --save 60 1000
      --appendonly yes
    volumes:
      - redis-data:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-data:
  bw-storage:
  redis-data:

# Networks are project-scoped (Compose prefixes them with COMPOSE_PROJECT_NAME)
# and use Docker-assigned subnets, so several stacks co-exist on one host.
networks:
  bw-universe:
  bw-services:
  bw-docker:
  bw-db:
COMPOSE
}

# Manager stack — bw-scheduler + bw-ui + bw-db + redis. Manages the remote
# BunkerWeb workers listed in BUNKERWEB_INSTANCES. Mirrors docs/advanced.md.
render_docker_compose_manager() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (manager) — generated by install-bunkerweb.sh.
# Runs the Scheduler + Web UI and manages the remote BunkerWeb workers listed
# in BUNKERWEB_INSTANCES (.env). ${VAR} placeholders are interpolated by Docker
# Compose from the .env file next to this file.
x-bw-env: &bw-env
  API_WHITELIST_IP: "${API_WHITELIST_IP}"
  API_TOKEN: "${API_TOKEN}"
  DATABASE_URI: "mariadb+pymysql://bunkerweb:${MARIADB_PASSWORD}@bw-db:3306/db"

services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BW_TAG}
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "${BUNKERWEB_INSTANCES}"
      SERVER_NAME: ""
      MULTISITE: "yes"
      UI_HOST: "http://bw-ui:7000"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
    volumes:
      - bw-storage:/data
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-ui:
    image: bunkerity/bunkerweb-ui:${BW_TAG}
    ports:
      - "${UI_PORT}:7000/tcp"
    environment:
      <<: *bw-env
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
      OVERRIDE_ADMIN_CREDS: "${OVERRIDE_ADMIN_CREDS}"
      FLASK_SECRET: "${FLASK_SECRET}"
      TOTP_ENCRYPTION_KEYS: "${TOTP_ENCRYPTION_KEYS}"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-db:
    image: mariadb:11
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "${MARIADB_PASSWORD}"
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

  redis:
    image: redis:8-alpine
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy volatile-lru
      --save 60 1000
      --appendonly yes
    volumes:
      - redis-data:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-data:
  bw-storage:
  redis-data:

# Networks are project-scoped (Compose prefixes them with COMPOSE_PROJECT_NAME)
# and use Docker-assigned subnets, so several stacks co-exist on one host.
networks:
  bw-universe:
  bw-db:
COMPOSE
}

# Worker stack — a lone BunkerWeb instance managed by a remote Scheduler.
# The manager pushes configuration over the internal API on TCP port 5000.
render_docker_compose_worker() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (worker) — generated by install-bunkerweb.sh.
# A lone BunkerWeb instance managed by a remote Scheduler/Manager, which pushes
# configuration over the internal API on TCP port 5000.
services:
  bunkerweb:
    image: bunkerity/bunkerweb:${BW_TAG}
    ports:
      - "${HTTP_PORT}:8080/tcp"
      - "${HTTPS_PORT}:8443/tcp"
      - "${HTTPS_PORT}:8443/udp" # QUIC / HTTP3
      - "${API_PORT}:5000/tcp" # Internal API — firewall this to the manager IP(s) only.
    environment:
      API_WHITELIST_IP: "${API_WHITELIST_IP}"
      API_TOKEN: "${API_TOKEN}"
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

# Networks are project-scoped (Compose prefixes them with COMPOSE_PROJECT_NAME)
# and use Docker-assigned subnets, so several stacks co-exist on one host.
networks:
  bw-universe:
  bw-services:
COMPOSE
}

# Scheduler stack — bw-scheduler + redis, connecting to a shared external
# database via DATABASE_URI and managing the remote workers.
render_docker_compose_scheduler() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (scheduler) — generated by install-bunkerweb.sh.
# Runs only the Scheduler; it connects to the shared database via DATABASE_URI
# and manages the remote BunkerWeb workers listed in BUNKERWEB_INSTANCES.
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:${BW_TAG}
    environment:
      DATABASE_URI: "${DATABASE_URI}"
      BUNKERWEB_INSTANCES: "${BUNKERWEB_INSTANCES}"
      API_WHITELIST_IP: "${API_WHITELIST_IP}"
      API_TOKEN: "${API_TOKEN}"
      SERVER_NAME: ""
      MULTISITE: "yes"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
    volumes:
      - bw-storage:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

  redis:
    image: redis:8-alpine
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy volatile-lru
      --save 60 1000
      --appendonly yes
    volumes:
      - redis-data:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-storage:
  redis-data:

# Network is project-scoped (Compose prefixes it with COMPOSE_PROJECT_NAME) and
# uses a Docker-assigned subnet, so several stacks co-exist on one host.
networks:
  bw-universe:
COMPOSE
}

# Web UI stack — bw-ui only, connecting to a shared external database.
render_docker_compose_ui() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (ui) — generated by install-bunkerweb.sh.
# Runs only the Web UI; it connects to the shared database via DATABASE_URI.
services:
  bw-ui:
    image: bunkerity/bunkerweb-ui:${BW_TAG}
    ports:
      - "${UI_PORT}:7000/tcp"
    environment:
      DATABASE_URI: "${DATABASE_URI}"
      ADMIN_USERNAME: "${ADMIN_USERNAME}"
      ADMIN_PASSWORD: "${ADMIN_PASSWORD}"
      OVERRIDE_ADMIN_CREDS: "${OVERRIDE_ADMIN_CREDS}"
      FLASK_SECRET: "${FLASK_SECRET}"
      TOTP_ENCRYPTION_KEYS: "${TOTP_ENCRYPTION_KEYS}"
    restart: "unless-stopped"
    networks:
      - bw-universe

# Network is project-scoped (Compose prefixes it with COMPOSE_PROJECT_NAME) and
# uses a Docker-assigned subnet, so several stacks co-exist on one host.
networks:
  bw-universe:
COMPOSE
}

# FastAPI stack — bw-api only, connecting to a shared external database.
render_docker_compose_api() {
    cat > "$DOCKER_COMPOSE_FILE" <<'COMPOSE'
# BunkerWeb Docker stack (api) — generated by install-bunkerweb.sh.
# Runs only the FastAPI control service; it connects to the shared database via
# DATABASE_URI. Put it behind a BunkerWeb instance before exposing it publicly.
services:
  bw-api:
    image: bunkerity/bunkerweb-api:${BW_TAG}
    ports:
      - "${FASTAPI_PORT}:8888/tcp"
    environment:
      DATABASE_URI: "${DATABASE_URI}"
      API_USERNAME: "${API_USERNAME}"
      API_PASSWORD: "${API_PASSWORD}"
    restart: "unless-stopped"
    networks:
      - bw-universe

# Network is project-scoped (Compose prefixes it with COMPOSE_PROJECT_NAME) and
# uses a Docker-assigned subnet, so several stacks co-exist on one host.
networks:
  bw-universe:
COMPOSE
}

# Render the compose file for the chosen install type, then ask Compose to
# validate it (catches a malformed .env or YAML before we ever call 'up').
render_docker_compose() {
    case "$INSTALL_TYPE" in
        full)
            if [ "$DOCKER_AUTOCONF" = "yes" ]; then
                render_docker_compose_autoconf
            else
                render_docker_compose_standard
            fi
            ;;
        manager)   render_docker_compose_manager   ;;
        worker)    render_docker_compose_worker    ;;
        scheduler) render_docker_compose_scheduler ;;
        ui)        render_docker_compose_ui        ;;
        api)       render_docker_compose_api       ;;
        *)
            print_error "Internal error: no Docker compose renderer for install type '$INSTALL_TYPE'."
            exit 1
            ;;
    esac
    chmod 644 "$DOCKER_COMPOSE_FILE" 2>/dev/null || true
    print_status "Wrote $DOCKER_COMPOSE_FILE."
    if ! _docker_compose config -q >/dev/null 2>&1; then
        print_error "Generated docker-compose.yml failed validation ('docker compose config'):"
        # Re-run WITHOUT -q so the parse error reaches the operator (stdout to
        # /dev/null — only the diagnostic on stderr matters here).
        _docker_compose config >/dev/null || true
        exit 1
    fi
}

# Poll until every service reports 'running', or DOCKER_WAIT_TIMEOUT elapses.
# Returns 0 when ready, 1 on timeout (caller surfaces a logs hint, not fatal).
wait_for_docker_stack_ready() {
    local deadline=$(( $(date +%s) + DOCKER_WAIT_TIMEOUT ))
    local total running=0
    total=$(_docker_compose ps --services 2>/dev/null | grep -c . || echo 0)
    [ "$total" -gt 0 ] || total=5
    print_status "Waiting for $total services to start (timeout ${DOCKER_WAIT_TIMEOUT}s)..."
    while [ "$(date +%s)" -lt "$deadline" ]; do
        running=$(_docker_compose ps --services --status running 2>/dev/null | grep -c . || echo 0)
        if [ "$running" -ge "$total" ]; then
            print_status "All $total services are running."
            return 0
        fi
        sleep 3
    done
    print_warning "Timed out waiting for the stack ($running/$total services running)."
    return 1
}

# Post-install summary — per-type entry point, management hints. Secrets are
# NEVER printed; the operator is pointed at the 0600 .env file that holds them.
show_docker_final_info() {
    resolve_display_server_ip
    local ip="${RESOLVED_SERVER_IP:-your-server-ip}"
    local env_file="$DOCKER_ENV_FILE"
    # HTTPS URL port suffix — omitted when the port is the scheme default (443).
    local _https_sfx=""
    [ "$DOCKER_HTTPS_PORT" != "443" ] && _https_sfx=":${DOCKER_HTTPS_PORT}"
    {
        echo
        echo "========================================="
        echo "  🐳 BunkerWeb Docker stack is up!"
        echo "========================================="
        echo
        echo "  📂 Compose directory : $DOCKER_PROJECT_DIR"
        echo "  📦 Installation type : $INSTALL_TYPE"
        [ "$INSTALL_TYPE" = "full" ] && \
            echo "  🧩 Variant           : $([ "$DOCKER_AUTOCONF" = "yes" ] && echo "autoconf" || echo "standard")"
        echo "  🏷️  Image tag         : $DOCKER_IMAGE_TAG"
        echo
        echo "  🔑 Secrets (admin password, API token, DB password, ...) are stored in"
        echo "     the generated env file — readable by root only (mode 0600):"
        echo "       $env_file"
        echo "     Inspect a single value with, e.g.:"
        echo "       grep '^ADMIN_PASSWORD=' \"$env_file\""
        echo
        case "$INSTALL_TYPE" in
            full)
                echo "  🧙 Finish setup in the web wizard:"
                echo "       https://${ip}${_https_sfx}/setup"
                echo "     (self-signed certificate on first boot — accept the browser warning)"
                echo
                echo "  👤 Web UI admin username : ${UI_ADMIN_USERNAME_INPUT}"
                echo "  🔑 Web UI admin password : see ADMIN_PASSWORD in $env_file"
                [ "$DOCKER_AUTOCONF" = "yes" ] && {
                    echo
                    echo "  🤖 Autoconf is active — label your service containers with"
                    echo "     'bunkerweb.*' labels and they are configured automatically."
                }
                ;;
            manager)
                echo "  🌐 Web UI:  http://${ip}:${DOCKER_UI_PORT}"
                echo
                echo "  👤 Web UI admin username : ${UI_ADMIN_USERNAME_INPUT}"
                echo "  🔑 Web UI admin password : see ADMIN_PASSWORD in $env_file"
                echo
                echo "  🔗 Managed worker instances: ${BUNKERWEB_INSTANCES_INPUT:-<none yet>}"
                echo "  🔑 Shared API token: see API_TOKEN in $env_file"
                echo "     Set the SAME API_TOKEN value on every worker host."
                ;;
            worker)
                echo "  🛰️  This worker is managed by a remote Scheduler/Manager."
                echo "  🔗 Manager IP(s) allowed to push config: ${MANAGER_IP_INPUT}"
                echo
                echo "  ⚠️  Host TCP port ${DOCKER_API_PORT} (internal API) is published on 0.0.0.0."
                echo "     Firewall it so ONLY the manager IP(s) above can reach it."
                echo
                echo "  🔑 Shared API token: see API_TOKEN in $env_file"
                echo "     It must match the manager's API_TOKEN exactly."
                ;;
            scheduler)
                echo "  🧠 Headless Scheduler — no Web UI on this host."
                echo "  🔗 Managed worker instances: ${BUNKERWEB_INSTANCES_INPUT:-<none yet>}"
                echo "  🔑 Shared API token: see API_TOKEN in $env_file"
                echo "     Set the SAME API_TOKEN value on every worker host."
                echo "  🗄️  Database: see DATABASE_URI in $env_file"
                ;;
            ui)
                echo "  🌐 Web UI:  http://${ip}:${DOCKER_UI_PORT}"
                echo
                echo "  👤 Web UI admin username : ${UI_ADMIN_USERNAME_INPUT}"
                echo "  🔑 Web UI admin password : see ADMIN_PASSWORD in $env_file"
                echo
                echo "  🗄️  This UI shares the database — see DATABASE_URI in $env_file"
                ;;
            api)
                echo "  🌐 FastAPI service:  http://${ip}:${DOCKER_FASTAPI_PORT}"
                echo
                echo "  👤 FastAPI admin username : ${API_USERNAME_INPUT}"
                echo "  🔑 FastAPI admin password : see API_PASSWORD in $env_file"
                echo
                echo "  🛡️  Put this API behind a BunkerWeb instance before exposing it publicly."
                ;;
        esac
        echo
        echo "  ⚙️  Manage the stack (run from $DOCKER_PROJECT_DIR):"
        echo "       docker compose ps           # status"
        echo "       docker compose logs -f      # follow logs"
        echo "       docker compose down         # stop"
        case "$INSTALL_TYPE" in
            full|manager)
                echo
                echo "  🗄️  The MariaDB root password is randomized at first boot; it is not"
                echo "     needed for BunkerWeb. Retrieve it once with:"
                echo "       docker compose logs bw-db | grep -i 'GENERATED ROOT PASSWORD'"
                ;;
        esac
        echo "========================================="
        echo
    } >&"${_BW_OUT_FD:-1}"
}

# Back up a file that is about to be overwritten. Secrets stay 0600.
_docker_backup_file() {
    local f="$1" bak
    [ -f "$f" ] || return 0
    bak="${f}.bak.$(date +%s)"
    cp -p "$f" "$bak" 2>/dev/null || cp "$f" "$bak"
    chmod 600 "$bak" 2>/dev/null || true
    print_warning "Backed up existing $(basename "$f") to $(basename "$bak")"
}

# Guard against clobbering an existing stack in the target directory.
# Aborts unless the operator opts in (interactive prompt, or --overwrite-compose).
_docker_check_existing() {
    local existing=""
    [ -f "$DOCKER_COMPOSE_FILE" ] && existing="docker-compose.yml"
    [ -f "$DOCKER_ENV_FILE" ] && existing="${existing:+$existing, }.env"
    [ -n "$existing" ] || return 0

    print_warning "Found existing files in $DOCKER_PROJECT_DIR: $existing"
    if [ "$DOCKER_OVERWRITE_EXISTING" = "yes" ]; then
        print_status "Proceeding with overwrite (--overwrite-compose)."
    elif [ "$INTERACTIVE_MODE" = "yes" ]; then
        if ! tui_yesno "Existing Stack Files" \
            "Existing files in $DOCKER_PROJECT_DIR: ${existing}.\nThey will be backed up (.bak.<timestamp>) and overwritten.\n\nContinue?" "no"; then
            print_error "Aborted — existing files left untouched."
            exit 0
        fi
    else
        print_error "Existing compose files present. Re-run with --overwrite-compose to replace them."
        exit 1
    fi
    _docker_backup_file "$DOCKER_COMPOSE_FILE"
    _docker_backup_file "$DOCKER_ENV_FILE"
}

# Orchestrator for INSTALL_TYPE=docker. Renders files, brings the stack up,
# waits for readiness, prints the summary. Called from main(); exits the script.
docker_install_flow() {
    # Runs only after the operator confirmed the configuration. _docker_ensure_runtime
    # performs any Docker install that check_docker_prereqs deferred — so the first
    # system mutation of the Docker path happens here, post-confirm, exactly like
    # the Linux phases run only after the same confirm screen.
    _docker_ensure_runtime

    print_step "🐳 Generating the BunkerWeb Docker stack in $DOCKER_PROJECT_DIR"
    _docker_check_existing
    render_docker_env
    render_docker_compose

    if [ "$DOCKER_PULL" = "yes" ]; then
        print_step "📥 Pulling container images"
        run_cmd _docker_compose pull
    fi

    print_step "🚀 Starting the stack"
    run_cmd _docker_compose up -d

    wait_for_docker_stack_ready || \
        print_warning "Check progress with: cd $DOCKER_PROJECT_DIR && docker compose ps"

    show_docker_final_info
}

# Generate a URL-safe random secret of N characters (default 32).
generate_secret() {
    local length="${1:-32}"
    local out=""

    if command -v openssl >/dev/null 2>&1; then
        out=$(openssl rand -base64 48 2>/dev/null | tr -dc 'A-Za-z0-9' | head -c "$length")
    fi

    if [ -z "$out" ] && [ -r /dev/urandom ]; then
        out=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length")
    fi

    if [ -z "$out" ]; then
        # Last-resort: no /dev/urandom, no openssl.
        out=$(date +%s%N | sha256sum 2>/dev/null | head -c "$length")
    fi

    printf '%s' "$out"
}

# Generates a UI admin password matching the UI regex (≥8, lower/upper/digit/special): 18 + Aa1!.
generate_ui_admin_password() {
    local base
    base=$(generate_secret 18)
    printf '%sAa1!' "$base"
}

# Validate a UI admin password against the same character classes the UI requires.
# Returns 0 if valid, 1 otherwise.
validate_ui_admin_password() {
    local pw="$1"

    if [ -z "$pw" ] || [ "${#pw}" -lt 8 ]; then
        return 1
    fi
    [[ "$pw" =~ [a-z] ]] || return 1
    [[ "$pw" =~ [A-Z] ]] || return 1
    [[ "$pw" =~ [0-9] ]] || return 1
    [[ "$pw" =~ [^A-Za-z0-9] ]] || return 1
    return 0
}

# DB password — looser than UI rule (MariaDB/Postgres accept short/digit-only).
# Rejects chars that break unquoted shell + SQL pipelines (CREATE USER, GRANT, DSN).
validate_db_password() {
    local pw="$1"

    if [ -z "$pw" ] || [ "${#pw}" -lt 8 ]; then
        return 1
    fi
    # Reject ' " \ ` — break heredoc CREATE USER, DSN assembly, shell history.
    if [[ "$pw" == *\'* ]] || [[ "$pw" == *\"* ]] || [[ "$pw" == *\\* ]] || [[ "$pw" == *\`* ]]; then
        return 1
    fi
    return 0
}

# Redis requirepass — written into redis.conf via _redis_conf_set.
# Reject whitespace and chars that break the config line or shell/DSN assembly.
validate_redis_password() {
    local pw="$1"

    if [ -z "$pw" ] || [ "${#pw}" -lt 8 ]; then
        return 1
    fi
    # Reject ' " \ ` # and whitespace — break redis.conf requirepass line, DSN, shell history.
    if [[ "$pw" == *\'* ]] || [[ "$pw" == *\"* ]] || [[ "$pw" == *\\* ]] || [[ "$pw" == *\`* ]] \
        || [[ "$pw" == *"#"* ]] || [[ "$pw" =~ [[:space:]] ]]; then
        return 1
    fi
    return 0
}

# DB identifier — SQL-safe ASCII that survives a URL path component intact.
# Matches MariaDB/Postgres unquoted-identifier rules.
validate_db_identifier() {
    local s="$1"
    [ -n "$s" ] || return 1
    [ "${#s}" -le 63 ] || return 1
    [[ "$s" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

# Hostname / IPv4 / IPv6 — rejects whitespace, shell metas, @:/ DSN separators.
# Two valid shapes: bracketed IPv6 `[2001:db8::1]`, or alnum-leading host (RFC 1123 §2.1).
# Leading dash explicitly rejected — `mariadb -h -Smalicious` would otherwise inject `-S`.
validate_db_host() {
    local s="$1"
    [ -n "$s" ] || return 1
    [ "${#s}" -le 253 ] || return 1
    [[ "$s" =~ ^(\[[0-9a-fA-F:]+\]|[A-Za-z0-9][A-Za-z0-9._-]*)$ ]]
}

# UI admin username — mirrors UI's server-side rule (alnum + . _ -, 1–64 chars).
# Catches malformed values before they land in ui.env and gunicorn rejects on first boot.
validate_ui_admin_username() {
    local s="$1"
    [ -n "$s" ] || return 1
    [ "${#s}" -le 64 ] || return 1
    [[ "$s" =~ ^[A-Za-z0-9._-]+$ ]]
}

# Docker image tag — Docker Hub tag grammar: first char alnum or '_', then
# alnum/'.'/'_'/'-', 1–128 chars. A leading '.' or '-' is invalid.
# Rejects ':' and '/' so callers always form "${image}:${tag}" themselves.
validate_docker_image_tag() {
    local s="$1"
    [ -n "$s" ] || return 1
    [ "${#s}" -le 128 ] || return 1
    [[ "$s" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]]
}

# Turn a BunkerWeb version into a Docker-Hub-safe image tag.
# Debian-style versions use '~' (e.g. 1.6.10~rc7) which Docker tags forbid → '-'.
# Empty input falls back to "latest".
derive_docker_image_tag() {
    local v="${1:-}"
    if [ -z "$v" ]; then
        printf 'latest'
        return 0
    fi
    printf '%s' "${v//\~/-}"
}

# URL-encode for SQLAlchemy DSN user:password — escapes @ : / % ? # & cleanly.
# Requires python3 (refuse pass-through; reserved chars would corrupt the DSN).
urlencode_dsn_part() {
    local raw="$1"
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "python3 is required to safely URL-encode database credentials."
        print_error "Install python3 (apt install python3 / dnf install python3) and retry."
        return 1
    fi
    python3 -c 'import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.argv[1], safe=""))' "$raw"
}

# Default TCP port per external-DB engine.
default_db_port() {
    case "$1" in
        mariadb|mysql) echo "3306" ;;
        postgresql)    echo "5432" ;;
        *)             echo "" ;;
    esac
}

# ---------------------------------------------------------------------------
# Default env-file templates — mirror what BunkerWeb start scripts write
# (src/linux/scripts/{start,bunkerweb-ui,bunkerweb-scheduler,bunkerweb-api}.sh).
# Each helper only writes when the file is empty/missing; caller's set_config_kv
# patches the resulting template in place.
# ---------------------------------------------------------------------------

write_default_variables_env_template() {
    local config_file="$1"
    if [ -s "$config_file" ]; then
        return 0
    fi
    ensure_config_file "$config_file"
    cat > "$config_file" <<'EOF'
# BunkerWeb runtime configuration (shared across scheduler, UI and API).
# The IS_LOADING flag is managed automatically by the deb/rpm postinstall
# and the wizard; do not pre-seed it here.
SERVER_NAME=
DNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4
HTTP_PORT=80
HTTPS_PORT=443
API_LISTEN_IP=127.0.0.1
API_TOKEN=
KEEP_CONFIG_ON_RESTART=no
# Shared database connection (read by scheduler, UI and API).
# Defaults to SQLite when unset. Examples:
#   sqlite:////var/lib/bunkerweb/db.sqlite3
#   mariadb+pymysql://bunkerweb:password@127.0.0.1:3306/bw_db
#   postgresql+psycopg://bunkerweb:password@127.0.0.1:5432/bw_db
# DATABASE_URI=
# DATABASE_LOG_LEVEL=warning
# DATABASE_RETRY_TIMEOUT=60
EOF
    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
}

write_default_ui_env_template() {
    local config_file="$1"
    if [ -s "$config_file" ]; then
        return 0
    fi
    ensure_config_file "$config_file"
    cat > "$config_file" <<'EOF'
# OVERRIDE_ADMIN_CREDS=no
ADMIN_USERNAME=
ADMIN_PASSWORD=
# FLASK_SECRET=changeme
# TOTP_ENCRYPTION_KEYS=changeme
LISTEN_ADDR=127.0.0.1
# LISTEN_PORT=7000
# MAX_CONTENT_LENGTH=50MB
FORWARDED_ALLOW_IPS=127.0.0.1,::1
PROXY_ALLOW_IPS=127.0.0.1,::1
# ENABLE_HEALTHCHECK=no
LOG_LEVEL=info
LOG_TYPES=file
# LOG_FILE_PATH=/var/log/bunkerweb/ui.log
EOF
    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
}

write_default_scheduler_env_template() {
    local config_file="$1"
    if [ -s "$config_file" ]; then
        return 0
    fi
    ensure_config_file "$config_file"
    cat > "$config_file" <<'EOF'
LOG_LEVEL=info
LOG_TYPES=file
# LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
# in seconds
HEALTHCHECK_INTERVAL=30

# in seconds (the minimum is calculated by the formula and whichever is greater: RELOAD_MIN_TIMEOUT or count(SERVERS) * 2))
RELOAD_MIN_TIMEOUT=5
EOF
    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
}

write_default_api_env_template() {
    local config_file="$1"
    if [ -s "$config_file" ]; then
        return 0
    fi
    ensure_config_file "$config_file"
    cat > "$config_file" <<'EOF'
# ==============================
# BunkerWeb API Configuration
# This file lists all supported API environment variables with their defaults.
# Uncomment and adjust as needed. Lines starting with # are ignored.
# ==============================

# --- Network & Proxy ---
# Listen address/port for the API
LISTEN_ADDR=127.0.0.1
LISTEN_PORT=8888
# Trusted proxy IPs for X-Forwarded-* headers (comma-separated).
# Default is restricted to loopback for security.
FORWARDED_ALLOW_IPS=127.0.0.1,::1
# Trusted proxy IPs for PROXY protocol (comma-separated).
# Defaults to FORWARDED_ALLOW_IPS when unset.
PROXY_ALLOW_IPS=127.0.0.1,::1

# --- Logging & Runtime ---
# LOG_LEVEL affects most components; CUSTOM_LOG_LEVEL overrides when provided.
# LOG_LEVEL=info
LOG_TYPES=file
# LOG_FILE_PATH=/var/log/bunkerweb/api.log
# Number of workers/threads (auto if unset).
# MAX_WORKERS=<auto>
# MAX_THREADS=<auto>

# --- Authentication & Authorization ---
# Optional admin Bearer token (grants full access when provided).
# API_TOKEN=changeme
# Bootstrap admin user (created/validated on startup if provided).
# API_USERNAME=
# API_PASSWORD=
# Force re-applying bootstrap admin credentials on startup (use with care).
# OVERRIDE_API_CREDS=no
# Fine-grained ACLs can be enabled/disabled here.
# API_ACL_BOOTSTRAP_FILE=

# --- IP allowlist ---
# Enable and shape inbound IP allowlist for the API.
# API_WHITELIST_ENABLED=yes
WHITELIST_IPS=127.0.0.1

# --- FastAPI surface ---
# Customize or disable documentation endpoints. Use 'disabled' to turn off.
# API_TITLE=BunkerWeb API
# API_DOCS_URL=/docs
# API_REDOC_URL=/redoc
# API_OPENAPI_URL=/openapi.json
# Mount the API under a subpath (useful behind reverse proxies).
# API_ROOT_PATH=

# --- TLS/SSL ---
# Enable TLS for the API listener (requires cert and key).
# API_SSL_ENABLED=no
# Path to PEM-encoded certificate and private key.
# API_SSL_CERTFILE=/etc/ssl/certs/bunkerweb-api.crt
# API_SSL_KEYFILE=/etc/ssl/private/bunkerweb-api.key
# Optional chain/CA bundle and cipher suite.
# API_SSL_CA_CERTS=
# API_SSL_CIPHERS_CUSTOM=
# API_SSL_CIPHERS_LEVEL=modern   # choices: modern|intermediate

# --- Biscuit keys & policy ---
# Bind token to client IP (except private ranges).
# CHECK_PRIVATE_IP=yes
# Biscuit token lifetime in seconds (0 disables expiry).
# API_BISCUIT_TTL_SECONDS=3600
# Provide Biscuit keys via env (hex) instead of files.
# BISCUIT_PUBLIC_KEY=
# BISCUIT_PRIVATE_KEY=

# --- Rate limiting ---
# Enable/disable and shape rate limiting.
# API_RATE_LIMIT_ENABLED=yes
# API_RATE_LIMIT_HEADERS_ENABLED=yes
# Global default limit (times per seconds).
# API_RATE_LIMIT_TIMES=100
# API_RATE_LIMIT_SECONDS=60
# Authentication endpoint limit.
# API_RATE_LIMIT_AUTH_TIMES=10
# API_RATE_LIMIT_AUTH_SECONDS=60
# Advanced limits and rules (CSV/JSON/YAML).
# API_RATE_LIMIT_DEFAULTS="200/minute"
# API_RATE_LIMIT_APPLICATION_LIMITS=
# API_RATE_LIMIT_RULES=
# Strategy: fixed-window | moving-window | sliding-window-counter
# API_RATE_LIMIT_STRATEGY=fixed-window
# Key selector: ip | user | path | method | header:<Name>
# API_RATE_LIMIT_KEY=ip
# Exempt IPs (space or comma-separated CIDRs).
# API_RATE_LIMIT_EXEMPT_IPS=
# Storage options in JSON (merged with Redis settings if USE_REDIS=yes).
# API_RATE_LIMIT_STORAGE_OPTIONS=

# --- Shared settings (defined in /etc/bunkerweb/variables.env) ---
# The following are read from variables.env and apply to every BunkerWeb
# service (scheduler, UI, API). Set them there rather than duplicating here:
#   DATABASE_URI, USE_REDIS, REDIS_HOST, REDIS_PORT, REDIS_DATABASE,
#   REDIS_USERNAME, REDIS_PASSWORD, REDIS_SSL, REDIS_SSL_VERIFY,
#   REDIS_TIMEOUT, REDIS_KEEPALIVE_POOL, REDIS_SENTINEL_HOSTS,
#   REDIS_SENTINEL_MASTER, REDIS_SENTINEL_USERNAME, REDIS_SENTINEL_PASSWORD
EOF
    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
}

# Function to check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This script must be run as root. Please use sudo or run as root."
        exit 1
    fi
}

# Function to detect operating system
# Map a lowercase distro ID to its canonical display name. Used only by
# detect_os() so the "Detected OS:" line is consistent across distros
# (otherwise /etc/os-release gives lowercase IDs like "debian" / "ubuntu"
# while FreeBSD has its own branch that prints "FreeBSD").
distro_display_name() {
    case "$1" in
        debian)      echo "Debian" ;;
        ubuntu)      echo "Ubuntu" ;;
        fedora)      echo "Fedora" ;;
        rhel|redhat) echo "RHEL" ;;
        rocky)       echo "Rocky Linux" ;;
        almalinux)   echo "AlmaLinux" ;;
        centos)      echo "CentOS" ;;
        opensuse|opensuse-leap|opensuse-tumbleweed) echo "openSUSE" ;;
        freebsd)     echo "FreeBSD" ;;
        "")          echo "unknown" ;;
        *)
            # Fallback: capitalize first letter only.
            printf '%s%s\n' "$(printf '%s' "$1" | cut -c1 | tr '[:lower:]' '[:upper:]')" "$(printf '%s' "$1" | cut -c2-)"
            ;;
    esac
}

detect_os() {
    DISTRO_ID=""
    DISTRO_VERSION=""
    DISTRO_CODENAME=""

    # Check for FreeBSD first
    if [ "$(uname)" = "FreeBSD" ]; then
        DISTRO_ID="freebsd"
        DISTRO_VERSION=$(freebsd-version -u 2>/dev/null | cut -d'-' -f1 || uname -r | cut -d'-' -f1)
        DISTRO_CODENAME=""
        print_status "Detected OS: $(distro_display_name "$DISTRO_ID") $DISTRO_VERSION"
        return
    fi

    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
        DISTRO_VERSION="$VERSION_ID"
        DISTRO_CODENAME="$VERSION_CODENAME"
    elif [ -f /etc/redhat-release ]; then
        DISTRO_ID="redhat"
        DISTRO_VERSION=$(grep -oE '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
    elif command -v lsb_release >/dev/null 2>&1; then
        DISTRO_ID=$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]')
        DISTRO_VERSION=$(lsb_release -rs 2>/dev/null)
        DISTRO_CODENAME=$(lsb_release -cs 2>/dev/null)
    else
        print_error "Unable to detect operating system."
        print_error "Checked: /etc/os-release, /etc/redhat-release, lsb_release."
        print_error "On minimal images set ID and VERSION_ID in /etc/os-release and re-run."
        exit 1
    fi

    # Normalize legacy distro ID aliases: some AlmaLinux derivatives report "alma",
    # and the /etc/redhat-release fallback above sets "redhat" on os-release-less boxes.
    case "$DISTRO_ID" in
        alma) DISTRO_ID="almalinux" ;;
        redhat) DISTRO_ID="rhel" ;;
    esac

    print_status "Detected OS: $(distro_display_name "$DISTRO_ID") $DISTRO_VERSION"
}

# Function to detect system architecture and warn for unsupported combinations
detect_architecture() {
    SYSTEM_ARCH=$(uname -m 2>/dev/null || echo "unknown")
    NORMALIZED_ARCH="$SYSTEM_ARCH"
    case "$SYSTEM_ARCH" in
        x86_64|amd64)
            NORMALIZED_ARCH="amd64"
            ;;
        aarch64|arm64)
            NORMALIZED_ARCH="arm64"
            ;;
        armv7l|armhf)
            NORMALIZED_ARCH="armhf"
            ;;
        unknown)
            print_warning "Unable to detect system architecture."
            ;;
        *)
            print_warning "Architecture $SYSTEM_ARCH is not officially tested. Supported: x86_64 (amd64), aarch64 (arm64), armv7l (armhf)."
            if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                if ! tui_yesno "Unsupported Architecture" \
                    "Architecture '$SYSTEM_ARCH' has not been validated. Continue anyway?" "no"; then
                    exit 1
                fi
            fi
            ;;
    esac
    export NORMALIZED_ARCH
}

# --- ask_docker_preferences helpers --------------------------------------
# Each helper is a no-op when its target value is already set (by a CLI flag);
# under --yes it fills a safe default or aborts when a value cannot be defaulted.

# Image tag — all types. derive_docker_image_tag always maps '~' → '-' so a
# Debian-style version (1.6.10~rc7) becomes a valid Docker Hub tag (1.6.10-rc7),
# whether it came from --image-tag, the interactive prompt, or BUNKERWEB_VERSION.
_docker_ask_image_tag() {
    local _default_tag
    _default_tag=$(derive_docker_image_tag "$BUNKERWEB_VERSION")
    if [ -n "$DOCKER_IMAGE_TAG" ]; then
        # Flag-provided — still normalize '~' → '-'.
        DOCKER_IMAGE_TAG=$(derive_docker_image_tag "$DOCKER_IMAGE_TAG")
        return 0
    fi
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        DOCKER_IMAGE_TAG="$_default_tag"
        return 0
    fi
    tui_section "🏷️  BunkerWeb Image Tag"
    while true; do
        DOCKER_IMAGE_TAG=$(tui_input "Image Tag" \
            "Docker Hub tag for the BunkerWeb images:" "$_default_tag") \
            || DOCKER_IMAGE_TAG="$_default_tag"
        [ -z "$DOCKER_IMAGE_TAG" ] && DOCKER_IMAGE_TAG="$_default_tag"
        # Normalize '~' → '-' before validating so a typed Debian-style version works.
        DOCKER_IMAGE_TAG=$(derive_docker_image_tag "$DOCKER_IMAGE_TAG")
        validate_docker_image_tag "$DOCKER_IMAGE_TAG" && break
        tui_msgbox "Invalid Tag" "Image tags allow letters, digits, '.', '_' and '-' only."
        DOCKER_IMAGE_TAG=""
    done
}

# Web UI admin username + password — full/manager/ui.
_docker_ask_admin() {
    if [ -z "$UI_ADMIN_USERNAME_INPUT" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            tui_section "👤 Web UI Admin Account"
            while true; do
                UI_ADMIN_USERNAME_INPUT=$(tui_input "Admin Username" \
                    "Username for the first Web UI admin:" "admin") \
                    || UI_ADMIN_USERNAME_INPUT="admin"
                [ -z "$UI_ADMIN_USERNAME_INPUT" ] && UI_ADMIN_USERNAME_INPUT="admin"
                validate_ui_admin_username "$UI_ADMIN_USERNAME_INPUT" && break
                tui_msgbox "Invalid Username" "Use letters, digits, '.', '_' and '-' (1–64 chars)."
                UI_ADMIN_USERNAME_INPUT=""
            done
        else
            UI_ADMIN_USERNAME_INPUT="admin"
        fi
    fi
    if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            while true; do
                UI_ADMIN_PASSWORD_INPUT=$(tui_password "Admin Password" \
                    "Web UI admin password (leave empty to auto-generate):") \
                    || UI_ADMIN_PASSWORD_INPUT=""
                if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
                    UI_ADMIN_PASSWORD_INPUT=$(generate_ui_admin_password)
                    break
                fi
                if validate_ui_admin_password "$UI_ADMIN_PASSWORD_INPUT" \
                    && validate_docker_env_value "$UI_ADMIN_PASSWORD_INPUT"; then
                    break
                fi
                tui_msgbox "Invalid Password" "Need 8+ chars with a lowercase, uppercase, digit and special character — and no '\$', single quote or backslash."
                UI_ADMIN_PASSWORD_INPUT=""
            done
        else
            UI_ADMIN_PASSWORD_INPUT=$(generate_ui_admin_password)
        fi
    fi
}

# MariaDB 'bunkerweb' user password — full/manager (bundled bw-db).
_docker_ask_db_password() {
    [ -n "$DOCKER_DB_PASSWORD_GENERATED" ] && return 0
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        DOCKER_DB_PASSWORD_GENERATED=$(generate_secret 32)
        return 0
    fi
    while true; do
        DOCKER_DB_PASSWORD_GENERATED=$(tui_password "Database Password" \
            "MariaDB password for the 'bunkerweb' user (leave empty to auto-generate):") \
            || DOCKER_DB_PASSWORD_GENERATED=""
        if [ -z "$DOCKER_DB_PASSWORD_GENERATED" ]; then
            DOCKER_DB_PASSWORD_GENERATED=$(generate_secret 32)
            break
        fi
        if validate_db_password "$DOCKER_DB_PASSWORD_GENERATED" \
            && validate_docker_env_value "$DOCKER_DB_PASSWORD_GENERATED"; then
            break
        fi
        tui_msgbox "Invalid Password" "Need 8+ chars and no quotes, backslash, backtick or '\$'."
        DOCKER_DB_PASSWORD_GENERATED=""
    done
}

# Shared API token — manager/worker/scheduler. MUST be identical on every host,
# so it is operator-provided (never auto-generated for these types).
_docker_ask_shared_token() {
    [ -n "$DOCKER_API_TOKEN_GENERATED" ] && return 0
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        print_error "--api-token is required for a non-interactive --docker ${INSTALL_TYPE} install."
        print_error "The token must be IDENTICAL on the manager and every worker/scheduler host."
        exit 1
    fi
    tui_section "🔑 Shared API Token" \
        "Authenticates the manager↔worker API. Use the SAME value on every host of this cluster."
    while true; do
        DOCKER_API_TOKEN_GENERATED=$(tui_password "Shared API Token" \
            "API token shared across the manager and all workers:") \
            || DOCKER_API_TOKEN_GENERATED=""
        if [ -z "$DOCKER_API_TOKEN_GENERATED" ]; then
            tui_msgbox "Token Required" "A shared API token is mandatory for manager/worker/scheduler installs."
            continue
        fi
        validate_docker_env_value "$DOCKER_API_TOKEN_GENERATED" && break
        tui_msgbox "Invalid Token" "The token must not contain '\$', a single quote or a backslash."
        DOCKER_API_TOKEN_GENERATED=""
    done
}

# Remote worker IPs (BUNKERWEB_INSTANCES) — manager/scheduler. May be empty.
_docker_ask_instances() {
    [ -n "$BUNKERWEB_INSTANCES_INPUT" ] && return 0
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        print_warning "No worker instances configured (--instances); add them later via the scheduler."
        return 0
    fi
    tui_section "🔗 Remote Worker Instances" \
        "Space-separated IPs/hostnames of the BunkerWeb worker hosts this ${INSTALL_TYPE} controls."
    BUNKERWEB_INSTANCES_INPUT=$(tui_input "Worker Instances" \
        "Worker IPs/hostnames (space-separated, leave empty to add later):" "") \
        || BUNKERWEB_INSTANCES_INPUT=""
}

# Manager IP(s) for a worker — required (the worker whitelists them).
_docker_ask_manager_ip() {
    [ -n "$MANAGER_IP_INPUT" ] && return 0
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        print_error "--manager-ip is required for a non-interactive --docker worker install."
        exit 1
    fi
    tui_section "🛡️  Manager API Access" \
        "IP(s) of the manager/scheduler allowed to push configuration to this worker."
    while true; do
        MANAGER_IP_INPUT=$(tui_input "Manager IP" \
            "Manager IP address(es) (space-separated):" "") \
            || MANAGER_IP_INPUT=""
        [ -n "$MANAGER_IP_INPUT" ] && break
        tui_msgbox "Manager IP Required" "A worker must know the IP of its manager."
    done
}

# External DATABASE_URI — scheduler/ui/api (they share one database).
_docker_ask_database_uri() {
    [ -n "$DOCKER_DATABASE_URI" ] && return 0
    if [ "$INTERACTIVE_MODE" != "yes" ]; then
        print_error "--database-uri is required for a non-interactive --docker ${INSTALL_TYPE} install."
        exit 1
    fi
    tui_section "🗄️  Shared Database" \
        "This ${INSTALL_TYPE} container connects to the database shared by the rest of the deployment."
    while true; do
        DOCKER_DATABASE_URI=$(tui_input "Database URI" \
            "DATABASE_URI of the shared database (e.g. mariadb+pymysql://bunkerweb:pass@10.0.0.5:3306/db):" "") \
            || DOCKER_DATABASE_URI=""
        if [ -z "$DOCKER_DATABASE_URI" ]; then
            tui_msgbox "URI Required" "A DATABASE_URI is mandatory for this type."
            continue
        fi
        validate_docker_env_value "$DOCKER_DATABASE_URI" && break
        tui_msgbox "Invalid URI" "The URI must not contain '\$', a single quote or a backslash (avoid those in the DB password)."
        DOCKER_DATABASE_URI=""
    done
}

# FastAPI admin credentials — api type.
_docker_ask_api_creds() {
    if [ -z "$API_USERNAME_INPUT" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            tui_section "👤 FastAPI Admin Account"
            while true; do
                API_USERNAME_INPUT=$(tui_input "API Username" \
                    "Username for the FastAPI admin:" "admin") || API_USERNAME_INPUT="admin"
                [ -z "$API_USERNAME_INPUT" ] && API_USERNAME_INPUT="admin"
                validate_ui_admin_username "$API_USERNAME_INPUT" \
                    && validate_docker_env_value "$API_USERNAME_INPUT" && break
                tui_msgbox "Invalid Username" "Use letters, digits, '.', '_' and '-' (1–64 chars)."
                API_USERNAME_INPUT=""
            done
        else
            API_USERNAME_INPUT="admin"
        fi
    fi
    if [ -z "$API_PASSWORD_INPUT" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            while true; do
                API_PASSWORD_INPUT=$(tui_password "API Password" \
                    "FastAPI admin password (leave empty to auto-generate):") \
                    || API_PASSWORD_INPUT=""
                if [ -z "$API_PASSWORD_INPUT" ]; then
                    API_PASSWORD_INPUT=$(generate_ui_admin_password)
                    break
                fi
                if validate_ui_admin_password "$API_PASSWORD_INPUT" \
                    && validate_docker_env_value "$API_PASSWORD_INPUT"; then
                    break
                fi
                tui_msgbox "Invalid Password" "Need 8+ chars with a lowercase, uppercase, digit and special character — and no '\$', single quote or backslash."
                API_PASSWORD_INPUT=""
            done
        else
            API_PASSWORD_INPUT=$(generate_ui_admin_password)
        fi
    fi
}

# Pre-load secrets from an existing .env so a re-run keeps the values tied to
# persistent state (the MariaDB password baked into the bw-data volume, the
# TOTP key that decrypts stored 2FA secrets, the Flask session secret, ...)
# instead of rotating them. Only fills globals that are still empty — an
# explicit CLI flag always wins.
_docker_load_existing_env() {
    [ -f "$DOCKER_ENV_FILE" ] || return 0
    local _loaded="no" _pair _k _v
    while IFS= read -r _pair || [ -n "$_pair" ]; do
        case "$_pair" in ''|'#'*) continue ;; esac
        _k=${_pair%%=*}
        _v=${_pair#*=}
        case "$_k" in
            MARIADB_PASSWORD)     [ -z "$DOCKER_DB_PASSWORD_GENERATED" ]  && { DOCKER_DB_PASSWORD_GENERATED="$_v";  _loaded="yes"; } ;;
            TOTP_ENCRYPTION_KEYS) [ -z "$DOCKER_TOTP_KEY_GENERATED" ]     && { DOCKER_TOTP_KEY_GENERATED="$_v";     _loaded="yes"; } ;;
            FLASK_SECRET)         [ -z "$DOCKER_FLASK_SECRET_GENERATED" ] && { DOCKER_FLASK_SECRET_GENERATED="$_v"; _loaded="yes"; } ;;
            API_TOKEN)            [ -z "$DOCKER_API_TOKEN_GENERATED" ]    && { DOCKER_API_TOKEN_GENERATED="$_v";    _loaded="yes"; } ;;
            ADMIN_USERNAME)       [ -z "$UI_ADMIN_USERNAME_INPUT" ]       && { UI_ADMIN_USERNAME_INPUT="$_v";       _loaded="yes"; } ;;
            ADMIN_PASSWORD)       [ -z "$UI_ADMIN_PASSWORD_INPUT" ]       && { UI_ADMIN_PASSWORD_INPUT="$_v";       _loaded="yes"; } ;;
            API_USERNAME)         [ -z "$API_USERNAME_INPUT" ]           && { API_USERNAME_INPUT="$_v";            _loaded="yes"; } ;;
            API_PASSWORD)         [ -z "$API_PASSWORD_INPUT" ]           && { API_PASSWORD_INPUT="$_v";            _loaded="yes"; } ;;
            DATABASE_URI)         [ -z "$DOCKER_DATABASE_URI" ]          && { DOCKER_DATABASE_URI="$_v";           _loaded="yes"; } ;;
        esac
    done < "$DOCKER_ENV_FILE"
    if [ "$_loaded" = "yes" ]; then
        print_warning "Reusing existing secrets from $DOCKER_ENV_FILE so a re-run keeps the DB/UI/2FA values that persisted data depends on."
        print_warning "Delete that file first if you intend to rotate them."
    fi
    return 0
}

# Collect every Docker-mode setting: install type, image tag, autoconf variant,
# per-type credentials / remote IPs / shared secrets. Called by
# docker_install_flow() for both interactive and non-interactive (--yes) runs.
ask_docker_preferences() {
    # Compose directory — current working directory unless --compose-dir set it.
    if [ -z "$DOCKER_PROJECT_DIR" ]; then
        DOCKER_PROJECT_DIR=$(pwd -P)
    else
        # --compose-dir: create if missing, then resolve to an absolute path.
        mkdir -p "$DOCKER_PROJECT_DIR" 2>/dev/null || {
            print_error "Cannot create compose directory: $DOCKER_PROJECT_DIR"
            exit 1
        }
        DOCKER_PROJECT_DIR=$(cd "$DOCKER_PROJECT_DIR" 2>/dev/null && pwd -P) || {
            print_error "Compose directory is not accessible: $DOCKER_PROJECT_DIR"
            exit 1
        }
    fi
    DOCKER_COMPOSE_FILE="$DOCKER_PROJECT_DIR/docker-compose.yml"
    DOCKER_ENV_FILE="$DOCKER_PROJECT_DIR/.env"
    if [ "$DOCKER_PROJECT_DIR" = "/root" ]; then
        print_warning "Compose files will be written to /root — consider re-running from a dedicated directory (e.g. --compose-dir /opt/bunkerweb-docker)."
    fi

    # Re-run idempotency — adopt secrets from an existing .env before prompting.
    _docker_load_existing_env

    # Install type — picked by the shared install-type menu in
    # ask_user_preferences (interactive) or a --full/--manager/... flag;
    # defaults to full for a non-interactive run with no type flag.
    [ -z "$INSTALL_TYPE" ] && INSTALL_TYPE="full"
    case "$INSTALL_TYPE" in
        full|manager|worker|scheduler|ui|api) : ;;
        *) print_error "Unsupported install type for Docker mode: '$INSTALL_TYPE'."; exit 1 ;;
    esac

    _docker_ask_image_tag

    # Autoconf integration — only meaningful for the full stack.
    if [ "$INSTALL_TYPE" = "full" ]; then
        if [ -z "$DOCKER_AUTOCONF" ]; then
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                tui_section "🐳 Docker Autoconf Integration" \
                    "Autoconf configures BunkerWeb automatically from labels on your other containers."
                if tui_yesno "Autoconf Integration" \
                    "Enable the autoconf integration? (adds bw-autoconf + a Docker socket proxy)" "no"; then
                    DOCKER_AUTOCONF="yes"
                else
                    DOCKER_AUTOCONF="no"
                fi
            else
                DOCKER_AUTOCONF="no"
            fi
        fi
    else
        if [ "$DOCKER_AUTOCONF" = "yes" ]; then
            print_warning "--autoconf only applies to the full stack; ignoring it for the '$INSTALL_TYPE' type."
        fi
        DOCKER_AUTOCONF="no"
    fi

    # Per-type input collection.
    case "$INSTALL_TYPE" in
        full)
            _docker_ask_admin
            _docker_ask_db_password
            ;;
        manager)
            _docker_ask_instances
            _docker_ask_admin
            _docker_ask_db_password
            _docker_ask_shared_token
            ;;
        worker)
            _docker_ask_manager_ip
            _docker_ask_shared_token
            ;;
        scheduler)
            _docker_ask_instances
            _docker_ask_database_uri
            _docker_ask_shared_token
            ;;
        ui)
            _docker_ask_admin
            _docker_ask_database_uri
            ;;
        api)
            _docker_ask_api_creds
            _docker_ask_database_uri
            ;;
    esac

    # Validate flag-provided values that may have skipped the interactive guards.
    if ! validate_docker_image_tag "$DOCKER_IMAGE_TAG"; then
        print_error "Invalid image tag '$DOCKER_IMAGE_TAG' (letters/digits/'.'/'_'/'-', first char alphanumeric or '_')."
        exit 1
    fi
    if [ -n "$UI_ADMIN_USERNAME_INPUT" ] && ! validate_ui_admin_username "$UI_ADMIN_USERNAME_INPUT"; then
        print_error "Invalid admin username '$UI_ADMIN_USERNAME_INPUT'."
        exit 1
    fi
    # Every operator-supplied string that lands in the .env file must be safe.
    local _v
    for _v in "$UI_ADMIN_PASSWORD_INPUT" "$DOCKER_DB_PASSWORD_GENERATED" \
              "$DOCKER_API_TOKEN_GENERATED" "$DOCKER_DATABASE_URI" \
              "$API_USERNAME_INPUT" "$API_PASSWORD_INPUT" \
              "$BUNKERWEB_INSTANCES_INPUT" "$MANAGER_IP_INPUT"; do
        if [ -n "$_v" ] && ! validate_docker_env_value "$_v"; then
            print_error "A supplied value contains a '\$', single quote or backslash, which the Docker .env file cannot carry safely."
            exit 1
        fi
    done

    # Infrastructure secrets — generated only for the types that need them, and
    # only when still empty (a value reused from an existing .env via
    # _docker_load_existing_env is kept, so a re-run does not rotate it).
    case "$INSTALL_TYPE" in
        full|manager|ui)
            [ -z "$DOCKER_TOTP_KEY_GENERATED" ] && DOCKER_TOTP_KEY_GENERATED=$(generate_secret 64)
            [ -z "$DOCKER_FLASK_SECRET_GENERATED" ] && DOCKER_FLASK_SECRET_GENERATED=$(generate_secret 48)
            ;;
    esac
    # API_TOKEN: full generates its own (single host); manager/worker/scheduler
    # already have the operator-provided shared token; ui/api do not use one.
    if [ "$INSTALL_TYPE" = "full" ] && [ -z "$DOCKER_API_TOKEN_GENERATED" ]; then
        DOCKER_API_TOKEN_GENERATED=$(generate_secret 48)
    fi
}

# Step 0 of the install — choose the deployment platform (Linux host packages
# vs Docker compose stack) BEFORE any host-capability gate, so a distro that is
# unsupported for host packages can still be used for a Docker deployment.
ask_deployment_platform() {
    [ "$DOCKER_MODE" = "yes" ] && return 0          # --docker already chose it
    [ "$INTERACTIVE_MODE" != "yes" ] && return 0    # non-interactive: --docker, else Linux
    local _platform=""
    echo
    print_step "Deployment Platform"
    echo
    tui_section "🚀 Deployment Platform" "Choose how BunkerWeb will run on this host."
    _platform=$(tui_menu "Deployment Platform" \
        "How do you want to deploy BunkerWeb?" \
        "linux" \
        "linux"  "Linux — install BunkerWeb as host packages (systemd services)" \
        "docker" "Docker — generate a docker-compose stack and run containers") \
        || { print_error "Installation cancelled."; exit 1; }
    if [ "$_platform" = "docker" ]; then DOCKER_MODE="yes"; fi
}

ask_user_preferences() {
    # Docker mode — same step sequence as the Linux path: installation type,
    # per-type configuration, then the shared configuration recap. The stack is
    # generated/started later by docker_install_flow(), after the confirm
    # screen, mirroring how the Linux phases run after the same confirm.
    if [ "$DOCKER_MODE" = "yes" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            echo
            print_step "Configuration Options"
            echo
            if [ -z "$INSTALL_TYPE" ]; then
                tui_section "📦 Installation Type" "Choose the type of installation based on your needs."
                INSTALL_TYPE=$(tui_menu "Installation Type" \
                    "Choose the type of installation based on your needs:" \
                    "full" \
                    "full"      "Full Stack (default) — BunkerWeb + Scheduler + UI" \
                    "manager"   "Manager — Scheduler and UI to manage remote workers" \
                    "worker"    "Worker — only the BunkerWeb instance, managed remotely" \
                    "scheduler" "Scheduler only" \
                    "ui"        "Web UI only" \
                    "api"       "API service only") || { print_error "Installation cancelled."; exit 1; }
            fi
        fi
        ask_docker_preferences
        [ "$INTERACTIVE_MODE" = "yes" ] && present_configuration_summary
        return 0
    fi

    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        echo
        print_step "Configuration Options"
        echo

        # Ask about installation type (Linux platform).
        if [ -z "$INSTALL_TYPE" ]; then
            tui_section "📦 Installation Type" "Choose the type of installation based on your needs."
            INSTALL_TYPE=$(tui_menu "Installation Type" \
                "Choose the type of installation based on your needs:" \
                "full" \
                "full"      "Full Stack (default) — BunkerWeb + Scheduler + UI" \
                "manager"   "Manager — Scheduler and UI to manage remote workers" \
                "worker"    "Worker — only the BunkerWeb instance, managed remotely" \
                "scheduler" "Scheduler only" \
                "ui"        "Web UI only" \
                "api"       "API service only") || { print_error "Installation cancelled."; exit 1; }
        fi

        if [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]]; then
            if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                tui_section "🔗 BunkerWeb Instances Configuration"
                BUNKERWEB_INSTANCES_INPUT=$(tui_input "BunkerWeb Instances" \
                    "Space-separated list of BunkerWeb workers (IPs or hostnames).\nExample: 192.168.1.10 192.168.1.11\nLeave empty to add workers later." \
                    "") || BUNKERWEB_INSTANCES_INPUT=""
                if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                    print_warning "No instances configured. You can add workers later."
                    print_status "See: https://docs.bunkerweb.io/latest/advanced/#3-manage-workers"
                fi
            fi
        fi

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            local detected_ip=""
            tui_section "🌐 Manager API Binding" \
                "The manager listens on 0.0.0.0 but only whitelists explicit local IPs."
            detected_ip=$(get_primary_ipv4)
            if [ -n "$detected_ip" ]; then
                if tui_yesno "Manager API Binding" \
                    "Whitelist detected IP $detected_ip for API access?" "yes"; then
                    MANAGER_IP_INPUT="$detected_ip"
                else
                    tui_section "✍️  Manual Manager IP Entry"
                    prompt_for_local_ipv4 MANAGER_IP_INPUT || {
                        print_error "Manager IP is required."; exit 1; }
                fi
            else
                print_warning "Unable to detect a local IPv4 automatically."
                tui_section "✍️  Manual Manager IP Entry"
                prompt_for_local_ipv4 MANAGER_IP_INPUT || {
                    print_error "Manager IP is required."; exit 1; }
            fi
        fi

        if [ "$INSTALL_TYPE" = "worker" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            tui_section "🛡️  Manager API Access" \
                "Provide the IP(s) of the manager/scheduler that controls this worker."
            while true; do
                MANAGER_IP_INPUT=$(tui_input "Manager API Access" \
                    "Enter manager IP address(es) (space-separated):" "") || {
                    print_error "Manager IP is required for worker installs."; exit 1; }
                if [ -n "$MANAGER_IP_INPUT" ]; then
                    break
                fi
                tui_msgbox "Manager API Access" \
                    "This field cannot be empty for Worker installations."
            done
        fi

        # Ask about custom DNS resolvers for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$DNS_RESOLVERS_INPUT" ]; then
            tui_section "🔍 DNS Resolvers Configuration" \
                "Default: 9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4 (Quad9 and Google DNS)"
            if tui_yesno "DNS Resolvers" "Use custom DNS resolvers?" "no"; then
                while true; do
                    DNS_RESOLVERS_INPUT=$(tui_input "DNS Resolvers" \
                        "Space-separated DNS resolver IPs:" "") || DNS_RESOLVERS_INPUT=""
                    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
                        break
                    fi
                    tui_msgbox "DNS Resolvers" \
                        "DNS resolvers cannot be empty. Please enter at least one resolver."
                done
            else
                DNS_RESOLVERS_INPUT="9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4"
            fi
        fi

        # Ask about internal API HTTPS communication for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$API_LISTEN_HTTPS_INPUT" ]; then
            tui_section "🔒 Internal API HTTPS Communication" \
                "Scheduler/manager can talk to workers over HTTPS instead of HTTP. Default: HTTP."
            if tui_yesno "Internal API HTTPS" \
                "Enable HTTPS for internal API communication?" "no"; then
                API_LISTEN_HTTPS_INPUT="yes"
            else
                API_LISTEN_HTTPS_INPUT="no"
            fi
        fi

        # Ask about setup wizard
        if [ "$INSTALL_TYPE" = "manager" ]; then
            if [ "$ENABLE_WIZARD" = "yes" ]; then
                tui_msgbox "Setup Wizard Not Available" \
                    "Manager installations are not compatible with the setup wizard; it will be disabled. The UI can still be started normally."
            fi
            ENABLE_WIZARD="no"
        elif [ -z "$ENABLE_WIZARD" ]; then
            if [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "scheduler" ] || [ "$INSTALL_TYPE" = "api" ]; then
                ENABLE_WIZARD="no"
            else
                tui_section "🧙 BunkerWeb Setup Wizard" \
                    "Web-based interface to complete initial configuration and access management."
                _tui_explain "The BunkerWeb setup wizard provides a web-based interface to:
  • Complete initial configuration easily
  • Set up your first protected service
  • Configure SSL/TLS certificates
  • Access the management interface"
                if tui_yesno "BunkerWeb Setup Wizard" \
                    "🧙 Enable the setup wizard?" "yes"; then
                    ENABLE_WIZARD="yes"
                else
                    ENABLE_WIZARD="no"
                fi
            fi
        fi

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$SERVICE_UI" ]; then
            tui_section "🖥  Manager Web UI" \
                "Wizard is disabled in manager mode, but the Web UI service can still run."
            if tui_yesno "Manager Web UI" \
                "Start the Web UI service after installation?" "yes"; then
                export SERVICE_UI="yes"
            else
                export SERVICE_UI="no"
            fi
        fi

        # UI admin prompt: wizard ON → default No (wizard collects); wizard OFF → default Yes (otherwise no login).
        # Manager forces wizard OFF earlier → defaults Yes.
        local _ui_admin_eligible="no"
        if [ "$INSTALL_TYPE" = "manager" ] && [ "${SERVICE_UI:-yes}" != "no" ]; then
            _ui_admin_eligible="yes"
        elif [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "ui" || -z "$INSTALL_TYPE" ]]; then
            _ui_admin_eligible="yes"
        fi

        if [ "$_ui_admin_eligible" = "yes" ] && [ -z "$UI_ADMIN_CREATE" ]; then
            tui_section "👤 Web UI Admin User"
            # Long explanation in its own box (gum confirm crops at one term width); keep tui_yesno short.
            local _admin_q _admin_default _admin_body
            if [ "$INSTALL_TYPE" = "manager" ]; then
                _admin_body="The setup wizard is disabled in manager mode.
The installer can create the first admin user now and write
the credentials into /etc/bunkerweb/ui.env.

Note: the Web UI listens on 127.0.0.1:7000 by default —
keep it behind a reverse proxy or SSH tunnel for remote access."
                _admin_q="👤 Create the Web UI admin user now?"
                _admin_default="yes"
            elif [ "$ENABLE_WIZARD" = "yes" ]; then
                _admin_body="The setup wizard is enabled and will collect an admin user
on first boot of the Web UI.

You can also pre-create the admin user here — doing so
SKIPS the wizard's admin step and lands the credentials
directly in /etc/bunkerweb/ui.env."
                _admin_q="👤 Pre-create the Web UI admin user now (skip the wizard's admin step)?"
                _admin_default="no"
            else
                _admin_body="You disabled the setup wizard.
The installer can create the first admin user now and
write the credentials into /etc/bunkerweb/ui.env so the
UI is usable on first boot."
                _admin_q="👤 Create the Web UI admin user now?"
                _admin_default="yes"
            fi
            _tui_explain "$_admin_body"
            if tui_yesno "Web UI Admin User" "$_admin_q" "$_admin_default"; then
                UI_ADMIN_CREATE="yes"
            else
                UI_ADMIN_CREATE="no"
            fi

            if [ "$UI_ADMIN_CREATE" = "yes" ]; then
                if [ -z "$UI_ADMIN_USERNAME_INPUT" ]; then
                    local _admin_user_in
                    while true; do
                        _admin_user_in=$(tui_input "Web UI Admin User" \
                            "Username (letters, digits, '.', '_', '-'; max 64 chars):" "admin") \
                            || _admin_user_in="admin"
                        _admin_user_in=${_admin_user_in:-admin}
                        if validate_ui_admin_username "$_admin_user_in"; then
                            UI_ADMIN_USERNAME_INPUT="$_admin_user_in"
                            break
                        fi
                        tui_msgbox "Web UI Admin User" \
                            "Invalid username. Allowed: letters, digits, '.', '_', '-' (1..64 chars)."
                    done
                fi

                if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
                    local _pw_rc _pw_confirm
                    _tui_explain "Password rules:
  • 8+ characters
  • at least one lowercase, one uppercase, one digit, one special
Leave empty to auto-generate a strong random password."
                    while true; do
                        UI_ADMIN_PASSWORD_INPUT=$(tui_password "Web UI Admin Password" \
                            "🔑 Enter password (or leave empty to auto-generate):")
                        _pw_rc=$?
                        if [ "$_pw_rc" -ne 0 ]; then
                            # ESC/Cancel: don't silently coerce to auto-generate; ask explicitly.
                            UI_ADMIN_PASSWORD_INPUT=""
                            if tui_yesno "Web UI Admin Password" \
                                "Cancel password entry and auto-generate a random one instead?" "yes"; then
                                break
                            fi
                            continue
                        fi
                        if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
                            # Empty → auto-generate.
                            break
                        fi
                        if ! validate_ui_admin_password "$UI_ADMIN_PASSWORD_INPUT"; then
                            tui_msgbox "Web UI Admin Password" \
                                "Password does not meet the rules. Try again, or leave empty to auto-generate."
                            UI_ADMIN_PASSWORD_INPUT=""
                            continue
                        fi
                        _pw_confirm=$(tui_password "Web UI Admin Password (confirm)" \
                            "Re-type the password:") || _pw_confirm=""
                        if [ "$UI_ADMIN_PASSWORD_INPUT" != "$_pw_confirm" ]; then
                            tui_msgbox "Web UI Admin Password" \
                                "Passwords don't match. Try again."
                            UI_ADMIN_PASSWORD_INPUT=""
                            continue
                        fi
                        break
                    done
                fi
            fi
        fi

        # Manager-mode UI hardening: opt-in self-signed HTTPS.
        if [ "$INSTALL_TYPE" = "manager" ] && [ "${SERVICE_UI:-yes}" != "no" ] && [ -z "$UI_SELFSIGNED_INPUT" ]; then
            tui_section "🔒 Manager Web UI HTTPS (self-signed)"
            _tui_explain "Enable HTTPS on the local Web UI listener with a self-signed certificate.
This is gunicorn-native TLS — no BunkerWeb in front needed.

  Cert: /var/lib/bunkerweb/ui-tls/cert.pem
  Key:  /var/lib/bunkerweb/ui-tls/key.pem
  CN:   \$(hostname -f)
  Validity: 365 days   RSA 2048"
            if tui_yesno "Web UI Self-signed HTTPS" \
                "🔒 Enable self-signed HTTPS on the Web UI listener?" "yes"; then
                UI_SELFSIGNED_INPUT="yes"
            else
                UI_SELFSIGNED_INPUT="no"
            fi
        fi

        # Ask about CrowdSec installation
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "api" ]]; then
            if [ -z "$CROWDSEC_INSTALL" ] || [ "$CROWDSEC_INSTALL" = "no" ]; then
                tui_section "🦙 CrowdSec Intrusion Prevention"
                _tui_explain "CrowdSec is a community-powered, open-source intrusion prevention
engine that analyses logs in real time to detect, block, and share
intelligence on malicious IPs. It integrates with BunkerWeb for
automated threat remediation."
                if tui_yesno "CrowdSec" \
                    "🦙 Install and configure CrowdSec?" "yes"; then
                    CROWDSEC_INSTALL="yes"
                else
                    CROWDSEC_INSTALL="no"
                fi
            fi
        else
            # N/A for manager/worker/scheduler/ui-only/api-only.
            CROWDSEC_INSTALL="no"
        fi

        # API service prompt (skipped for worker/scheduler/ui-only/api-only).
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "api" ]] && [ -z "$SERVICE_API" ]; then
            tui_section "🧩 BunkerWeb API Service"
            _tui_explain "The BunkerWeb API provides a programmatic interface (FastAPI) to
manage instances, perform actions (reload/stop), and integrate with
external systems. Optional, disabled by default on Linux."
            if tui_yesno "BunkerWeb API Service" \
                "🧩 Enable the API service?" "no"; then
                SERVICE_API=yes
            else
                SERVICE_API=no
            fi
        elif [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
            SERVICE_API=no
        fi

        # AppSec — only if CrowdSec is chosen.
        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            tui_section "🛡️ CrowdSec Application Security (AppSec)"
            _tui_explain "The CrowdSec Application Security Component (AppSec) adds advanced
application security, turning CrowdSec into a full WAF. Optional,
installs alongside CrowdSec, and integrates seamlessly with the engine."
            if tui_yesno "CrowdSec AppSec" \
                "🛡️  Install and configure the AppSec Component?" "yes"; then
                CROWDSEC_APPSEC_INSTALL="yes"
            else
                CROWDSEC_APPSEC_INSTALL="no"
            fi
        fi

        # Ask about Redis configuration
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || -z "$INSTALL_TYPE" ]]; then
            if [ -z "$REDIS_INSTALL" ] || [ "$REDIS_INSTALL" = "no" ]; then
                tui_section "🧠 Redis (HA persistence + worker sync)"
                _tui_explain "Redis/Valkey makes BunkerWeb production-ready:
  • Persists metrics and bans across restarts
  • Synchronises bans/reports between workers in HA setups
  • Stores UI session data so users survive a UI restart

Without Redis this state is lost on restart and not shared between
instances. For HA, Redis Sentinel can also be used for automatic
failover. You can install Redis locally or point to an existing server."
                if tui_yesno "Redis Integration" \
                    "🧠 Enable Redis integration?" "no"; then
                    REDIS_INSTALL="yes"
                else
                    REDIS_INSTALL="no"
                fi
            fi

            if [ "$REDIS_INSTALL" = "yes" ]; then
                tui_section "🗄️  Redis Instance"
                if tui_yesno "Redis Instance" \
                    "Install Redis locally on this host?\n(Choose No to connect to an existing Redis server.)" "yes"; then
                    REDIS_INSTALL="yes"
                else
                    REDIS_INSTALL="no"
                fi

                # Local install: pick redis or valkey (wire-compatible).
                if [ "$REDIS_INSTALL" = "yes" ] && [ -z "$REDIS_FLAVOR" ]; then
                    tui_section "🔀 Server: Redis or Valkey"
                    REDIS_FLAVOR=$(tui_menu "Redis or Valkey" \
"Both speak the same wire protocol — BunkerWeb works with either.
If the chosen package is missing from your distro repos, the installer \
will warn and fall back to the other one." \
                        "redis" \
                        "redis"  "redis  (widest distro coverage; default)" \
                        "valkey" "valkey (open-source fork under the Linux Foundation)") || REDIS_FLAVOR="redis"
                fi

                # Manager: pick Redis bind interface for workers; full stack stays on 127.0.0.1.
                if [ "$REDIS_INSTALL" = "yes" ] && [ "$INSTALL_TYPE" = "manager" ] && [ -z "$REDIS_BIND_INPUT" ]; then
                    tui_section "🌐 Redis Bind Address"
                    REDIS_BIND_INPUT=$(tui_input "Redis Bind Address" \
"Workers connect to this Redis from the network.
  • 0.0.0.0     — accept on every interface (HA default; needs firewall + password)
  • 10.x.y.z    — pin to a specific private interface (recommended for VPC/LAN)
  • 127.0.0.1   — local only; workers will NOT reach it" \
                        "0.0.0.0") || REDIS_BIND_INPUT="0.0.0.0"
                    REDIS_BIND_INPUT=${REDIS_BIND_INPUT:-0.0.0.0}

                    if [ "$REDIS_BIND_INPUT" = "0.0.0.0" ]; then
                        print_warning "Redis will accept connections from every network interface."
                        print_warning "Strongly recommended: firewall port 6379 to your worker subnet, and set a Redis password."
                    fi

                fi

                # Local Redis password (REQUIREPASS): opt-in gate, then a
                # DB/UI-style prompt — type a password or leave empty to
                # auto-generate. Runs for every local install (full + manager).
                if [ "$REDIS_AUTOPASS" != "no" ] && [ -z "$REDIS_REQUIREPASS_LOCAL" ]; then
                    tui_section "🔑 Redis Password"
                    local _redis_flavor_label="${REDIS_FLAVOR:-redis}"
                    local _redis_pw_default="yes"
                    # Loopback-only Redis is unreachable from the network → password optional.
                    [ "${REDIS_BIND_INPUT:-127.0.0.1}" = "127.0.0.1" ] && _redis_pw_default="no"
                    _tui_explain "Protecting ${_redis_flavor_label} with a password (REQUIREPASS) is
strongly recommended whenever it is reachable from the network.
Leave the password empty to auto-generate a strong random one
(printed at the end of install)."
                    if tui_yesno "Redis Password" \
                        "🔑 Protect the local ${_redis_flavor_label} server with a password?" "$_redis_pw_default"; then
                        REDIS_AUTOPASS="yes"
                        local _redis_pw_rc _redis_pw_confirm
                        while true; do
                            REDIS_REQUIREPASS_LOCAL=$(tui_password "Redis Password" \
                                "🔑 Enter password (or leave empty to auto-generate):")
                            _redis_pw_rc=$?
                            if [ "$_redis_pw_rc" -ne 0 ]; then
                                # ESC/Cancel: don't silently coerce; ask explicitly.
                                REDIS_REQUIREPASS_LOCAL=""
                                if tui_yesno "Redis Password" \
                                    "Cancel password entry and auto-generate a random one instead?" "yes"; then
                                    break
                                fi
                                continue
                            fi
                            if [ -z "$REDIS_REQUIREPASS_LOCAL" ]; then
                                # Empty → auto-generate after the loop.
                                break
                            fi
                            if ! validate_redis_password "$REDIS_REQUIREPASS_LOCAL"; then
                                tui_msgbox "Redis Password" \
                                    "Password must be 8+ characters with no whitespace, quotes, backslash, backtick or '#'. Try again, or leave empty to auto-generate."
                                REDIS_REQUIREPASS_LOCAL=""
                                continue
                            fi
                            _redis_pw_confirm=$(tui_password "Redis Password (confirm)" \
                                "Re-type the password:") || _redis_pw_confirm=""
                            if [ "$REDIS_REQUIREPASS_LOCAL" != "$_redis_pw_confirm" ]; then
                                tui_msgbox "Redis Password" "Passwords don't match. Try again."
                                REDIS_REQUIREPASS_LOCAL=""
                                continue
                            fi
                            break
                        done
                        # Empty after the loop → auto-generate now (works for loopback too).
                        if [ -z "$REDIS_REQUIREPASS_LOCAL" ]; then
                            REDIS_REQUIREPASS_LOCAL=$(generate_secret 32)
                            REDIS_PASSWORD_GENERATED="$REDIS_REQUIREPASS_LOCAL"
                        fi
                    else
                        REDIS_AUTOPASS="no"
                    fi
                fi

                # Memory cap (manager + full-stack). Default noeviction rejects writes when full;
                # bounded + volatile-lru evicts transient WAF counters, preserves bans/sessions.
                if [ "$REDIS_INSTALL" = "yes" ] && [ -z "$REDIS_MAXMEMORY_MB" ]; then
                    # Human-readable flavor label.
                    local _flavor_label
                    case "${REDIS_FLAVOR:-redis}" in
                        valkey) _flavor_label="Valkey" ;;
                        redis|*) _flavor_label="Redis" ;;
                    esac
                    tui_section "🧠 ${_flavor_label} Memory Cap"
                    local _mem_choice
                    _mem_choice=$(tui_menu "${_flavor_label} Memory Cap" \
"Without a cap, ${_flavor_label} grows until the kernel OOM-kills it.
The installer will apply maxmemory-policy=volatile-lru — evicts the least-recently-used \
keys with TTL first, preserving permanent bans and active sessions." \
                        "256" \
                        "128"        "128 MB    — small/dev VMs (≤ 2 GB RAM)" \
                        "256"        "256 MB    — recommended for most installs (4–8 GB)" \
                        "512"        "512 MB    — high-traffic / dedicated nodes (8 GB+)" \
                        "custom"     "Custom    — enter your own value in MB" \
                        "unlimited"  "Unlimited — keep distro defaults (NOT recommended)") \
                        || _mem_choice="256"
                    case "$_mem_choice" in
                        128|256|512) REDIS_MAXMEMORY_MB="$_mem_choice" ;;
                        custom)
                            while true; do
                                local _custom_mb
                                _custom_mb=$(tui_input "${_flavor_label} Memory Cap" \
                                    "Memory cap in MB (e.g. 1024):" "1024") || _custom_mb=""
                                if [[ "$_custom_mb" =~ ^[1-9][0-9]*$ ]]; then
                                    REDIS_MAXMEMORY_MB="$_custom_mb"
                                    break
                                fi
                                tui_msgbox "${_flavor_label} Memory Cap" \
                                    "Please enter a positive integer (MB)."
                            done
                            ;;
                        unlimited)
                            REDIS_MAXMEMORY_MB="0"
                            print_warning "Skipping memory cap — ${_flavor_label} may consume all system RAM under load."
                            ;;
                    esac
                fi

                if [ "$REDIS_INSTALL" = "no" ]; then
                    tui_section "✍️  Existing Redis Configuration" \
                        "Provide connection details for your existing Redis server."
                    REDIS_HOST_INPUT=$(tui_input "Existing Redis — Host" "Redis host:" "127.0.0.1") || REDIS_HOST_INPUT=""
                    REDIS_HOST_INPUT=${REDIS_HOST_INPUT:-127.0.0.1}
                    REDIS_PORT_INPUT=$(tui_input "Existing Redis — Port" "Redis port:" "6379") || REDIS_PORT_INPUT=""
                    REDIS_PORT_INPUT=${REDIS_PORT_INPUT:-6379}
                    REDIS_DATABASE_INPUT=$(tui_input "Existing Redis — Database" "Redis database number:" "0") || REDIS_DATABASE_INPUT=""
                    REDIS_DATABASE_INPUT=${REDIS_DATABASE_INPUT:-0}
                    REDIS_USERNAME_INPUT=$(tui_input "Existing Redis — Username" "Redis username (optional):" "") || REDIS_USERNAME_INPUT=""
                    # Distinguish ESC/Cancel from "no password" — accidental cancel must not silently empty REQUIREPASS.
                    while true; do
                        local _redis_pw_rc
                        REDIS_PASSWORD_INPUT=$(tui_password "Existing Redis — Password" \
                            "Redis password (leave empty if the server requires none):")
                        _redis_pw_rc=$?
                        if [ "$_redis_pw_rc" -ne 0 ]; then
                            REDIS_PASSWORD_INPUT=""
                            if tui_yesno "Existing Redis — Password" \
                                "Connect to the Redis server WITHOUT a password?" "no"; then
                                break
                            fi
                            continue
                        fi
                        break
                    done
                    if tui_yesno "Existing Redis — SSL" "Use SSL/TLS for Redis connection?" "no"; then
                        REDIS_SSL_INPUT="yes"
                    else
                        REDIS_SSL_INPUT="no"
                    fi
                    if [ "$REDIS_SSL_INPUT" = "yes" ]; then
                        if tui_yesno "Existing Redis — SSL Verify" \
                            "Verify Redis SSL certificate?" "yes"; then
                            REDIS_SSL_VERIFY_INPUT="yes"
                        else
                            REDIS_SSL_VERIFY_INPUT="no"
                        fi
                    fi
                fi
            fi
        else
            # Redis: full/manager only.
            REDIS_INSTALL="no"
        fi

        # Database auto-install (full + manager).
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || -z "$INSTALL_TYPE" ]]; then
            if [ -z "$DB_INSTALL" ]; then
                tui_section "🗄️  Database"
                DB_INSTALL=$(tui_menu "Database" \
"BunkerWeb stores configuration, services and jobs in a database.
SQLite is safe for single-node trials but not recommended for HA \
or any setup with more than one BunkerWeb instance.
Pick \"external\" to plug BunkerWeb into a remote database you already operate." \
                    "mariadb" \
                    "mariadb"    "MariaDB (local, recommended)" \
                    "postgresql" "PostgreSQL (local)" \
                    "external"   "Connect to an existing external database" \
                    "none"       "Skip (keep SQLite or set DATABASE_URI manually later)") \
                    || DB_INSTALL="mariadb"
            fi

            if [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; then
                if [ "$DB_INSTALL" = "mariadb" ] && [ "$DISTRO_ID" = "freebsd" ]; then
                    print_warning "MariaDB auto-install is not supported on FreeBSD by this installer."
                    print_warning "Falling back to SQLite — install MariaDB manually and set DATABASE_URI yourself."
                    DB_INSTALL="none"
                elif [ "$DB_INSTALL" = "postgresql" ] && [ "$DISTRO_ID" = "freebsd" ]; then
                    print_warning "PostgreSQL auto-install is not supported on FreeBSD by this installer."
                    print_warning "Falling back to SQLite — install PostgreSQL manually and set DATABASE_URI yourself."
                    DB_INSTALL="none"
                fi
            fi

            if [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; then
                local _db_answer
                tui_section "✍️  Database Configuration"
                while true; do
                    _db_answer=$(tui_input "Database — Name" \
                        "Database name (letters, digits, underscore; starts with letter or _):" \
                        "$DB_NAME_INPUT") || _db_answer=""
                    _db_answer=${_db_answer:-$DB_NAME_INPUT}
                    if validate_db_identifier "$_db_answer"; then
                        DB_NAME_INPUT="$_db_answer"
                        break
                    fi
                    tui_msgbox "Database — Name" "Invalid identifier. Use letters/digits/underscore only (max 63 chars)."
                done
                while true; do
                    _db_answer=$(tui_input "Database — User" \
                        "Database user (letters, digits, underscore; starts with letter or _):" \
                        "$DB_USER_INPUT") || _db_answer=""
                    _db_answer=${_db_answer:-$DB_USER_INPUT}
                    if validate_db_identifier "$_db_answer"; then
                        DB_USER_INPUT="$_db_answer"
                        break
                    fi
                    tui_msgbox "Database — User" "Invalid identifier. Use letters/digits/underscore only (max 63 chars)."
                done
                if [ -z "$DB_PASSWORD_INPUT" ]; then
                    # Same UX as UI admin: empty → auto-gen, else validate + confirm.
                    local _db_pw_rc _db_pw_confirm
                    _tui_explain "Database password rules:
  • 8+ characters
  • no quotes (' or \")
  • no backslash (\\)
  • no backtick (\`)
Leave empty to auto-generate a strong random password (printed at
the end of install)."
                    while true; do
                        DB_PASSWORD_INPUT=$(tui_password "Database — Password" \
                            "🔑 Enter password (or leave empty to auto-generate):")
                        _db_pw_rc=$?
                        if [ "$_db_pw_rc" -ne 0 ]; then
                            # ESC/Cancel: ask explicitly (same as admin prompt).
                            DB_PASSWORD_INPUT=""
                            if tui_yesno "Database — Password" \
                                "Cancel password entry and auto-generate a random one instead?" "yes"; then
                                break
                            fi
                            continue
                        fi
                        if [ -z "$DB_PASSWORD_INPUT" ]; then
                            # Empty → auto-gen in install_mariadb/install_postgresql.
                            break
                        fi
                        if ! validate_db_password "$DB_PASSWORD_INPUT"; then
                            tui_msgbox "Database — Password" \
                                "Password does not meet the rules. Try again, or leave empty to auto-generate."
                            DB_PASSWORD_INPUT=""
                            continue
                        fi
                        _db_pw_confirm=$(tui_password "Database — Password (confirm)" \
                            "Re-type the password:") || _db_pw_confirm=""
                        if [ "$DB_PASSWORD_INPUT" != "$_db_pw_confirm" ]; then
                            tui_msgbox "Database — Password" "Passwords don't match. Try again."
                            DB_PASSWORD_INPUT=""
                            continue
                        fi
                        break
                    done
                fi
            elif [ "$DB_INSTALL" = "external" ]; then
                tui_section "🌐 External Database"
                if [ -z "$DB_EXTERNAL_ENGINE" ]; then
                    DB_EXTERNAL_ENGINE=$(tui_menu "External Database — Engine" \
"Pick the engine that matches your existing server.
BunkerWeb supports MariaDB, MySQL and PostgreSQL." \
                        "mariadb" \
                        "mariadb"    "MariaDB (mariadb+pymysql)" \
                        "mysql"      "MySQL (mysql+pymysql)" \
                        "postgresql" "PostgreSQL (postgresql+psycopg)") \
                        || DB_EXTERNAL_ENGINE="mariadb"
                fi

                local _db_answer
                while true; do
                    _db_answer=$(tui_input "External Database — Host" \
                        "Database host (FQDN or IP):" "${DB_HOST_INPUT:-127.0.0.1}") || _db_answer=""
                    _db_answer=${_db_answer:-${DB_HOST_INPUT:-127.0.0.1}}
                    if validate_db_host "$_db_answer"; then
                        DB_HOST_INPUT="$_db_answer"
                        break
                    fi
                    tui_msgbox "External Database — Host" \
                        "Invalid hostname. Allowed: letters, digits, dot, hyphen, colon (IPv6), square brackets."
                done

                local _default_port
                _default_port=$(default_db_port "$DB_EXTERNAL_ENGINE")
                _db_answer=$(tui_input "External Database — Port" \
                    "Database port:" "${DB_PORT_INPUT:-$_default_port}") || _db_answer=""
                DB_PORT_INPUT=${_db_answer:-${DB_PORT_INPUT:-$_default_port}}
                if ! [[ "$DB_PORT_INPUT" =~ ^[1-9][0-9]{0,4}$ ]] || [ "$DB_PORT_INPUT" -gt 65535 ]; then
                    print_warning "Invalid port '${DB_PORT_INPUT}', falling back to default ${_default_port}."
                    DB_PORT_INPUT="$_default_port"
                fi

                while true; do
                    _db_answer=$(tui_input "External Database — Name" \
                        "Database name (must already exist):" "$DB_NAME_INPUT") || _db_answer=""
                    _db_answer=${_db_answer:-$DB_NAME_INPUT}
                    if validate_db_identifier "$_db_answer"; then
                        DB_NAME_INPUT="$_db_answer"
                        break
                    fi
                    tui_msgbox "External Database — Name" \
                        "Invalid identifier. Letters/digits/underscore only (starts with letter or _, max 63 chars)."
                done

                while true; do
                    _db_answer=$(tui_input "External Database — User" \
                        "Database user (must have privileges on the database above):" "$DB_USER_INPUT") || _db_answer=""
                    _db_answer=${_db_answer:-$DB_USER_INPUT}
                    if validate_db_identifier "$_db_answer"; then
                        DB_USER_INPUT="$_db_answer"
                        break
                    fi
                    tui_msgbox "External Database — User" \
                        "Invalid identifier. Letters/digits/underscore only (starts with letter or _, max 63 chars)."
                done

                if [ -z "$DB_PASSWORD_INPUT" ]; then
                    local _db_pw_confirm _db_pw_rc
                    _tui_explain "Password for the database user above.

Rules:
  • 8+ characters
  • no quotes (' or \")
  • no backslash (\\)
  • no backtick (\`)"
                    while true; do
                        DB_PASSWORD_INPUT=$(tui_password "External Database — Password" \
                            "🔑 Enter the database password:")
                        _db_pw_rc=$?
                        if [ "$_db_pw_rc" -ne 0 ]; then
                            DB_PASSWORD_INPUT=""
                            tui_msgbox "External Database — Password" \
                                "A password is required for an external database."
                            continue
                        fi
                        if ! validate_db_password "$DB_PASSWORD_INPUT"; then
                            tui_msgbox "External Database — Password" \
                                "Password does not meet the rules. Try again."
                            DB_PASSWORD_INPUT=""
                            continue
                        fi
                        _db_pw_confirm=$(tui_password "External Database — Password (confirm)" \
                            "Re-type the password:") || _db_pw_confirm=""
                        if [ "$DB_PASSWORD_INPUT" != "$_db_pw_confirm" ]; then
                            tui_msgbox "External Database — Password" \
                                "Passwords don't match. Try again."
                            DB_PASSWORD_INPUT=""
                            continue
                        fi
                        break
                    done
                fi

                if [ -z "$DB_SSL_INPUT" ]; then
                    if tui_yesno "External Database — SSL" \
                        "Use SSL/TLS for the database connection?" "no"; then
                        DB_SSL_INPUT="yes"
                    else
                        DB_SSL_INPUT="no"
                    fi
                fi
                if [ "$DB_SSL_INPUT" = "yes" ] && [ -z "$DB_SSL_VERIFY_INPUT" ]; then
                    if tui_yesno "External Database — SSL Verify" \
                        "Verify the database server certificate?" "yes"; then
                        DB_SSL_VERIFY_INPUT="yes"
                    else
                        DB_SSL_VERIFY_INPUT="no"
                    fi
                fi
            fi
        else
            DB_INSTALL="none"
        fi

        present_configuration_summary
    fi
}

# Build the config recap once and route it via the active TUI tier: gum
# panel/pager, whiptail msgbox, or plain stdout. Shared by the Linux and Docker
# preference flows so both show the same recap step before the confirm screen.
present_configuration_summary() {
    local _summary
    _summary=$(_build_configuration_summary)
    if [ "$GUM_AVAILABLE" = "yes" ]; then
        _present_summary_gum "$_summary"
    elif [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
        tui_msgbox "Configuration Summary" "$_summary"
    else
        echo
        print_status "Configuration summary:"
        echo "$_summary"
        echo
    fi
}

# Render summary via gum. Body text inherits terminal default for cross-theme contrast.
# Print inline (no pager): the recap is informational and scrolls in the normal
# buffer; the `gum confirm` that follows is the single interaction gate. A pager
# here would grab the alt screen and only exit on q/esc — on consoles where input
# never reaches bubbletea it hangs, and it reads as "stuck" even when it works.
_present_summary_gum() {
    local _summary="$1"
    local _term_w _box_w
    _term_w=$(tput cols  2>/dev/null || echo 80)
    _box_w=$(( _term_w > 84 ? 78 : _term_w - 6 ))
    [ "$_box_w" -lt 40 ] && _box_w=40

    local _title
    _title=$(gum style --bold --foreground "#2eac68" "Configuration Summary")
    local _styled
    _styled=$(gum style \
        --border rounded --padding "0 1" \
        --border-foreground "#2eac68" \
        --width "$_box_w" \
        --margin "1 0" \
        "$(printf '%s\n%s' "$_title" "$_summary")")

    printf '%s\n' "$_styled"
}

# Build config recap string with dot-padded fields. No I/O. UTF-8 glyphs safe — tui_init forces UTF-8.
_build_configuration_summary() {
    local out=""
    # Render a section divider: "── Section ──────────────────────"
    _section() {
        local title="$1" pad_len pad
        pad_len=$(( 70 - ${#title} - 4 ))
        [ "$pad_len" -lt 4 ] && pad_len=4
        pad=$(printf '%*s' "$pad_len" "")
        pad="${pad// /─}"
        out+=$'\n'"── ${title} ${pad}"$'\n'
    }
    # Aligned field: "  Label .......... Value"
    _field() {
        local label="$1" value="$2" pad_len pad
        pad_len=$(( 26 - ${#label} ))
        [ "$pad_len" -lt 2 ] && pad_len=2
        pad=$(printf '%*s' "$pad_len" "")
        pad="${pad// /.}"
        out+="  ${label} ${pad} ${value}"$'\n'
    }

    # Docker mode — its own recap (no host-package fields, never any secrets).
    if [ "$DOCKER_MODE" = "yes" ]; then
        _section "Core"
        _field "Deployment platform" "Docker (compose stack)"
        _field "Installation type"   "$INSTALL_TYPE"
        _field "Image tag"           "${DOCKER_IMAGE_TAG:-$(derive_docker_image_tag "$BUNKERWEB_VERSION")}"
        [ "$INSTALL_TYPE" = "full" ] && \
            _field "Autoconf integration" "$([ "$DOCKER_AUTOCONF" = "yes" ] && echo "Enabled" || echo "Disabled")"
        _field "Compose directory"   "${DOCKER_PROJECT_DIR:-$(pwd -P)}"

        _section "Topology"
        case "$INSTALL_TYPE" in
            full)      _field "Services" "bunkerweb, bw-scheduler, bw-ui, bw-db, redis"
                       [ "$DOCKER_AUTOCONF" = "yes" ] && _field "" "+ bw-autoconf, bw-docker"
                       _field "Database" "MariaDB (bundled bw-db)" ;;
            manager)   _field "Services" "bw-scheduler, bw-ui, bw-db, redis"
                       _field "Database" "MariaDB (bundled bw-db)"
                       _field "Worker instances" "${BUNKERWEB_INSTANCES_INPUT:-<none yet>}" ;;
            worker)    _field "Services" "bunkerweb (ports 80/443/5000)"
                       _field "Manager IP(s)" "${MANAGER_IP_INPUT}" ;;
            scheduler) _field "Services" "bw-scheduler, redis"
                       _field "Database" "external (DATABASE_URI)"
                       _field "Worker instances" "${BUNKERWEB_INSTANCES_INPUT:-<none yet>}" ;;
            ui)        _field "Services" "bw-ui (port 7000)"
                       _field "Database" "external (DATABASE_URI)" ;;
            api)       _field "Services" "bw-api (port 8888)"
                       _field "Database" "external (DATABASE_URI)" ;;
        esac

        _section "Credentials"
        case "$INSTALL_TYPE" in
            full|manager|ui) _field "Web UI admin user" "${UI_ADMIN_USERNAME_INPUT:-admin}" ;;
            api)             _field "FastAPI admin user" "${API_USERNAME_INPUT:-admin}" ;;
        esac
        _field "Secrets" "generated/collected — written only to the 0600 .env file"

        printf '%s' "$out"
        return 0
    fi

    # ── Core ──
    _section "Core"
    _field "BunkerWeb version" "$BUNKERWEB_VERSION"
    local _type_label
    case "$INSTALL_TYPE" in
        "full"|"") _type_label="Full Stack" ;;
        "manager")   _type_label="Manager" ;;
        "worker")    _type_label="Worker" ;;
        "scheduler") _type_label="Scheduler Only" ;;
        "ui")        _type_label="Web UI Only" ;;
        "api")       _type_label="API Only" ;;
    esac
    _field "Installation type" "$_type_label"
    _field "Operating system"  "$DISTRO_ID $DISTRO_VERSION"
    _field "Architecture"      "${SYSTEM_ARCH:-unknown}"
    _field "NGINX version"     "$NGINX_VERSION"

    # ── Networking ──
    if [ -n "$BUNKERWEB_INSTANCES_INPUT" ] \
        || [ -n "$MANAGER_IP_INPUT" ] \
        || [ -n "$DNS_RESOLVERS_INPUT" ] \
        || [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        _section "Networking"
        if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
            _field "BunkerWeb instances" "$BUNKERWEB_INSTANCES_INPUT"
        fi
        if [ -n "$MANAGER_IP_INPUT" ]; then
            _field "Internal Lua API whitelist" "$MANAGER_IP_INPUT"
        fi
        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
            _field "DNS resolvers" "$DNS_RESOLVERS_INPUT"
        fi
        if [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
            _field "Internal Lua API HTTPS" "Enabled"
        fi
    fi

    # ── Services ──
    _section "Services"
    # Wizard applies only to full/ui (mode running NGINX). Manager forces wizard off; worker/scheduler/api have no UI surface.
    case "${INSTALL_TYPE:-full}" in
        manager)
            _field "Web UI service" "$([ "${SERVICE_UI:-yes}" = "no" ] && echo "Disabled" || echo "Enabled")"
            _field "Setup wizard"   "Disabled (manager mode)"
            ;;
        full|ui|"")
            _field "Setup wizard" "$([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
            ;;
        worker|scheduler|api)
            _field "Setup wizard" "n/a (this mode)"
            ;;
    esac
    if [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" ]]; then
        _field "FastAPI service" "n/a (this mode)"
    elif [ "${SERVICE_API:-no}" = "yes" ] || [ "$INSTALL_TYPE" = "api" ]; then
        _field "FastAPI service" "Enabled (port 8888)"
    else
        _field "FastAPI service" "Disabled"
    fi

    # ── Security ──
    _section "Security"
    if [ "$INSTALL_TYPE" = "manager" ] || [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "api" ]; then
        _field "CrowdSec" "n/a (this mode)"
    elif [ "$CROWDSEC_INSTALL" = "yes" ]; then
        if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
            _field "CrowdSec" "Will install (with AppSec)"
        else
            _field "CrowdSec" "Will install (no AppSec)"
        fi
    else
        _field "CrowdSec" "Not installed"
    fi

    # ── Storage ──
    _section "Storage"
    if [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && -n "$INSTALL_TYPE" ]]; then
        _field "Database" "n/a (this mode)"
        _field "Redis"    "n/a (this mode)"
    else
        case "$DB_INSTALL" in
            "mariadb")    _field "Database" "MariaDB (local, db=${DB_NAME_INPUT}, user=${DB_USER_INPUT})" ;;
            "postgresql") _field "Database" "PostgreSQL (local, db=${DB_NAME_INPUT}, user=${DB_USER_INPUT})" ;;
            "external")
                local _engine_label="${DB_EXTERNAL_ENGINE:-mariadb}"
                local _ssl_label=""
                if [ "$DB_SSL_INPUT" = "yes" ]; then
                    if [ "$DB_SSL_VERIFY_INPUT" = "no" ]; then
                        _ssl_label=", SSL (no verify)"
                    else
                        _ssl_label=", SSL"
                    fi
                fi
                _field "Database" "${_engine_label} (external, ${DB_HOST_INPUT:-?}:${DB_PORT_INPUT:-?}/${DB_NAME_INPUT}${_ssl_label})"
                ;;
            ""|"none")    _field "Database" "SQLite (set DATABASE_URI later for production)" ;;
        esac
        if [ "$REDIS_INSTALL" = "yes" ]; then
            local _flavor_label
            case "${REDIS_FLAVOR:-redis}" in
                valkey) _flavor_label="Valkey" ;;
                redis|*) _flavor_label="Redis" ;;
            esac
            if [ "$INSTALL_TYPE" = "manager" ]; then
                _field "$_flavor_label" "Local, bind ${REDIS_BIND_INPUT:-0.0.0.0}"
            else
                _field "$_flavor_label" "Local, default config"
            fi
            # States: opted out / interactive auto-gen / interactive typed /
            # non-interactive auto-gen (bind ≠ loopback, settled at apply time).
            if [ "$REDIS_AUTOPASS" = "no" ]; then
                _field "Redis password" "None (REQUIREPASS not set)"
            elif [ -n "$REDIS_PASSWORD_GENERATED" ]; then
                _field "Redis password" "Auto-generated (REQUIREPASS)"
            elif [ -n "$REDIS_REQUIREPASS_LOCAL" ]; then
                _field "Redis password" "Set (provided)"
            elif [ "${REDIS_BIND_INPUT:-127.0.0.1}" != "127.0.0.1" ]; then
                _field "Redis password" "Auto-generated (REQUIREPASS)"
            fi
            if [ -n "$REDIS_MAXMEMORY_MB" ]; then
                if [ "$REDIS_MAXMEMORY_MB" = "0" ]; then
                    _field "Memory cap" "Unlimited (NOT recommended)"
                else
                    _field "Memory cap" "${REDIS_MAXMEMORY_MB} MB (${REDIS_MAXMEMORY_POLICY:-volatile-lru})"
                fi
            fi
        elif [ -n "$REDIS_HOST_INPUT" ]; then
            _field "Redis" "Existing — $REDIS_HOST_INPUT:${REDIS_PORT_INPUT:-6379}"
        else
            _field "Redis" "Not installed (in-memory only)"
        fi
    fi

    # ── Web UI ── always render when UI is in scope so "no" answers stay visible in the recap.
    local _ui_in_scope="no"
    case "$INSTALL_TYPE" in
        manager) [ "${SERVICE_UI:-yes}" != "no" ] && _ui_in_scope="yes" ;;
        full|ui|"") _ui_in_scope="yes" ;;
    esac
    if [ "$_ui_in_scope" = "yes" ]; then
        _section "Web UI"
        case "$UI_ADMIN_CREATE" in
            yes) _field "Admin user" "Will be created (${UI_ADMIN_USERNAME_INPUT:-admin})" ;;
            no)
                if [ "$ENABLE_WIZARD" = "yes" ]; then
                    _field "Admin user" "Wizard will collect on first boot"
                else
                    _field "Admin user" "Not pre-created — UI will be unloggable until you set ADMIN_USERNAME/PASSWORD in /etc/bunkerweb/ui.env"
                fi
                ;;
            *) _field "Admin user" "Not configured" ;;
        esac
        if [ "$INSTALL_TYPE" = "manager" ]; then
            case "$UI_SELFSIGNED_INPUT" in
                yes) _field "HTTPS" "Self-signed cert (gunicorn TLS)" ;;
                no)  _field "HTTPS" "Plain HTTP listener (127.0.0.1:7000)" ;;
                *)   _field "HTTPS" "Default (plain HTTP listener)" ;;
            esac
        fi
    fi

    # Strip leading/trailing newline (dialogs render empty lines otherwise).
    out="${out#$'\n'}"
    printf '%s' "${out%$'\n'}"
}

# RHEL database-client warning. Gated on INTERACTIVE_MODE — previously blocked unattended installs via `read`.
show_rhel_database_warning() {
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]]; then
        local msg="If you plan to use an external database (recommended for production), \
install the appropriate database client first:

  • MariaDB:    dnf install mariadb
  • MySQL:      dnf install mysql
  • PostgreSQL: dnf install postgresql

This is required for the BunkerWeb Scheduler to connect to your database."
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            tui_msgbox "RHEL-based systems — Database client" "$msg"
        else
            print_warning "Important information for RHEL-based systems:"
            echo
            echo "$msg"
            echo
            print_status "Continuing installation..."
        fi
    fi
}

check_supported_os() {
    case "$DISTRO_ID" in
        "freebsd")
            major_version=$(echo "$DISTRO_VERSION" | cut -d. -f1)
            if [[ "$major_version" != "13" && "$major_version" != "14" ]]; then
                print_warning "Only FreeBSD 13 and 14 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Unsupported OS" \
                        "Only FreeBSD 13 and 14 are officially supported (detected: $DISTRO_VERSION).\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.28.0"
            ;;
        "debian")
            if [[ "$DISTRO_VERSION" != "12" && "$DISTRO_VERSION" != "13" ]]; then
                print_warning "Only Debian 12 (Bookworm) and 13 (Trixie) are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Unsupported OS" \
                        "Only Debian 12 (Bookworm) and 13 (Trixie) are officially supported (detected: $DISTRO_VERSION).\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.2-1~$DISTRO_CODENAME"
            ;;
        "ubuntu")
            if [[ "$DISTRO_VERSION" != "22.04" && "$DISTRO_VERSION" != "24.04" ]]; then
                print_warning "Only Ubuntu 22.04 (Jammy) and 24.04 (Noble) are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Unsupported OS" \
                        "Only Ubuntu 22.04 (Jammy) and 24.04 (Noble) are officially supported (detected: $DISTRO_VERSION).\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.2-1~$DISTRO_CODENAME"
            ;;
        "fedora")
            if [[ "$DISTRO_VERSION" != "43" && "$DISTRO_VERSION" != "44" ]]; then
                print_warning "Only Fedora 43 and 44 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Unsupported OS" \
                        "Only Fedora 43 and 44 are officially supported (detected: $DISTRO_VERSION).\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.1"
            ;;
        "rhel"|"rocky"|"almalinux"|"centos")
            major_version=$(echo "$DISTRO_VERSION" | cut -d. -f1)
            if [[ "$major_version" != "8" && "$major_version" != "9" && "$major_version" != "10" ]]; then
                print_warning "Only RHEL, CentOS, Rocky Linux, and AlmaLinux 8, 9, and 10 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Unsupported OS" \
                        "Only RHEL, CentOS, Rocky Linux, and AlmaLinux 8, 9, and 10 are officially supported (detected: $DISTRO_VERSION).\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.2"
            ;;
        *)
            print_error "Unsupported operating system: $DISTRO_ID"
            print_error "Supported distributions: Debian 12/13, Ubuntu 22.04/24.04, Fedora 43/44, RHEL/CentOS/Rocky/AlmaLinux 8/9/10, FreeBSD 13/14"
            exit 1
            ;;
    esac
}

check_ports() {
    if [[ "$INSTALL_TYPE" == "full" || "$INSTALL_TYPE" == "worker" || "$DOCKER_MODE" == "yes" || -z "$INSTALL_TYPE" ]]; then
        if command -v ss >/dev/null 2>&1; then
            local _pc_rows
            _pc_rows=$(ss -tulpn 2>/dev/null | awk '/:(80|443) /{print}' | head -3)
            if [ -n "$_pc_rows" ]; then
                print_warning "Port 80 or 443 already bound. Common conflict: Apache (httpd) or another reverse proxy."
                printf '%s\n' "$_pc_rows" | sed 's/^/  /'
                print_warning "Identify it with: ss -tulpn 'sport = :80 or sport = :443'  (or: lsof -i :80 -i :443)"
                print_warning "Stop the conflicting service before proceeding."
                if [ "$INTERACTIVE_MODE" = "yes" ]; then
                    if ! tui_yesno "Port Conflict Detected" \
                        "Port 80 or 443 is already in use (commonly Apache (httpd) or another reverse proxy).\nStop the conflicting service first, then re-run.\n\nContinue anyway?" "no"; then
                        exit 1
                    fi
                fi
            fi
        fi
    fi
}

# Install Docker Engine + the Compose plugin via Docker's official convenience
# script (https://get.docker.com). Per Docker's documented good practice the
# script is downloaded to a file first so it can be inspected, then run.
_install_docker_convenience() {
    print_step "🐳 Installing Docker via the official convenience script (https://get.docker.com)"
    local script
    script=$(mktemp /tmp/get-docker.XXXXXX.sh) || {
        print_error "Cannot create a temporary file for the Docker install script."
        exit 1
    }
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://get.docker.com -o "$script" || {
            rm -f "$script"
            print_error "Failed to download the Docker convenience script from https://get.docker.com"
            exit 1
        }
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$script" https://get.docker.com || {
            rm -f "$script"
            print_error "Failed to download the Docker convenience script from https://get.docker.com"
            exit 1
        }
    else
        rm -f "$script"
        print_error "Neither curl nor wget is available to download the Docker convenience script."
        print_error "Install Docker manually: https://docs.docker.com/engine/install/"
        exit 1
    fi
    print_status "Downloaded the Docker convenience script to $script (inspect it if you wish)."
    if ! sh "$script"; then
        rm -f "$script"
        print_error "The Docker convenience script failed."
        exit 1
    fi
    rm -f "$script"
    # The script enables the daemon on systemd hosts; make sure it is running.
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable --now docker >/dev/null 2>&1 || true
    fi
    print_status "Docker installed."
}

# Verify an already-present Docker can run a compose stack. Hard-fails with
# actionable hints on a v1-only compose or an unreachable daemon. Read-only —
# safe to call before the confirm screen.
_docker_verify_runtime() {
    # Compose v2 is the Go plugin invoked as 'docker compose'. The standalone
    # Python 'docker-compose' (v1) is end-of-life and unsupported here.
    if ! docker compose version >/dev/null 2>&1; then
        print_error "The Docker Compose v2 plugin is not available ('docker compose')."
        if command -v docker-compose >/dev/null 2>&1; then
            print_error "Found the legacy v1 'docker-compose' — it is end-of-life and not supported."
        fi
        print_error "Install the Compose v2 plugin: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Daemon reachability — catches a stopped daemon or a permission problem.
    if ! docker info >/dev/null 2>&1; then
        print_error "Cannot talk to the Docker daemon."
        print_error "Start it ('systemctl start docker') and ensure this user may reach the socket."
        exit 1
    fi

    print_status "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?') / $(docker compose version --short 2>/dev/null || echo 'compose v2') detected."

    # The installer runs as root, but the operator usually drives 'docker compose'
    # later as their normal user — warn if that user lacks docker-group access.
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        if ! id -nG "$SUDO_USER" 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
            print_warning "User '$SUDO_USER' is not in the 'docker' group; they will need sudo to manage this stack."
            print_warning "Grant access with: usermod -aG docker $SUDO_USER  (then re-login)."
        fi
    fi

    # A host-package BunkerWeb install would fight this stack over ports 80/443.
    if [ -f /usr/share/bunkerweb/VERSION ]; then
        print_warning "An existing host-package BunkerWeb install was detected (/usr/share/bunkerweb/VERSION)."
        print_warning "Stop it before starting the Docker stack: systemctl stop bunkerweb bunkerweb-scheduler bunkerweb-ui"
    fi
}

# Early host-capability gate (runs BEFORE the confirm screen, like
# check_supported_os). It only CHECKS and, if Docker is missing, records the
# operator's consent to install it later — it never mutates the system here.
# The deferred install happens in _docker_ensure_runtime() after the confirm.
check_docker_prereqs() {
    print_step "🐳 Checking Docker prerequisites"

    if command -v docker >/dev/null 2>&1; then
        _docker_verify_runtime
        return 0
    fi

    # Docker missing — decide WHETHER to install it; defer the install itself.
    if [ "$DOCKER_AUTO_INSTALL" = "yes" ]; then
        DOCKER_NEED_INSTALL="yes"
        print_status "Docker is not installed — it will be installed after you confirm the configuration."
    elif [ "$INTERACTIVE_MODE" = "yes" ]; then
        if tui_yesno "Install Docker?" \
            "Docker is not installed.\nInstall it via Docker's official convenience script (https://get.docker.com) once you confirm the configuration?" "yes"; then
            DOCKER_NEED_INSTALL="yes"
        else
            print_error "Docker is required for the Docker deployment path."
            print_error "Install Docker Engine: https://docs.docker.com/engine/install/"
            exit 1
        fi
    else
        print_error "Docker is not installed."
        print_error "Re-run with --install-docker to install it automatically,"
        print_error "or install Docker Engine first: https://docs.docker.com/engine/install/"
        exit 1
    fi
    # Compose/daemon checks cannot run until Docker exists — _docker_ensure_runtime().
}

# Perform any deferred Docker install, then verify the runtime. This is the
# FIRST step of docker_install_flow(), i.e. the first thing that runs AFTER the
# operator confirmed the configuration — no system mutation happens before it.
_docker_ensure_runtime() {
    if [ "$DOCKER_NEED_INSTALL" = "yes" ]; then
        _install_docker_convenience
        if ! command -v docker >/dev/null 2>&1; then
            print_error "Docker is still not available after the install attempt."
            exit 1
        fi
        _docker_verify_runtime
    fi
}

# Private (RFC1918) IPv4 check.
is_private_ipv4() {
    local ip="$1"
    local o1 o2 _o3 _o4

    if [[ ! $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        return 1
    fi

    IFS='.' read -r o1 o2 _o3 _o4 <<< "$ip"

    if [ "$o1" -eq 10 ]; then
        return 0
    elif [ "$o1" -eq 172 ] && [ "$o2" -ge 16 ] && [ "$o2" -le 31 ]; then
        return 0
    elif [ "$o1" -eq 192 ] && [ "$o2" -eq 168 ]; then
        return 0
    fi

    return 1
}

# Reject 127.0.0.0/8 + 169.254.0.0/16 — last-resort filter for cloud public-IPv4 pickup.
is_loopback_or_link_local_ipv4() {
    local ip="$1"
    local o1 o2 _o3 _o4

    if [[ ! $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        return 1
    fi

    IFS='.' read -r o1 o2 _o3 _o4 <<< "$ip"

    if [ "$o1" -eq 127 ]; then
        return 0
    elif [ "$o1" -eq 169 ] && [ "$o2" -eq 254 ]; then
        return 0
    fi

    return 1
}

# First IPv4 from a whitespace-separated list.
extract_first_ipv4() {
    local input="$1"
    local token

    for token in $input; do
        if [[ $token =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
            echo "$token"
            return 0
        fi
    done

    # Always return 0 — caller detects empty stdout. Non-zero would kill the script under `set -e`.
    echo ""
    return 0
}

# Prompt for a local IPv4. 0 = set, 1 = cancel (caller decides if fatal).
prompt_for_local_ipv4() {
    local -n __target_var="$1"
    local answer=""
    local ip=""

    while true; do
        if ! answer=$(tui_input "Local IPv4 Address" \
            "Enter the local IPv4 address to use:" ""); then
            return 1
        fi
        ip=$(extract_first_ipv4 "$answer")
        if [ -n "$ip" ]; then
            __target_var="$ip"
            return 0
        fi
        tui_msgbox "Local IPv4 Address" "Invalid IPv4 address. Please try again."
    done
}

# Primary IPv4 from local routing/interface info — no external queries.
get_primary_ipv4() {
    local primary_ip=""
    local route_output=""
    local host_output=""
    local addr_output=""
    local prev=""
    local token=""
    local line=""
    local candidate=""

    # Ask the kernel for the source addr it'd use to reach TEST-NET-1 (RFC 5737, 192.0.2.0/24, reserved).
    # Pure routing lookup — no packet sent. Honours policy routing/VRFs.
    if command -v ip >/dev/null 2>&1; then
        route_output=$(ip -4 route get 192.0.2.1 2>/dev/null || true)
        if [ -n "$route_output" ]; then
            prev=""
            for token in $route_output; do
                if [ "$prev" = "src" ]; then
                    candidate="$token"
                    if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! is_loopback_or_link_local_ipv4 "$candidate"; then
                        echo "$candidate"
                        return 0
                    fi
                fi
                prev="$token"
            done
        fi
    fi

    if command -v ip >/dev/null 2>&1; then
        route_output=$(ip -4 route show default 2>/dev/null || true)
        if [ -z "$route_output" ]; then
            route_output=$(ip route show default 2>/dev/null || true)
        fi
        if [ -n "$route_output" ]; then
            prev=""
            for token in $route_output; do
                if [ "$prev" = "src" ]; then
                    candidate="$token"
                    if is_private_ipv4 "$candidate"; then
                        primary_ip="$candidate"
                        break
                    fi
                fi
                prev="$token"
            done
        fi
    fi

    if [ -z "$primary_ip" ] && command -v hostname >/dev/null 2>&1; then
        host_output=$(hostname -I 2>/dev/null || true)
        if [ -n "$host_output" ]; then
            for token in $host_output; do
                if [[ $token =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && is_private_ipv4 "$token"; then
                    primary_ip="$token"
                    break
                fi
            done
        fi
    fi

    if [ -z "$primary_ip" ] && command -v ip >/dev/null 2>&1; then
        addr_output=$(ip -4 addr show scope global 2>/dev/null || true)
        if [ -n "$addr_output" ]; then
            while IFS= read -r line; do
                case "$line" in
                    *inet\ *)
                        line=${line#*inet }
                        candidate=${line%%/*}
                        if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && is_private_ipv4 "$candidate"; then
                            primary_ip="$candidate"
                            break
                        fi
                        ;;
                esac
            done <<< "$addr_output"
        fi
    fi

    # Fallback: no RFC1918 — accept any non-loopback/non-link-local (cloud public-only VMs).
    if [ -z "$primary_ip" ] && command -v ip >/dev/null 2>&1; then
        prev=""
        route_output=$(ip -4 route show default 2>/dev/null || true)
        if [ -z "$route_output" ]; then
            route_output=$(ip route show default 2>/dev/null || true)
        fi
        if [ -n "$route_output" ]; then
            for token in $route_output; do
                if [ "$prev" = "src" ]; then
                    candidate="$token"
                    if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! is_loopback_or_link_local_ipv4 "$candidate"; then
                        primary_ip="$candidate"
                        break
                    fi
                fi
                prev="$token"
            done
        fi

        if [ -z "$primary_ip" ]; then
            addr_output=$(ip -4 addr show scope global 2>/dev/null || true)
            if [ -n "$addr_output" ]; then
                while IFS= read -r line; do
                    case "$line" in
                        *inet\ *)
                            line=${line#*inet }
                            candidate=${line%%/*}
                            if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! is_loopback_or_link_local_ipv4 "$candidate"; then
                                primary_ip="$candidate"
                                break
                            fi
                            ;;
                    esac
                done <<< "$addr_output"
            fi
        fi
    fi

    if [ -z "$primary_ip" ] && command -v hostname >/dev/null 2>&1; then
        host_output=$(hostname -I 2>/dev/null || true)
        if [ -n "$host_output" ]; then
            for token in $host_output; do
                if [[ $token =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! is_loopback_or_link_local_ipv4 "$token"; then
                    primary_ip="$token"
                    break
                fi
            done
        fi
    fi

    # FreeBSD: parse ifconfig (ip(8)/hostname -I are Linux-only). Pass 1 private, pass 2 any non-loopback.
    if [ -z "$primary_ip" ] && command -v ifconfig >/dev/null 2>&1; then
        addr_output=$(ifconfig 2>/dev/null || true)
        # Pass 1: private candidate.
        while IFS= read -r line; do
            case "$line" in
                *inet\ *)
                    line=${line#*inet }
                    candidate=${line%% *}
                    if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && is_private_ipv4 "$candidate"; then
                        primary_ip="$candidate"
                        break
                    fi
                    ;;
            esac
        done <<< "$addr_output"
        # Pass 2: any non-loopback / non-link-local (cloud VM with only public IP).
        if [ -z "$primary_ip" ]; then
            while IFS= read -r line; do
                case "$line" in
                    *inet\ *)
                        line=${line#*inet }
                        candidate=${line%% *}
                        if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! is_loopback_or_link_local_ipv4 "$candidate"; then
                            primary_ip="$candidate"
                            break
                        fi
                        ;;
                esac
            done <<< "$addr_output"
        fi
    fi

    echo "$primary_ip"
}

# Enumerate global-scope IPv4s with iface names ("<ip> <iface>" per line, kernel primary first).
enumerate_global_ipv4_candidates() {
    local addr_output line ip iface kernel_choice=""

    if command -v ip >/dev/null 2>&1; then
        addr_output=$(ip -4 addr show scope global 2>/dev/null || true)
    elif command -v ifconfig >/dev/null 2>&1; then
        # FreeBSD: reshape ifconfig into `inet IP/PFX … iface` for the parser below.
        addr_output=$(ifconfig 2>/dev/null | awk '
            /^[^[:space:]]/ {
                iface = $1
                sub(/:$/, "", iface)
                next
            }
            /^[[:space:]]*inet / {
                if ($2 ~ /^127\./) next
                # Reshape to `ip addr` format; /32 stub — parser only reads IP before slash.
                printf "    inet %s/32 brd 0.0.0.0 scope global %s\n", $2, iface
            }
        ' || true)
    fi
    if [ -z "$addr_output" ]; then
        return 0
    fi

    kernel_choice=$(get_primary_ipv4)

    if [ -n "$kernel_choice" ]; then
        while IFS= read -r line; do
            case "$line" in
                *inet\ *)
                    ip=${line#*inet }
                    ip=${ip%%/*}
                    iface=${line##* }
                    if [ "$ip" = "$kernel_choice" ]; then
                        printf '%s %s\n' "$ip" "$iface"
                        break
                    fi
                    ;;
            esac
        done <<< "$addr_output"
    fi

    while IFS= read -r line; do
        case "$line" in
            *inet\ *)
                ip=${line#*inet }
                ip=${ip%%/*}
                iface=${line##* }
                if [[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] \
                   && ! is_loopback_or_link_local_ipv4 "$ip" \
                   && [ "$ip" != "$kernel_choice" ]; then
                    printf '%s %s\n' "$ip" "$iface"
                fi
                ;;
        esac
    done <<< "$addr_output"
}

# Decide IP for post-install "Next steps" URLs. Precedence:
#   1. --server-ip / $SERVER_IP_INPUT
#   2. Single global IPv4 → use silently
#   3. None → empty (placeholder)
#   4. Multiple + non-interactive → kernel primary
#   5. Multiple + interactive → menu with kernel primary preselected
# Output in $RESOLVED_SERVER_IP (global; menu prompts stay on stdout, not $(...) captured).
resolve_display_server_ip() {
    RESOLVED_SERVER_IP=""

    local provided raw_input="${SERVER_IP_INPUT:-}"
    provided=$(extract_first_ipv4 "$raw_input")
    if [ -n "$provided" ]; then
        RESOLVED_SERVER_IP="$provided"
        return 0
    fi
    # Non-IPv4 input (e.g. FQDN) — accept verbatim after trim + length sanity.
    if [ -n "$raw_input" ]; then
        local _trimmed="${raw_input#"${raw_input%%[![:space:]]*}"}"
        _trimmed="${_trimmed%"${_trimmed##*[![:space:]]}"}"
        if [ -n "$_trimmed" ] && [ "${#_trimmed}" -le 253 ]; then
            RESOLVED_SERVER_IP="$_trimmed"
            return 0
        fi
        print_warning "--server-ip / SERVER_IP_INPUT '$raw_input' is empty after trimming or too long (>253 chars); using auto-detection."
    fi

    local kernel_choice
    kernel_choice=$(get_primary_ipv4)

    local candidates=() count=0 line
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        candidates+=("$line")
        count=$((count + 1))
    done < <(enumerate_global_ipv4_candidates)

    if [ "$count" -le 1 ] || [ "$INTERACTIVE_MODE" != "yes" ]; then
        RESOLVED_SERVER_IP="$kernel_choice"
        return 0
    fi

    tui_section "🌐 Server IP for the post-install URLs"

    # Build tui_menu args: one tag per IP (tag IS the answer), plus "__manual__" fallback.
    local menu_args=() ip iface default_tag=""
    local i=0
    for line in "${candidates[@]}"; do
        ip=${line%% *}
        iface=${line##* }
        [ "$i" -eq 0 ] && default_tag="$ip"
        if [ "$i" -eq 0 ]; then
            menu_args+=("$ip" "$ip on $iface (default)")
        else
            menu_args+=("$ip" "$ip on $iface")
        fi
        i=$((i + 1))
    done
    menu_args+=("__manual__" "Enter manually")

    local picked manual_ip=""
    picked=$(tui_menu "Server IP" \
        "Multiple IPv4 addresses detected. Select the one clients will use to reach this server:" \
        "$default_tag" "${menu_args[@]}") || picked="$default_tag"

    if [ "$picked" = "__manual__" ]; then
        # ESC out → fall back to kernel choice rather than die.
        if prompt_for_local_ipv4 manual_ip; then
            RESOLVED_SERVER_IP="$manual_ip"
        else
            print_warning "Manual IP entry cancelled; using detected $default_tag."
            RESOLVED_SERVER_IP="$default_tag"
        fi
    else
        RESOLVED_SERVER_IP="$picked"
    fi
    return 0
}

should_apply_redis_config() {
    if [ "$REDIS_INSTALL" = "yes" ] || [ -n "$REDIS_HOST_INPUT" ] || [ -n "$REDIS_PORT_INPUT" ] || [ -n "$REDIS_DATABASE_INPUT" ] || [ -n "$REDIS_USERNAME_INPUT" ] || [ -n "$REDIS_PASSWORD_INPUT" ] || [ -n "$REDIS_SSL_INPUT" ] || [ -n "$REDIS_SSL_VERIFY_INPUT" ]; then
        return 0
    fi
    return 1
}

apply_redis_config() {
    local config_file="$1"
    local redis_host="${REDIS_HOST_INPUT:-}"
    local redis_port="${REDIS_PORT_INPUT:-6379}"
    local redis_db="${REDIS_DATABASE_INPUT:-0}"

    if [ -z "$redis_host" ]; then
        redis_host="127.0.0.1"
    fi

    set_config_kv "$config_file" "USE_REDIS" "yes"
    set_config_kv "$config_file" "REDIS_HOST" "$redis_host"
    set_config_kv "$config_file" "REDIS_PORT" "$redis_port"
    set_config_kv "$config_file" "REDIS_DATABASE" "$redis_db"
    if [ -n "$REDIS_USERNAME_INPUT" ]; then
        set_config_kv "$config_file" "REDIS_USERNAME" "$REDIS_USERNAME_INPUT"
    fi
    if [ -n "$REDIS_PASSWORD_INPUT" ]; then
        set_config_kv "$config_file" "REDIS_PASSWORD" "$REDIS_PASSWORD_INPUT"
    fi
    if [ -n "$REDIS_SSL_INPUT" ]; then
        set_config_kv "$config_file" "REDIS_SSL" "$REDIS_SSL_INPUT"
    fi
    if [ -n "$REDIS_SSL_VERIFY_INPUT" ]; then
        set_config_kv "$config_file" "REDIS_SSL_VERIFY" "$REDIS_SSL_VERIFY_INPUT"
    fi
}

should_apply_crowdsec_config() {
    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        return 0
    fi
    return 1
}

apply_crowdsec_config() {
    local config_file="$1"

    set_config_kv "$config_file" "USE_CROWDSEC" "yes"
    set_config_kv "$config_file" "CROWDSEC_API" "http://127.0.0.1:8080"
    if [ -n "$CROWDSEC_API_KEY" ]; then
        set_config_kv "$config_file" "CROWDSEC_API_KEY" "$CROWDSEC_API_KEY"
    fi
    if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
        set_config_kv "$config_file" "CROWDSEC_APPSEC_URL" "http://127.0.0.1:7422"
    fi
}

apply_optional_integrations() {
    local config_file="$1"
    local needs_reload_var="$2"
    # `_changes` must not collide with caller var: bash `local -n` resolves in current scope first,
    # so a `local needs_reload` here would shadow the caller's `needs_reload` (used by configure_full_config).
    local _changes=false

    if should_apply_redis_config; then
        print_status "Applying Redis configuration"
        apply_redis_config "$config_file"
        _changes=true
    fi

    if should_apply_crowdsec_config; then
        print_status "Applying CrowdSec configuration"
        apply_crowdsec_config "$config_file"
        _changes=true
    fi

    # Propagate change flag via nameref (`__aoi_target` unique to avoid local-scope collision).
    if [ -n "$needs_reload_var" ] && [ "$_changes" = true ]; then
        local -n __aoi_target="$needs_reload_var"
        __aoi_target=true
    fi
}

# Ensure manager installations expose the API and only whitelist the local host IP
configure_manager_api_defaults() {
    local config_file="/etc/bunkerweb/variables.env"
    local whitelist_ip
    local provided_ip

    provided_ip=$(extract_first_ipv4 "$MANAGER_IP_INPUT")

    if [ -n "$provided_ip" ]; then
        whitelist_ip="$provided_ip"
    else
        whitelist_ip=$(get_primary_ipv4)
    fi

    if [ -z "$whitelist_ip" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            print_warning "Unable to detect a local network IP automatically."
            prompt_for_local_ipv4 whitelist_ip || {
                print_error "A local network IP is required for the manager API whitelist."
                exit 1
            }
            MANAGER_IP_INPUT="$whitelist_ip"
        else
            print_error "Unable to detect a local network IP. Provide it with --manager-ip <IP>."
            exit 1
        fi
    fi

    whitelist_ip="127.0.0.0/8 $whitelist_ip"
    whitelist_ip=$(printf '%s\n' "$whitelist_ip" | xargs)

    if [ -z "$provided_ip" ]; then
        MANAGER_IP_INPUT="$whitelist_ip"
    fi

    print_status "Applying manager API defaults (listen on 0.0.0.0, whitelist local IP $whitelist_ip)"

    # Template (no-op if file exists) + manager overrides via set_config_kv.
    write_default_variables_env_template "$config_file"

    set_config_kv "$config_file" "SERVER_NAME" ""
    if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
        set_config_kv "$config_file" "BUNKERWEB_INSTANCES" "$BUNKERWEB_INSTANCES_INPUT"
    else
        set_config_kv "$config_file" "BUNKERWEB_INSTANCES" ""
    fi
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        set_config_kv "$config_file" "DNS_RESOLVERS" "$DNS_RESOLVERS_INPUT"
    fi
    set_config_kv "$config_file" "HTTP_PORT" "80"
    set_config_kv "$config_file" "HTTPS_PORT" "443"
    set_config_kv "$config_file" "API_LISTEN_IP" "0.0.0.0"
    set_config_kv "$config_file" "API_WHITELIST_IP" "$whitelist_ip"
    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        set_config_kv "$config_file" "API_LISTEN_HTTPS" "yes"
    fi
    set_config_kv "$config_file" "API_TOKEN" ""
    # MULTISITE=yes whenever UI runs. Manager UI hardening: SERVICE_UI=no defers start
    # until admin/TLS provisioning; start_manager_ui re-enables. UI still runs → write yes here.
    if [ "${SERVICE_UI:-yes}" != "no" ] || [ "${MANAGER_UI_DEFERRED:-no}" = "yes" ]; then
        set_config_kv "$config_file" "MULTISITE" "yes"
    fi
    apply_optional_integrations "$config_file"

    print_status "Enabling and starting BunkerWeb Scheduler with configured settings..."
    if [ "$DISTRO_ID" = "freebsd" ]; then
        sysrc bunkerweb_scheduler_enable=YES >/dev/null 2>&1
        service bunkerweb_scheduler start
        sleep 2
        service bunkerweb_scheduler status || print_warning "BunkerWeb Scheduler may not be running"
    else
        run_cmd systemctl enable --now bunkerweb-scheduler
        sleep 2
        systemctl status bunkerweb-scheduler --no-pager -l || print_warning "BunkerWeb Scheduler may not be running"
    fi
}

# Worker installations: whitelist manager/scheduler IPs.
configure_worker_api_whitelist() {
    local config_file="/etc/bunkerweb/variables.env"
    local whitelist_value

    if [ -z "$MANAGER_IP_INPUT" ]; then
        print_warning "Manager IP not provided; please whitelist it manually in $config_file."
        return
    fi

    whitelist_value="127.0.0.0/8 $MANAGER_IP_INPUT"
    whitelist_value=$(printf '%s\n' "$whitelist_value" | xargs)

    print_status "Applying worker API whitelist: $whitelist_value"

    ensure_config_file "$config_file"

    set_config_kv "$config_file" "API_LISTEN_IP" "0.0.0.0"
    set_config_kv "$config_file" "API_WHITELIST_IP" "$whitelist_value"

    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        set_config_kv "$config_file" "DNS_RESOLVERS" "$DNS_RESOLVERS_INPUT"
    fi

    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        set_config_kv "$config_file" "API_LISTEN_HTTPS" "yes"
    fi

    print_status "Enabling and starting BunkerWeb with configured settings..."
    if [ "$DISTRO_ID" = "freebsd" ]; then
        sysrc bunkerweb_enable=YES >/dev/null 2>&1
        service bunkerweb start
        sleep 2
        service bunkerweb status || print_warning "BunkerWeb may not be running"
    else
        run_cmd systemctl enable --now bunkerweb
        sleep 2
        systemctl status bunkerweb --no-pager -l || print_warning "BunkerWeb may not be running"
    fi
}

# Full install: DNS resolvers, API HTTPS, multisite.
configure_full_config() {
    local config_file="/etc/bunkerweb/variables.env"
    local needs_reload=false

    # Idempotent template (preserves user edits on re-run).
    write_default_variables_env_template "$config_file"
    ensure_config_file "$config_file"

    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        set_config_kv "$config_file" "DNS_RESOLVERS" "$DNS_RESOLVERS_INPUT"
        needs_reload=true
    fi

    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        set_config_kv "$config_file" "API_LISTEN_HTTPS" "yes"
        needs_reload=true
    fi

    if [ "$ENABLE_WIZARD" = "yes" ] || [ "${SERVICE_UI:-no}" = "yes" ]; then
        set_config_kv "$config_file" "MULTISITE" "yes"
        needs_reload=true
    fi

    apply_optional_integrations "$config_file" "needs_reload"

    # Restart-or-start: `enable --now` is a no-op when active, so post-postinst changes
    # (MULTISITE, DNS_RESOLVERS) wouldn't apply otherwise.
    # Order: scheduler before bunkerweb (scheduler renders templates first).
    if [ "$needs_reload" = true ]; then
        print_status "Enabling and (re)starting services with configured settings..."
        if [ "$DISTRO_ID" = "freebsd" ]; then
            sysrc bunkerweb_scheduler_enable=YES >/dev/null 2>&1
            service bunkerweb_scheduler restart || service bunkerweb_scheduler start || true
            sysrc bunkerweb_enable=YES >/dev/null 2>&1
            service bunkerweb restart || service bunkerweb start || true
            if [ "$FULL_API_DEFERRED" = "yes" ]; then
                sysrc bunkerweb_api_enable=YES >/dev/null 2>&1
                service bunkerweb_api restart || service bunkerweb_api start || true
            fi
        else
            run_cmd systemctl enable bunkerweb-scheduler
            if systemctl is-active --quiet bunkerweb-scheduler; then
                run_cmd systemctl restart bunkerweb-scheduler
            else
                run_cmd systemctl start bunkerweb-scheduler
            fi
            run_cmd systemctl enable bunkerweb
            if systemctl is-active --quiet bunkerweb; then
                run_cmd systemctl restart bunkerweb
            else
                run_cmd systemctl start bunkerweb
            fi
            if [ "$FULL_API_DEFERRED" = "yes" ]; then
                run_cmd systemctl enable bunkerweb-api
                if systemctl is-active --quiet bunkerweb-api; then
                    run_cmd systemctl restart bunkerweb-api
                else
                    run_cmd systemctl start bunkerweb-api
                fi
            fi
        fi
    fi
}

install_nginx_debian() {
    print_step "Installing NGINX on Debian/Ubuntu"

    run_cmd apt update
    run_cmd apt install -y curl gnupg2 ca-certificates lsb-release

    if [ "$DISTRO_ID" = "debian" ]; then
        run_cmd apt install -y debian-archive-keyring
    elif [ "$DISTRO_ID" = "ubuntu" ]; then
        run_cmd apt install -y ubuntu-keyring
    fi

    # NGINX repo: stage key to tempfile (no `pipefail`; `curl | gpg | tee` would silently produce
    # an empty keyring on failure → cryptic NO_PUBKEY error later).
    local _nkey_tmp
    _nkey_tmp=$(mktemp /tmp/bw-nginx-key.XXXXXX) || {
        print_error "Could not create tempfile for the NGINX signing key."
        exit 1
    }
    if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
              --connect-timeout 10 --max-time 30 -L \
              -o "$_nkey_tmp" https://nginx.org/keys/nginx_signing.key; then
        print_error "Failed to download NGINX signing key from https://nginx.org/keys/nginx_signing.key"
        rm -f "$_nkey_tmp"
        exit 1
    fi
    if ! gpg --dearmor < "$_nkey_tmp" > /usr/share/keyrings/nginx-archive-keyring.gpg; then
        print_error "Failed to dearmor the NGINX signing key (key may be malformed)."
        rm -f "$_nkey_tmp" /usr/share/keyrings/nginx-archive-keyring.gpg
        exit 1
    fi
    rm -f "$_nkey_tmp"
    chmod 644 /usr/share/keyrings/nginx-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/$DISTRO_ID $DISTRO_CODENAME nginx" > /etc/apt/sources.list.d/nginx.list

    run_cmd apt update
    run_cmd apt install -y "nginx=$NGINX_VERSION"

    # Hold to prevent upgrades.
    run_cmd apt-mark hold nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

install_nginx_fedora() {
    print_step "Installing NGINX on Fedora"

    run_cmd dnf install -y 'dnf-command(versionlock)'

    if ! dnf info "nginx-$NGINX_VERSION" >/dev/null 2>&1; then
        print_status "Enabling updates-testing repository"
        run_cmd dnf config-manager setopt updates-testing.enabled=1
    fi

    run_cmd dnf install -y "nginx-$NGINX_VERSION"
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

install_nginx_rhel() {
    print_step "Installing NGINX on RHEL"

    run_cmd dnf install -y 'dnf-command(versionlock)'

    cat > /etc/yum.repos.d/nginx.repo << EOF
[nginx-stable]
name=nginx stable repo
baseurl=http://nginx.org/packages/centos/\$releasever/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true

[nginx-mainline]
name=nginx mainline repo
baseurl=http://nginx.org/packages/mainline/centos/\$releasever/\$basearch/
gpgcheck=1
enabled=0
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true
EOF

    # Remove any distro/AppStream nginx and conflicting modules first: their RPMs are
    # pinned to the distro nginx version and block the nginx.org package install.
    # Also disable the modular stream so AppStream filtering can't re-block the install
    # (belt-and-suspenders alongside module_hotfixes=true in the repo above).
    dnf -y module disable nginx >/dev/null 2>&1 || true
    dnf remove -y nginx nginx-mod-stream nginx-mod-http-image-filter nginx-mod-http-perl nginx-mod-http-xslt-filter nginx-mod-mail 2>/dev/null || true

    run_cmd dnf install -y "nginx-$NGINX_VERSION"
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

install_nginx_freebsd() {
    print_step "Installing NGINX on FreeBSD"

    run_cmd pkg update -f
    run_cmd pkg install -y nginx
    run_cmd pkg lock -y nginx

    print_status "NGINX installed successfully"
}

install_bunkerweb_debian() {
    print_step "Installing BunkerWeb on Debian/Ubuntu"

    if [[ "$BUNKERWEB_VERSION" =~ (testing|dev) ]]; then
        print_status "Adding force-bad-version directive for testing/dev version"
        echo "force-bad-version" >> /etc/dpkg/dpkg.cfg
    fi

    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # TLS-pin + bounded timeouts (no hang on stalled CDN).
    run_cmd curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
                 --connect-timeout 10 --max-time 60 -L \
                 https://repo.bunkerweb.io/install/script.deb.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    run_cmd apt update
    run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"

    run_cmd apt-mark hold bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

install_bunkerweb_rpm() {
    print_step "Installing BunkerWeb on $DISTRO_ID"

    # Offer EPEL on RHEL-family distros before installing BunkerWeb.
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]] && ! rpm -q epel-release >/dev/null 2>&1; then
        if [ "$INSTALL_EPEL" = "yes" ]; then
            print_step "Installing EPEL repository (epel-release)"
            run_cmd dnf install -y epel-release
        elif [ "$INSTALL_EPEL" = "no" ]; then
            print_warning "EPEL repository not installed; continuing without epel-release."
        elif [ "$INTERACTIVE_MODE" = "yes" ]; then
            print_warning "EPEL repository is not installed."
            if tui_yesno "EPEL Repository" \
                "The EPEL repository is not installed. Install epel-release now?" "no"; then
                INSTALL_EPEL="yes"
                print_step "Installing EPEL repository (epel-release)"
                run_cmd dnf install -y epel-release
            else
                INSTALL_EPEL="no"
            fi
        else
            INSTALL_EPEL="no"
            print_warning "EPEL repository not installed; skipping epel-release in non-interactive mode."
        fi
    fi

    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # TLS-pin + bounded timeouts (no hang on stalled CDN).
    run_cmd curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
                 --connect-timeout 10 --max-time 60 -L \
                 https://repo.bunkerweb.io/install/script.rpm.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    run_cmd dnf makecache
    run_cmd dnf install -y "bunkerweb-$BUNKERWEB_VERSION"
    run_cmd dnf versionlock add bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

install_bunkerweb_freebsd() {
    print_step "Installing BunkerWeb on FreeBSD"

    run_cmd pkg install -y bash python311 py311-pip curl libxml2 yajl gd sudo \
        lsof libmaxminddb postgresql16-client mariadb1011-client sqlite3 \
        openssl pcre2 lmdb ssdeep unzip gtar

    if ! pw groupshow nginx >/dev/null 2>&1; then
        print_status "Creating nginx group..."
        pw groupadd nginx
    fi

    if ! pw usershow nginx >/dev/null 2>&1; then
        print_status "Creating nginx user..."
        pw useradd nginx -g nginx -d /nonexistent -s /usr/sbin/nologin -c "nginx user"
    fi

    # Set environment variables
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # Download and install BunkerWeb source. FreeBSD packages aren't published
    # yet (the project ships pkg-built artifacts on Linux only); on FreeBSD we
    # extract a release tarball.
    BUNKERWEB_INSTALL_DIR="/usr/share/bunkerweb"

    if [ -z "${BUNKERWEB_TARBALL_URL:-}" ]; then
        print_error "Automatic FreeBSD installation requires BUNKERWEB_TARBALL_URL to be set."
        print_error "FreeBSD packages are not published yet — manual install is required:"
        print_error "  1. Pick a release from https://github.com/bunkerity/bunkerweb/releases"
        print_error "  2. export BUNKERWEB_TARBALL_URL=https://github.com/bunkerity/bunkerweb/archive/refs/tags/v${BUNKERWEB_VERSION}.tar.gz"
        print_error "  3. Re-run this installer."
        exit 1
    fi

    print_status "Installing BunkerWeb from source tarball..."

    mkdir -p "$BUNKERWEB_INSTALL_DIR"
    mkdir -p /etc/bunkerweb/configs /etc/bunkerweb/plugins
    mkdir -p /var/cache/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb
    mkdir -p /var/log/bunkerweb /var/lib/bunkerweb /var/www/html

    run_cmd curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
                 --connect-timeout 10 --max-time 300 -L \
                 "$BUNKERWEB_TARBALL_URL" -o /tmp/bunkerweb.tar.gz
    run_cmd tar -xzf /tmp/bunkerweb.tar.gz -C "$BUNKERWEB_INSTALL_DIR" --strip-components=1
    rm -f /tmp/bunkerweb.tar.gz

    if [ -d "$BUNKERWEB_INSTALL_DIR/deps" ]; then
        print_status "Python dependencies already bundled"
    elif [ -f "$BUNKERWEB_INSTALL_DIR/requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        mkdir -p "$BUNKERWEB_INSTALL_DIR/deps/python"
        # Surface pip errors — `|| true` would mask them and BunkerWeb would fail at runtime with cryptic ImportErrors.
        if ! python3.11 -m pip install --target "$BUNKERWEB_INSTALL_DIR/deps/python" \
                -r "$BUNKERWEB_INSTALL_DIR/requirements.txt"; then
            print_error "pip install failed — BunkerWeb cannot run without its Python dependencies."
            print_error "Inspect ${BUNKERWEB_INSTALL_DIR}/requirements.txt, fix the environment, and re-run."
            exit 1
        fi
    else
        print_error "Neither ${BUNKERWEB_INSTALL_DIR}/deps nor ${BUNKERWEB_INSTALL_DIR}/requirements.txt found."
        print_error "The tarball at \$BUNKERWEB_TARBALL_URL does not contain Python dependency information."
        print_error "Use a release tarball that bundles deps/ or includes requirements.txt at the top level."
        exit 1
    fi

    print_status "Installing rc.d service scripts..."
    if [ -d "$BUNKERWEB_INSTALL_DIR/rc.d" ]; then
        for script in bunkerweb bunkerweb_scheduler bunkerweb_ui bunkerweb_api; do
            if [ -f "$BUNKERWEB_INSTALL_DIR/rc.d/${script}" ]; then
                cp "$BUNKERWEB_INSTALL_DIR/rc.d/${script}" "/usr/local/etc/rc.d/${script}"
                chmod 555 "/usr/local/etc/rc.d/${script}"
            fi
        done
    fi

    chown -R root:nginx "$BUNKERWEB_INSTALL_DIR"
    chown -R nginx:nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb \
        /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb
    chmod 755 /var/log/bunkerweb
    chmod 770 /var/cache/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb
    chmod 2770 /var/tmp/bunkerweb

    if [ -f "$BUNKERWEB_INSTALL_DIR/helpers/bwcli" ]; then
        install -m 755 "$BUNKERWEB_INSTALL_DIR/helpers/bwcli" /usr/bin/bwcli
    fi

    echo "FreeBSD" > "$BUNKERWEB_INSTALL_DIR/INTEGRATION"

    pkg lock -y bunkerweb 2>/dev/null || true

    print_status "BunkerWeb installed successfully on FreeBSD"
}

install_crowdsec() {
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}CrowdSec Security Engine Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing CrowdSec security engine"

    # Check for the gpg binary (provided by the gnupg/gnupg2 package depending on distro);
    # `command -v gnupg2` never resolves since gnupg2 is a package name, not an executable.
    for dep in curl gpg; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            print_status "Installing missing dependency: $dep"
            case "$DISTRO_ID" in
                "debian"|"ubuntu")
                    dep_pkg="$dep"; [ "$dep" = "gpg" ] && dep_pkg="gnupg"
                    run_cmd apt update
                    run_cmd apt install -y "$dep_pkg"
                    ;;
                "fedora"|"rhel"|"rocky"|"almalinux"|"centos")
                    dep_pkg="$dep"; [ "$dep" = "gpg" ] && dep_pkg="gnupg2"
                    run_cmd dnf install -y "$dep_pkg"
                    ;;
                "freebsd")
                    dep_pkg="$dep"; [ "$dep" = "gpg" ] && dep_pkg="gnupg"
                    run_cmd pkg install -y "$dep_pkg"
                    ;;
                *)
                    print_warning "Automatic install not supported on $DISTRO_ID"
                    ;;
            esac
        fi
    done

    # ca-certificates has no binary, so probe the package, not `command -v`.
    case "$DISTRO_ID" in
        "debian"|"ubuntu") dpkg -s ca-certificates >/dev/null 2>&1 || { run_cmd apt update; run_cmd apt install -y ca-certificates; } ;;
        "fedora"|"rhel"|"rocky"|"almalinux"|"centos") rpm -q ca-certificates >/dev/null 2>&1 || run_cmd dnf install -y ca-certificates ;;
        "freebsd") pkg info -e ca_root_nss >/dev/null 2>&1 || run_cmd pkg install -y ca_root_nss ;;
    esac

    echo -e "${YELLOW}--- Step 1: Add CrowdSec repository and install engine ---${NC}"
    print_step "Adding CrowdSec repository and installing engine"
    # Tempfile + exec (not `curl … | sh`): pipefail isn't set so --fail errors wouldn't propagate,
    # and an HTML 4xx/5xx body would otherwise execute as shell.
    local _csc_install
    _csc_install=$(mktemp /tmp/bw-crowdsec-install.XXXXXX) || {
        print_error "Could not create tempfile for CrowdSec install script."
        return 1
    }
    if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
              --connect-timeout 10 --max-time 60 -L \
              -o "$_csc_install" https://install.crowdsec.net; then
        print_error "Failed to download CrowdSec install script from https://install.crowdsec.net"
        rm -f "$_csc_install"
        return 1
    fi
    run_cmd sh "$_csc_install"
    rm -f "$_csc_install"
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt install -y crowdsec
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux"|"centos")
            run_cmd dnf install -y crowdsec
            ;;
        "freebsd")
            run_cmd pkg install -y crowdsec
            ;;
        *)
            print_error "Unsupported distribution: $DISTRO_ID"
            return
            ;;
    esac
    print_status "CrowdSec engine installed"

    echo -e "${YELLOW}--- Step 2: Configure log acquisition for BunkerWeb ---${NC}"
    print_step "Configuring CrowdSec to parse BunkerWeb logs"
    # Use acquis.d/bunkerweb.yaml (idempotent overwrite) rather than appending to acquis.yaml.
    # CrowdSec auto-loads every *.yaml under acquis.d.
    ACQ_DIR="/etc/crowdsec/acquis.d"
    ACQ_FILE="${ACQ_DIR}/bunkerweb.yaml"
    ACQ_CONTENT="filenames:
  - /var/log/bunkerweb/access.log
  - /var/log/bunkerweb/error.log
  - /var/log/bunkerweb/modsec_audit.log
labels:
  type: bunkerweb
"
    mkdir -p "$ACQ_DIR"
    echo "$ACQ_CONTENT" > "$ACQ_FILE"
    print_status "Wrote BunkerWeb acquisition config to: $ACQ_FILE"
    # Comment out legacy stanzas in shared acquis.yaml (kept, not deleted — recoverable from backup).
    local _legacy="/etc/crowdsec/acquis.yaml"
    if [ -f "$_legacy" ] && grep -q '/var/log/bunkerweb/' "$_legacy"; then
        cp "$_legacy" "${_legacy}.bw-install.bak"
        print_status "Legacy bunkerweb stanza detected in $_legacy; a backup was saved to ${_legacy}.bw-install.bak"
        print_warning "Edit $_legacy and remove the bunkerweb block — it is now superseded by $ACQ_FILE."
    fi

    echo -e "${YELLOW}--- Step 3: Update hub and install core collections/parsers ---${NC}"
    print_step "Updating hub and installing detection collections/parsers"
    cscli hub update
    cscli collections install bunkerity/bunkerweb
    cscli parsers install crowdsecurity/geoip-enrich

    # AppSec installation if chosen
    if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
        echo -e "${YELLOW}--- Step 4: Install and configure CrowdSec AppSec Component ---${NC}"
        print_step "Installing and configuring CrowdSec AppSec Component"
        APPSEC_ACQ_FILE="/etc/crowdsec/acquis.d/appsec.yaml"
        APPSEC_ACQ_CONTENT="appsec_config: crowdsecurity/appsec-default
labels:
  type: appsec
listen_addr: 127.0.0.1:7422
source: appsec
"
        mkdir -p /etc/crowdsec/acquis.d
        echo "$APPSEC_ACQ_CONTENT" > "$APPSEC_ACQ_FILE"
        print_status "Created AppSec acquisition file: $APPSEC_ACQ_FILE"
        cscli collections install crowdsecurity/appsec-virtual-patching
        cscli collections install crowdsecurity/appsec-generic-rules
        print_status "Installed AppSec collections"
    fi

    echo -e "${YELLOW}--- Step 5: Register BunkerWeb bouncer(s) and retrieve API key ---${NC}"
    print_step "Registering BunkerWeb bouncer with CrowdSec"
    local _csc_err
    # Explicit template — FreeBSD mktemp requires one (bare `mktemp` returns
    # status 1 on BSD even when /tmp is writable).
    _csc_err=$(mktemp /tmp/bw-cscli-err.XXXXXX) || {
        print_warning "Could not create tempfile for cscli stderr capture; continuing without it."
        _csc_err=""
    }
    if [ -n "$_csc_err" ]; then
        BOUNCER_KEY=$(cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --output raw 2>"$_csc_err")
    else
        BOUNCER_KEY=$(cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --output raw 2>/dev/null)
    fi
    if [ -z "$BOUNCER_KEY" ]; then
        print_warning "Failed to register bouncer with CrowdSec."
        [ -s "$_csc_err" ] && sed 's/^/  cscli: /' "$_csc_err"
        print_warning "Register it manually after install: cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6"
    else
        print_status "Bouncer registered successfully"
    fi
    rm -f "$_csc_err"

    if [ -n "$BOUNCER_KEY" ]; then
        CROWDSEC_API_KEY="$BOUNCER_KEY"
    fi

    echo
    echo -e "${GREEN}CrowdSec installed successfully${NC}"
    echo "See BunkerWeb docs for more: https://docs.bunkerweb.io/latest/features/#crowdsec"
    echo -e "${BLUE}========================================${NC}"
}

# Try installing the chosen Redis-compatible package; fall back to redis if valkey is missing.
# Sets REDIS_FLAVOR (resolved to "redis" or "valkey") on the way out.
_install_redis_package() {
    local desired="${REDIS_FLAVOR:-redis}"
    local installed=""

    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt update
            if [ "$desired" = "valkey" ]; then
                if apt-cache show valkey-server >/dev/null 2>&1; then
                    if apt install -y valkey-server; then
                        installed="valkey-server"
                    fi
                fi
                if [ -z "$installed" ]; then
                    print_warning "Valkey not available in your apt repos — falling back to redis-server."
                    REDIS_FLAVOR="redis"
                    run_cmd apt install -y redis-server
                fi
            else
                run_cmd apt install -y redis-server
            fi
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux"|"centos")
            if [ "$desired" = "valkey" ]; then
                if dnf info valkey >/dev/null 2>&1; then
                    if dnf install -y valkey; then
                        installed="valkey"
                    fi
                fi
                if [ -z "$installed" ]; then
                    print_warning "Valkey not available in your dnf repos — falling back to redis."
                    REDIS_FLAVOR="redis"
                    run_cmd dnf install -y redis
                fi
            else
                run_cmd dnf install -y redis
            fi
            ;;
        "freebsd")
            if [ "$desired" = "valkey" ]; then
                if pkg search -q '^valkey$' >/dev/null 2>&1 || pkg search -q '^valkey-' >/dev/null 2>&1; then
                    if pkg install -y valkey; then
                        installed="valkey"
                    fi
                fi
                if [ -z "$installed" ]; then
                    print_warning "Valkey not available via pkg — falling back to redis."
                    REDIS_FLAVOR="redis"
                    run_cmd pkg install -y redis
                fi
            else
                run_cmd pkg install -y redis
            fi
            ;;
        *)
            print_error "Unsupported distribution: $DISTRO_ID"
            return 1
            ;;
    esac

    return 0
}

# Path to redis/valkey config file (empty if not found).
_locate_redis_conf() {
    local flavor="${REDIS_FLAVOR:-redis}"
    local candidates=()

    if [ "$flavor" = "valkey" ]; then
        candidates=(
            /etc/valkey/valkey.conf
            /usr/local/etc/valkey/valkey.conf
            /etc/redis/redis.conf
            /etc/redis.conf
            /usr/local/etc/redis.conf
        )
    else
        candidates=(
            /etc/redis/redis.conf
            /etc/redis.conf
            /usr/local/etc/redis.conf
            /etc/valkey/valkey.conf
        )
    fi

    for path in "${candidates[@]}"; do
        if [ -f "$path" ]; then
            echo "$path"
            return 0
        fi
    done

    echo ""
    return 1
}

# systemd unit name for the installed flavor.
_locate_redis_service() {
    local flavor="${REDIS_FLAVOR:-redis}"
    local order=()

    if [ "$flavor" = "valkey" ]; then
        order=(valkey-server valkey redis-server redis)
    else
        order=(redis-server redis valkey-server valkey)
    fi

    for candidate in "${order[@]}"; do
        if systemctl list-unit-files --type=service --all 2>/dev/null | grep -q "^${candidate}\.service"; then
            echo "$candidate"
            return 0
        fi
    done

    echo ""
    return 1
}

# Idempotent directive rewrite (replace all matches case-insensitive, else append).
_redis_conf_set() {
    local conf="$1"
    local directive="$2"
    local value="$3"
    local tmp

    if [ ! -f "$conf" ]; then
        return 1
    fi

    # Explicit template — bare `mktemp` returns 1 on FreeBSD even when /tmp is writable.
    tmp=$(mktemp /tmp/bw-redis-conf.XXXXXX) || return 1
    # Strip every existing matching line (commented or not).
    awk -v d="$directive" 'BEGIN{IGNORECASE=1} {
        line=$0
        sub(/^[ \t]+/, "", line)
        sub(/^#+[ \t]*/, "", line)
        n=length(d)
        if (tolower(substr(line,1,n)) == tolower(d) && substr(line,n+1,1) ~ /[ \t]/) next
        print
    }' "$conf" > "$tmp"
    printf '%s %s\n' "$directive" "$value" >> "$tmp"
    cat "$tmp" > "$conf"
    rm -f "$tmp"
}

install_redis() {
    local label conf service redis_started="no"
    label="${REDIS_FLAVOR:-redis}"

    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}${label^} Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing ${label}"

    if ! _install_redis_package; then
        return
    fi

    label="${REDIS_FLAVOR:-redis}"

    if [ "$DISTRO_ID" = "freebsd" ]; then
        # FreeBSD rc service name (also used in the remediation hints below).
        if [ "$REDIS_FLAVOR" = "valkey" ]; then
            service="valkey"
            sysrc valkey_enable=YES >/dev/null 2>&1
        else
            service="redis"
            sysrc redis_enable=YES >/dev/null 2>&1
        fi
        if service "$service" start; then
            redis_started="yes"
            print_status "${label^} service enabled and started"
        else
            print_warning "${label^} service ($service) failed to start."
        fi
    else
        # Refresh systemd's unit view BEFORE locating the unit — the dpkg
        # postinst may have failed to reach systemd (deb-systemd-invoke
        # "Could not execute systemctl"), leaving the just-installed unit
        # unregistered. Must run before _locate_redis_service, not inside
        # start_optional_service (which is skipped when the locator fails).
        systemctl daemon-reload 2>/dev/null || true
        service=$(_locate_redis_service || true)
        if [ -n "$service" ]; then
            # Optional daemon — a start failure must not abort the install.
            if start_optional_service "$service" "${label^}"; then
                redis_started="yes"
                print_status "${label^} service enabled and started ($service)"
            fi
        else
            print_warning "${label^} service name not found; start it manually if needed."
        fi
    fi

    # Apply bind / requirepass / protected-mode from user choices.
    conf=$(_locate_redis_conf || true)
    if [ -z "$conf" ]; then
        print_warning "Could not locate the ${label} config file; bind/password configuration skipped."
    else
        local bind_addr password_set=""
        bind_addr="${REDIS_BIND_INPUT:-127.0.0.1}"

        # Auto-gen password if user opted in and bind ≠ loopback.
        # Non-interactive fallback only — the interactive prompt sets
        # REDIS_REQUIREPASS_LOCAL itself (and its own REDIS_PASSWORD_GENERATED).
        if [ "$bind_addr" != "127.0.0.1" ] && [ -z "$REDIS_REQUIREPASS_LOCAL" ] && [ "$REDIS_AUTOPASS" = "yes" ]; then
            REDIS_REQUIREPASS_LOCAL=$(generate_secret 32)
            REDIS_PASSWORD_GENERATED="$REDIS_REQUIREPASS_LOCAL"
        fi

        _redis_conf_set "$conf" "bind" "$bind_addr"

        if [ -n "$REDIS_REQUIREPASS_LOCAL" ]; then
            _redis_conf_set "$conf" "requirepass" "$REDIS_REQUIREPASS_LOCAL"
            _redis_conf_set "$conf" "protected-mode" "no"
            password_set="yes"
        fi

        # Memory cap + eviction. "0" = keep distro defaults, skip writes.
        local memory_summary=""
        if [ -n "$REDIS_MAXMEMORY_MB" ] && [ "$REDIS_MAXMEMORY_MB" != "0" ]; then
            _redis_conf_set "$conf" "maxmemory" "${REDIS_MAXMEMORY_MB}mb"
            _redis_conf_set "$conf" "maxmemory-policy" "${REDIS_MAXMEMORY_POLICY:-volatile-lru}"
            memory_summary=" maxmemory=${REDIS_MAXMEMORY_MB}mb policy=${REDIS_MAXMEMORY_POLICY:-volatile-lru}"
        fi

        chmod 640 "$conf" 2>/dev/null || true
        print_status "Configured ${label} bind=${bind_addr}${password_set:+ (REQUIREPASS set)}${memory_summary} in ${conf}"

        # Restart to pick up new bind/password.
        if [ "$DISTRO_ID" = "freebsd" ]; then
            if service "$service" restart; then
                redis_started="yes"
            else
                redis_started="no"
                print_warning "${label^} service ($service) failed to restart after configuration."
            fi
        else
            if [ -n "$service" ]; then
                echo -e "${BLUE}[CMD]${NC} systemctl restart $service"
                if systemctl restart "$service"; then
                    redis_started="yes"
                else
                    redis_started="no"
                    print_warning "${label^} service ($service) failed to restart after configuration."
                    _dump_service_diagnostics "$service"
                fi
            fi
        fi
    fi

    # BunkerWeb client target: 0.0.0.0 bind → manager's primary IPv4; else bind addr.
    if [ -z "$REDIS_HOST_INPUT" ]; then
        if [ "${REDIS_BIND_INPUT:-127.0.0.1}" = "0.0.0.0" ]; then
            local primary_ip
            primary_ip=$(get_primary_ipv4)
            REDIS_HOST_INPUT="${primary_ip:-127.0.0.1}"
        else
            REDIS_HOST_INPUT="${REDIS_BIND_INPUT:-127.0.0.1}"
        fi
    fi

    # Push auto-gen password into BunkerWeb client config.
    if [ -n "$REDIS_REQUIREPASS_LOCAL" ] && [ -z "$REDIS_PASSWORD_INPUT" ]; then
        REDIS_PASSWORD_INPUT="$REDIS_REQUIREPASS_LOCAL"
    fi

    echo
    if [ "$redis_started" = "yes" ]; then
        echo -e "${GREEN}${label^} installed and configured successfully${NC}"
        echo "Used by BunkerWeb to persist metrics and bans across restarts and to sync state between workers."
        echo "See BunkerWeb docs for more: https://docs.bunkerweb.io/latest/features/#redis"
    else
        # Optional daemon down — install continues. BunkerWeb still runs without
        # Redis (in-memory only); USE_REDIS=yes points at a server not yet up.
        print_warning "${label^} is installed and configured but the local server is NOT running."
        print_warning "BunkerWeb is set to use it (USE_REDIS=yes), but until it is started:"
        print_warning "  - bans and rate-limit counters are NOT shared between workers/instances"
        print_warning "  - that state is lost on every reload/restart (no HA persistence)"
        print_warning "Start it manually to close this gap:"
        if [ "$DISTRO_ID" = "freebsd" ]; then
            print_warning "  service $service status    # see why it failed"
            print_warning "  service $service start     # start once fixed"
        elif [ -n "$service" ]; then
            print_warning "  systemctl status $service    # see why it failed"
            print_warning "  journalctl -xeu $service     # full error log"
            print_warning "  systemctl start $service     # start once fixed"
        else
            print_warning "  check the local ${label} service status and start it manually"
        fi
    fi
    echo -e "${BLUE}========================================${NC}"
}

# Write DATABASE_URI once to variables.env — scheduler/UI/API all source it before their own env files.
apply_db_config() {
    local dsn="$1"
    local target

    if [ -z "$dsn" ]; then
        return
    fi

    target=/etc/bunkerweb/variables.env
    write_default_variables_env_template "$target"
    set_config_kv "$target" "DATABASE_URI" "$dsn"
}

# Write UI_HOST + MULTISITE to variables.env — required by default-server-http/ui.conf
# (`{%- if UI_HOST != "" %}` gate); without UI_HOST the wizard/login pages are unreachable.
# MULTISITE=yes must accompany it: postinstall.sh:189 only writes wizard defaults
# when variables.env is missing/IS_LOADING=yes, and we pre-create the file.
# Scheme: http (gunicorn default); https when UI_SELFSIGNED_INPUT=yes.
apply_ui_host_config() {
    local target=/etc/bunkerweb/variables.env
    local scheme="http"
    if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
        scheme="https"
    fi
    write_default_variables_env_template "$target"
    set_config_kv "$target" "UI_HOST" "${scheme}://127.0.0.1:7000"
    set_config_kv "$target" "MULTISITE" "yes"
}

# SQLAlchemy DSN for the external engine. Output matches DB_STRING_RX at src/common/db/Database.py:111.
build_external_db_dsn() {
    local engine="${DB_EXTERNAL_ENGINE:-mariadb}"
    local host="${DB_HOST_INPUT:-127.0.0.1}"
    local port="${DB_PORT_INPUT:-$(default_db_port "$engine")}"

    # Validate required fields up front so the operator sees the real reason
    # before we attempt to URL-encode anything.
    if [ -z "$DB_USER_INPUT" ]; then
        print_error "External DB user is empty (set --db-user or DB_USER_INPUT)."
        return 1
    fi
    if [ -z "$DB_PASSWORD_INPUT" ]; then
        print_error "External DB password is empty (set --db-password or DB_PASSWORD_INPUT)."
        return 1
    fi
    if [ -z "$DB_NAME_INPUT" ]; then
        print_error "External DB name is empty (set --db-name or DB_NAME_INPUT)."
        return 1
    fi
    if [ -z "$host" ]; then
        print_error "External DB host is empty (set --db-host or DB_HOST_INPUT)."
        return 1
    fi
    if [ -z "$port" ]; then
        print_error "External DB port is empty and no default known for engine '${engine}'."
        return 1
    fi

    local user_enc pass_enc db_enc
    # Propagate urlencode_dsn_part failures — half-built DSN with empty user/pass is worse than aborting.
    user_enc=$(urlencode_dsn_part "${DB_USER_INPUT}") || return 1
    pass_enc=$(urlencode_dsn_part "${DB_PASSWORD_INPUT}") || return 1
    db_enc=$(urlencode_dsn_part "${DB_NAME_INPUT}") || return 1

    local scheme query=""
    case "$engine" in
        mariadb)    scheme="mariadb+pymysql" ;;
        mysql)      scheme="mysql+pymysql" ;;
        postgresql) scheme="postgresql+psycopg" ;;
        *)
            print_error "build_external_db_dsn: unsupported engine '${engine}' (expected mariadb / mysql / postgresql)."
            return 1
            ;;
    esac

    if [ "$DB_SSL_INPUT" = "yes" ]; then
        case "$engine" in
            mariadb|mysql)
                if [ "$DB_SSL_VERIFY_INPUT" = "no" ]; then
                    query="?ssl=true&ssl_verify_cert=false"
                else
                    query="?ssl=true&ssl_verify_cert=true"
                fi
                ;;
            postgresql)
                if [ "$DB_SSL_VERIFY_INPUT" = "no" ]; then
                    query="?sslmode=require"
                else
                    query="?sslmode=verify-full"
                fi
                ;;
        esac
    fi

    printf '%s://%s:%s@%s:%s/%s%s' \
        "$scheme" "$user_enc" "$pass_enc" "$host" "$port" "$db_enc" "$query"
}

# Connectivity probe via native CLI. 0 = success or client missing, 1 = probe failed.
# Secret handling: password via 0600 option file (--defaults-extra-file / PGPASSFILE);
# never in argv or env. Files shredded after use.
check_external_db() {
    local engine="${DB_EXTERNAL_ENGINE:-mariadb}"
    local host="${DB_HOST_INPUT:-127.0.0.1}"
    local port="${DB_PORT_INPUT:-$(default_db_port "$engine")}"
    local _bin _rc=0 _tmp

    case "$engine" in
        mariadb|mysql)
            if command -v mariadb >/dev/null 2>&1; then
                _bin=mariadb
            elif command -v mysql >/dev/null 2>&1; then
                _bin=mysql
            else
                print_warning "${engine} client not installed locally — skipping connectivity probe."
                return 0
            fi
            _tmp=$(mktemp /tmp/bw-db-probe.XXXXXX) || return 1
            chmod 600 "$_tmp"
            # Register before write so SIGINT cleanup via EXIT trap still wipes it.
            _bw_register_secret_tmpfile "$_tmp"
            # Unquoted value in [client] — pymysql/mysql parse fine; validate_db_password rejected ' " \ `.
            {
                printf '[client]\n'
                printf 'user=%s\n' "$DB_USER_INPUT"
                printf 'password=%s\n' "$DB_PASSWORD_INPUT"
            } > "$_tmp"
            "$_bin" --defaults-extra-file="$_tmp" \
                -h "$host" -P "$port" \
                --connect-timeout=5 \
                -e "SELECT 1" "$DB_NAME_INPUT" >/dev/null 2>&1 || _rc=1
            shred -u "$_tmp" 2>/dev/null || rm -f "$_tmp"
            ;;
        postgresql)
            if ! command -v psql >/dev/null 2>&1; then
                print_warning "psql client not installed locally — skipping connectivity probe."
                return 0
            fi
            local _enc_user _enc_db _probe_uri
            _enc_user=$(urlencode_dsn_part "$DB_USER_INPUT") || return 1
            _enc_db=$(urlencode_dsn_part "$DB_NAME_INPUT") || return 1
            _probe_uri="postgresql://${_enc_user}@${host}:${port}/${_enc_db}"
            if [ "$DB_SSL_INPUT" = "yes" ]; then
                if [ "$DB_SSL_VERIFY_INPUT" = "no" ]; then
                    _probe_uri+="?sslmode=require"
                else
                    _probe_uri+="?sslmode=verify-full"
                fi
            fi
            # PGPASSFILE = host:port:database:user:password.
            # libpq strips brackets from IPv6 URIs BEFORE PGPASSFILE match — write unbracketed
            # else psql falls through to an interactive prompt and hangs under --yes.
            _tmp=$(mktemp /tmp/bw-pgpass.XXXXXX) || return 1
            chmod 600 "$_tmp"
            _bw_register_secret_tmpfile "$_tmp"
            local _pgpass_host="$host"
            if [[ "$_pgpass_host" == \[*\] ]]; then
                _pgpass_host="${_pgpass_host#[}"
                _pgpass_host="${_pgpass_host%]}"
            fi
            printf '%s:%s:%s:%s:%s\n' "$_pgpass_host" "$port" "$DB_NAME_INPUT" "$DB_USER_INPUT" "$DB_PASSWORD_INPUT" > "$_tmp"
            PGPASSFILE="$_tmp" PGCONNECT_TIMEOUT=5 \
                psql "$_probe_uri" -tAc "SELECT 1" >/dev/null 2>&1 || _rc=1
            shred -u "$_tmp" 2>/dev/null || rm -f "$_tmp"
            ;;
        *)
            return 0
            ;;
    esac

    return "$_rc"
}

# Local MariaDB + BunkerWeb-ready database/user.
install_mariadb() {
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}MariaDB Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing MariaDB"

    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt update
            run_cmd apt install -y mariadb-server
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux"|"centos")
            run_cmd dnf install -y mariadb-server
            ;;
        *)
            print_warning "MariaDB auto-install not supported on $DISTRO_ID. Skipping."
            return 1
            ;;
    esac

    # BunkerWeb tuning: max_allowed_packet=64M, bind loopback.
    local conf_dir conf_file
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            conf_dir=/etc/mysql/mariadb.conf.d
            ;;
        *)
            conf_dir=/etc/my.cnf.d
            ;;
    esac
    if [ ! -d "$conf_dir" ]; then
        mkdir -p "$conf_dir"
    fi
    conf_file="$conf_dir/99-bunkerweb.cnf"
    cat > "$conf_file" <<'EOF'
[mysqld]
bind-address = 127.0.0.1
max_allowed_packet = 64M
EOF
    chmod 644 "$conf_file"

    run_cmd systemctl enable --now mariadb

    # Wait briefly for the socket to come up.
    local _wait
    for _wait in 1 2 3 4 5; do
        if mariadb -u root -e 'SELECT 1' >/dev/null 2>&1 \
           || mysql -u root -e 'SELECT 1' >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if [ -z "$DB_PASSWORD_INPUT" ]; then
        DB_PASSWORD_INPUT=$(generate_secret 32)
        DB_PASSWORD_GENERATED="$DB_PASSWORD_INPUT"
    fi

    local mariadb_bin
    if command -v mariadb >/dev/null 2>&1; then
        mariadb_bin=mariadb
    else
        mariadb_bin=mysql
    fi

    print_status "Bootstrapping MariaDB database and user"
    "$mariadb_bin" -u root <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME_INPUT}\` CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS '${DB_USER_INPUT}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD_INPUT}';
ALTER USER '${DB_USER_INPUT}'@'127.0.0.1' IDENTIFIED BY '${DB_PASSWORD_INPUT}';
GRANT ALL PRIVILEGES ON \`${DB_NAME_INPUT}\`.* TO '${DB_USER_INPUT}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

    # URL-encode every credential / identifier component so passwords containing
    # @, /, :, % … don't break the SQLAlchemy DSN parser. validate_db_password
    # already blocks ' " \ ` but the DSN reserved set is broader.
    local _du _dp _dn
    _du=$(urlencode_dsn_part "$DB_USER_INPUT") || return 1
    _dp=$(urlencode_dsn_part "$DB_PASSWORD_INPUT") || return 1
    _dn=$(urlencode_dsn_part "$DB_NAME_INPUT") || return 1
    DB_DSN_GENERATED="mariadb+pymysql://${_du}:${_dp}@127.0.0.1:3306/${_dn}"

    # Pick up our snippet.
    run_cmd systemctl restart mariadb

    echo
    echo -e "${GREEN}MariaDB installed and bootstrapped${NC}"
    echo -e "${BLUE}========================================${NC}"
    return 0
}

# Local PostgreSQL + BunkerWeb-ready database/user.
install_postgresql() {
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}PostgreSQL Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing PostgreSQL"

    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt update
            run_cmd apt install -y postgresql
            ;;
        "fedora")
            run_cmd dnf install -y postgresql-server postgresql-contrib
            if [ ! -d /var/lib/pgsql/data/base ]; then
                run_cmd postgresql-setup --initdb
            fi
            ;;
        "rhel"|"rocky"|"almalinux"|"centos")
            run_cmd dnf install -y postgresql-server postgresql-contrib
            if [ ! -d /var/lib/pgsql/data/base ]; then
                run_cmd postgresql-setup --initdb
            fi
            ;;
        *)
            print_warning "PostgreSQL auto-install not supported on $DISTRO_ID. Skipping."
            return 1
            ;;
    esac

    run_cmd systemctl enable --now postgresql

    # Wait for the socket.
    local _wait
    for _wait in 1 2 3 4 5; do
        if sudo -u postgres psql -tAc 'SELECT 1' >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if [ -z "$DB_PASSWORD_INPUT" ]; then
        DB_PASSWORD_INPUT=$(generate_secret 32)
        DB_PASSWORD_GENERATED="$DB_PASSWORD_INPUT"
    fi

    print_status "Bootstrapping PostgreSQL database and role"

    # Idempotent role. Password-bearing statements via stdin (not `psql -c`) — plaintext stays out of argv.
    # USER/NAME validated to [A-Za-z_][A-Za-z0-9_]*; pw rejects ' " \ ` → safe to single-quote.
    local user_exists db_exists
    user_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER_INPUT}'" 2>/dev/null || true)
    if [ "$user_exists" != "1" ]; then
        sudo -u postgres psql <<SQL
CREATE ROLE "${DB_USER_INPUT}" LOGIN PASSWORD '${DB_PASSWORD_INPUT}';
SQL
    else
        sudo -u postgres psql <<SQL
ALTER ROLE "${DB_USER_INPUT}" WITH LOGIN PASSWORD '${DB_PASSWORD_INPUT}';
SQL
    fi

    db_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME_INPUT}'" 2>/dev/null || true)
    if [ "$db_exists" != "1" ]; then
        sudo -u postgres psql -c "CREATE DATABASE \"${DB_NAME_INPUT}\" OWNER \"${DB_USER_INPUT}\";"
    fi

    # Ensure pg_hba.conf allows md5 from 127.0.0.1/32 for our user.
    local pg_hba
    pg_hba=$(sudo -u postgres psql -tAc 'SHOW hba_file' 2>/dev/null || true)
    if [ -n "$pg_hba" ] && [ -f "$pg_hba" ]; then
        if ! grep -qE "^[^#]*${DB_USER_INPUT}[[:space:]]+127\\.0\\.0\\.1/32" "$pg_hba"; then
            printf '\nhost    %s    %s    127.0.0.1/32    md5\n' "$DB_NAME_INPUT" "$DB_USER_INPUT" >> "$pg_hba"
            run_cmd systemctl reload postgresql
        fi
    fi

    local _du _dp _dn
    _du=$(urlencode_dsn_part "$DB_USER_INPUT") || return 1
    _dp=$(urlencode_dsn_part "$DB_PASSWORD_INPUT") || return 1
    _dn=$(urlencode_dsn_part "$DB_NAME_INPUT") || return 1
    DB_DSN_GENERATED="postgresql+psycopg://${_du}:${_dp}@127.0.0.1:5432/${_dn}"

    echo
    echo -e "${GREEN}PostgreSQL installed and bootstrapped${NC}"
    echo -e "${BLUE}========================================${NC}"
    return 0
}

# Dispatch to MariaDB/Postgres/external installer and write DSN.
install_database() {
    case "$DB_INSTALL" in
        "mariadb")
            if install_mariadb; then
                apply_db_config "$DB_DSN_GENERATED"
            else
                print_warning "Falling back to SQLite — set DATABASE_URI manually if you need a different DB."
                DB_INSTALL="none"
            fi
            ;;
        "postgresql")
            if install_postgresql; then
                apply_db_config "$DB_DSN_GENERATED"
            else
                print_warning "Falling back to SQLite — set DATABASE_URI manually if you need a different DB."
                DB_INSTALL="none"
            fi
            ;;
        "external")
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}External Database${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo

            DB_DSN_GENERATED=$(build_external_db_dsn) || {
                print_error "Could not build external database DSN — aborting."
                exit 1
            }

            if [ "$DB_SKIP_PROBE" = "yes" ]; then
                print_status "Skipping external DB connectivity probe (--db-skip-probe)."
            else
                print_step "Probing connectivity to ${DB_EXTERNAL_ENGINE} at ${DB_HOST_INPUT}:${DB_PORT_INPUT}"
                if check_external_db; then
                    print_status "External database reachable."
                else
                    print_warning "Could not reach the database with the provided credentials."
                    if [ "$INTERACTIVE_MODE" = "yes" ]; then
                        _tui_explain "Connectivity probe failed. The credentials may still be correct:
  • the engine client (mariadb / psql) might be missing on this host
  • a firewall may block the probe but not the scheduler
  • the DB may not yet be reachable from this network segment

The DSN will be written either way; the scheduler will surface the
real connection error on first boot if the credentials are wrong."
                        if ! tui_yesno "External Database — Continue?" \
                            "🌐 Write the DSN to /etc/bunkerweb/variables.env anyway?" "no"; then
                            print_error "Aborting at user request."
                            exit 1
                        fi
                    else
                        print_error "Non-interactive mode: external DB probe failed and --db-skip-probe was not set."
                        print_error "Either fix the credentials, install the engine client on this host,"
                        print_error "or re-run with --db-skip-probe to assert the DSN is correct."
                        exit 1
                    fi
                fi
            fi

            apply_db_config "$DB_DSN_GENERATED"
            echo -e "${GREEN}External database wired into /etc/bunkerweb/variables.env${NC}"
            echo -e "${BLUE}========================================${NC}"
            ;;
        *)
            : # nothing to do
            ;;
    esac
}

# UI admin via ui.env. gunicorn pre-fork reads ADMIN_USERNAME/PASSWORD on first start;
# OVERRIDE_ADMIN_CREDS=yes → idempotent across re-runs.
create_ui_admin_user() {
    local ui_env=/etc/bunkerweb/ui.env

    if [ -z "$UI_ADMIN_USERNAME_INPUT" ]; then
        UI_ADMIN_USERNAME_INPUT="admin"
    fi

    if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
        UI_ADMIN_PASSWORD_INPUT=$(generate_ui_admin_password)
        UI_ADMIN_PASSWORD_GENERATED="$UI_ADMIN_PASSWORD_INPUT"
    fi

    if ! validate_ui_admin_password "$UI_ADMIN_PASSWORD_INPUT"; then
        print_warning "Provided admin password does not meet the BunkerWeb rules; auto-generating one instead."
        UI_ADMIN_PASSWORD_INPUT=$(generate_ui_admin_password)
        UI_ADMIN_PASSWORD_GENERATED="$UI_ADMIN_PASSWORD_INPUT"
    fi

    write_default_ui_env_template "$ui_env"
    set_config_kv "$ui_env" "OVERRIDE_ADMIN_CREDS" "yes"
    set_config_kv "$ui_env" "ADMIN_USERNAME" "$UI_ADMIN_USERNAME_INPUT"
    set_config_kv "$ui_env" "ADMIN_PASSWORD" "$UI_ADMIN_PASSWORD_INPUT"

    print_status "Web UI admin user provisioned (${UI_ADMIN_USERNAME_INPUT})"
}

# Self-signed cert + gunicorn-native TLS on the manager UI listener.
setup_ui_selfsigned_tls() {
    local tls_dir=/var/lib/bunkerweb/ui-tls
    local cert="$tls_dir/cert.pem"
    local key="$tls_dir/key.pem"
    local ui_env=/etc/bunkerweb/ui.env
    local fqdn short cn primary_ip san

    # CN DN-safe; DNS SANs match RFC 1035 (alnum/dot/dash).
    fqdn=$(hostname -f 2>/dev/null || true)
    short=$(hostname 2>/dev/null || true)
    fqdn=${fqdn//[^A-Za-z0-9.-]/}
    short=${short//[^A-Za-z0-9.-]/}
    cn="${fqdn:-${short:-bunkerweb-manager}}"

    primary_ip=$(get_primary_ipv4)

    # SAN covers all plausible operator-facing addrs.
    san="DNS:${cn},DNS:localhost,IP:127.0.0.1,IP:::1"
    if [ -n "$short" ] && [ "$short" != "$cn" ]; then
        san="${san},DNS:${short}"
    fi
    if [ -n "$primary_ip" ] && [ "$primary_ip" != "127.0.0.1" ]; then
        san="${san},IP:${primary_ip}"
    fi

    if ! command -v openssl >/dev/null 2>&1; then
        case "$DISTRO_ID" in
            "debian"|"ubuntu") run_cmd apt install -y openssl ;;
            "fedora"|"rhel"|"rocky"|"almalinux"|"centos") run_cmd dnf install -y openssl ;;
            "freebsd") run_cmd pkg install -y openssl ;;
        esac
    fi

    mkdir -p "$tls_dir"
    chmod 750 "$tls_dir"
    chown root:nginx "$tls_dir" 2>/dev/null || true

    print_step "Generating self-signed TLS certificate (CN=${cn}, SAN=${san})"
    # RSA 3072 per NIST SP 800-57 (2048 sunsets 2030; 3072 = 128-bit security, OpenSSL ≥ 1.0.2).
    run_cmd openssl req -x509 -nodes -newkey rsa:3072 -days 365 \
        -subj "/CN=${cn}" \
        -addext "subjectAltName=${san}" \
        -addext "basicConstraints=critical,CA:FALSE" \
        -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" \
        -keyout "$key" \
        -out "$cert"

    chown root:nginx "$cert" "$key" 2>/dev/null || true
    chmod 640 "$cert" "$key" 2>/dev/null || true

    write_default_ui_env_template "$ui_env"
    set_config_kv "$ui_env" "UI_SSL_ENABLED" "yes"
    set_config_kv "$ui_env" "UI_SSL_CERTFILE" "$cert"
    set_config_kv "$ui_env" "UI_SSL_KEYFILE" "$key"

    print_status "Self-signed HTTPS enabled for the manager Web UI"
}

# Manager UI hardening + explicit start. Called after configure_manager_api_defaults.
start_manager_ui() {
    if [ "${SERVICE_UI:-yes}" = "no" ]; then
        return
    fi

    if [ "$UI_ADMIN_CREATE" = "yes" ]; then
        create_ui_admin_user
    fi

    if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
        setup_ui_selfsigned_tls
    fi

    if [ "$DISTRO_ID" = "freebsd" ]; then
        sysrc bunkerweb_ui_enable=YES >/dev/null 2>&1
        service bunkerweb_ui restart || service bunkerweb_ui start || true
    else
        run_cmd systemctl enable --now bunkerweb-ui
        # Restart if hardening landed after a previous start.
        if [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
            run_cmd systemctl restart bunkerweb-ui
        fi
    fi
}

get_current_bunkerweb_version() {
    local _version=""
    if [ -f /usr/share/bunkerweb/VERSION ]; then
        _version=$(cat /usr/share/bunkerweb/VERSION 2>/dev/null || true)
    fi
    printf '%s' "${_version:-${BUNKERWEB_VERSION:-unknown}}"
}

get_installed_nginx_version() {
    local _raw="" _version=""
    if command -v nginx >/dev/null 2>&1; then
        _raw=$(nginx -v 2>&1 || true)
        _version="${_raw#nginx version: nginx/}"
        if [ -n "$_version" ] && [ "$_version" != "$_raw" ]; then
            printf '%s' "$_version"
            return 0
        fi
    fi

    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            if command -v dpkg-query >/dev/null 2>&1; then
                _version=$(dpkg-query -W -f='${Version}' nginx 2>/dev/null || true)
            fi
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux"|"centos")
            if command -v rpm >/dev/null 2>&1; then
                if rpm -q nginx >/dev/null 2>&1; then
                    _version=$(rpm -q --qf '%{VERSION}-%{RELEASE}' nginx 2>/dev/null || true)
                fi
            fi
            ;;
        "freebsd")
            if command -v pkg >/dev/null 2>&1; then
                _version=$(pkg info -q nginx 2>/dev/null || true)
                _version="${_version#nginx-}"
            fi
            ;;
    esac

    printf '%s' "${_version:-unknown}"
}

show_final_info() {
    local _current_bw_version="" _nginx_version=""

    echo
    echo "========================================="
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        _current_bw_version=$(get_current_bunkerweb_version)
        _nginx_version=$(get_installed_nginx_version)

        echo -e "${GREEN}BunkerWeb Upgrade Complete!${NC}"
    else
        echo -e "${GREEN}BunkerWeb Installation Complete!${NC}"
    fi
    echo "========================================="
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        echo
        echo "Upgrade summary:"
        echo "  - Previous BunkerWeb version: ${INSTALLED_VERSION:-unknown}"
        echo "  - New BunkerWeb version: ${_current_bw_version:-unknown}"
        echo "  - Current NGINX version: ${_nginx_version:-unknown}"
    fi
    echo
    echo "Services status:"

    if [ "$DISTRO_ID" = "freebsd" ]; then
        service bunkerweb status 2>/dev/null || true
        service bunkerweb_scheduler status 2>/dev/null || true
        if [ -f /usr/local/etc/rc.d/bunkerweb_api ]; then
            service bunkerweb_api status 2>/dev/null || true
        fi
        if [ "$ENABLE_WIZARD" = "yes" ]; then
            service bunkerweb_ui status 2>/dev/null || true
        fi
    else
        systemctl status bunkerweb --no-pager -l || true
        systemctl status bunkerweb-scheduler --no-pager -l || true
        if systemctl list-units --type=service --all | grep -q '^bunkerweb-api.service'; then
            systemctl status bunkerweb-api --no-pager -l || true
        fi
        if [ "$ENABLE_WIZARD" = "yes" ]; then
            systemctl status bunkerweb-ui --no-pager -l || true
        fi
    fi

    echo
    echo "Configuration:"
    echo "  - Main config: /etc/bunkerweb/variables.env"

    if [ "$ENABLE_WIZARD" = "yes" ]; then
        echo "  - UI config: /etc/bunkerweb/ui.env"
    fi

    echo "  - Scheduler config: /etc/bunkerweb/scheduler.env"

    if [ "$DISTRO_ID" = "freebsd" ]; then
        if [ "${SERVICE_API:-no}" = "yes" ] || [ -f /usr/local/etc/rc.d/bunkerweb_api ]; then
            echo "  - API config: /etc/bunkerweb/api.env"
        fi
    else
        if [ "${SERVICE_API:-no}" = "yes" ] || systemctl list-units --type=service --all | grep -q '^bunkerweb-api.service'; then
            echo "  - API config: /etc/bunkerweb/api.env"
        fi
    fi
    echo "  - Logs: /var/log/bunkerweb/"
    echo

    if [ "$DISTRO_ID" = "freebsd" ]; then
        echo "FreeBSD Notes:"
        echo "  - Services are managed via rc.d: service bunkerweb start|stop|restart"
        echo "  - Enable services in /etc/rc.conf: sysrc bunkerweb_enable=YES"
        echo "  - View logs: tail -f /var/log/bunkerweb/error.log /var/log/bunkerweb/access.log"
        echo
    fi

    # Honour --server-ip; otherwise auto-detect (prompts only on multiple global IPv4s).
    resolve_display_server_ip
    local _server_ip="${RESOLVED_SERVER_IP:-your-server-ip}"
    local _ui_scheme="http" _ui_host="$_server_ip"
    if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
        _ui_scheme="https"
        _ui_host="127.0.0.1"
    fi
    case "$INSTALL_TYPE" in
        "manager")
            echo "Next steps:"
            if [ -n "$DB_DSN_GENERATED" ]; then
                echo "  1. Database is already configured (see credentials block below)."
            else
                echo "  1. Configure database connection in /etc/bunkerweb/scheduler.env"
                echo "     Set DATABASE_URI (e.g., sqlite:///var/lib/bunkerweb/db.sqlite3)"
            fi
            echo "  2. Verify BUNKERWEB_INSTANCES is set to: $BUNKERWEB_INSTANCES_INPUT"
            if [ "${SERVICE_UI:-yes}" != "no" ]; then
                echo "  3. Access the Web UI at: ${_ui_scheme}://${_ui_host}:7000"
                if [ "$UI_SELFSIGNED_INPUT" = "yes" ] || [ "${REDIS_INSTALL}" = "yes" ]; then
                    echo "     (UI is local-only by default; tunnel SSH or place a reverse proxy in front for remote access.)"
                fi
                echo "  4. Use the UI to manage your BunkerWeb workers"
            else
                echo "     (UI service start was deferred via --no-ui-service / SERVICE_UI=no.)"
                if [ "$DISTRO_ID" = "freebsd" ]; then
                    echo "  3. Start the Web UI: service bunkerweb_ui start"
                else
                    echo "  3. Start the Web UI: systemctl start bunkerweb-ui"
                fi
                echo "  4. Access the UI at: ${_ui_scheme}://${_ui_host}:7000"
            fi
            echo
            echo "📝 Manager mode information:"
            echo "  • The scheduler orchestrates configuration across all workers"
            echo "  • Workers must have their API accessible on port 5000 (default)"
            echo "  • Ensure workers whitelist this manager's IP: $MANAGER_IP_INPUT"
            echo "  • Use multisite mode: MULTISITE=yes for multiple services"
            if [ "$REDIS_INSTALL" = "yes" ]; then
                echo "  • ${REDIS_FLAVOR:-redis} is configured: metrics and bans persist across restarts and are shared between workers"
            fi
            ;;
        "worker")
            echo "Next steps:"
            echo "  1. Verify this worker's API is accessible from the manager"
            echo "     Default API port: 5000 (configured via API_HTTP_PORT)"
            echo "  2. Ensure firewall allows connections from: $MANAGER_IP_INPUT"
            echo "  3. Configuration will be pushed automatically from the manager"
            echo
            echo "📝 Worker mode information:"
            echo "  • This instance is managed remotely by the scheduler"
            echo "  • API_WHITELIST_IP is configured to allow: $MANAGER_IP_INPUT"
            echo "  • API listens on: 0.0.0.0:5000 (whitelisting enforces access control)"
            echo "  • Local config changes in /etc/bunkerweb/variables.env may be overwritten"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  • Check logs: tail -f /var/log/bunkerweb/error.log /var/log/bunkerweb/access.log"
            else
                echo "  • Check logs: journalctl -u bunkerweb -f"
            fi
            ;;
        "scheduler")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/variables.env"
            echo "     Set DATABASE_URI (canonical location; sourced by every component)"
            echo "  2. Verify BUNKERWEB_INSTANCES is set to: $BUNKERWEB_INSTANCES_INPUT"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  3. Restart scheduler: service bunkerweb_scheduler restart"
            else
                echo "  3. Restart scheduler: systemctl restart bunkerweb-scheduler"
            fi
            echo "  4. Use 'bwcli' commands to manage the cluster"
            echo
            echo "📝 Scheduler-only mode information:"
            echo "  • Workers' internal Lua API listens on port 5000 (set via API_HTTP_PORT)"
            echo "  • Install the Web UI separately for graphical management"
            echo "  • All instances must share the same database backend"
            ;;
        "ui")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/variables.env"
            echo "     Set DATABASE_URI to the same database as your scheduler"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  2. Restart the UI: service bunkerweb_ui restart"
            else
                echo "  2. Restart the UI: systemctl restart bunkerweb-ui"
            fi
            echo "  3. Access the Web UI at: http://${_server_ip}:7000"
            echo
            echo "📝 UI-only mode information:"
            echo "  • The UI must connect to the same database as the scheduler"
            echo "  • Requires an existing scheduler instance managing workers"
            echo "  • Default UI port: 7000"
            ;;
        "api")
            echo "Next steps:"
            echo "  1. Configure API listener in /etc/bunkerweb/api.env"
            echo "     LISTEN_ADDR (default 127.0.0.1) and LISTEN_PORT (default 8888)"
            echo "  2. Configure database connection in /etc/bunkerweb/variables.env"
            echo "     Set DATABASE_URI to the same database as your scheduler"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  3. Restart the API: service bunkerweb_api restart"
            else
                echo "  3. Restart the API: systemctl restart bunkerweb-api"
            fi
            echo "  4. The API will be available at: http://${_server_ip}:8888"
            echo "     (Default LISTEN_ADDR is 127.0.0.1 — change to 0.0.0.0 in api.env"
            echo "      to expose externally; configure firewall accordingly.)"
            echo
            echo "📝 API-only mode information:"
            echo "  • The API service provides programmatic access to BunkerWeb"
            echo "  • Must connect to the same database as scheduler/UI"
            echo "  • Default API port: 8888 (FastAPI service, not internal Lua API)"
            echo "  • Configure API_TOKEN in api.env for bearer-token authentication"
            ;;
        "full"|*)
            if [ "$ENABLE_WIZARD" = "yes" ]; then
                echo "Next steps:"
                echo "  1. Access the setup wizard at: https://${_server_ip}/setup"
                echo "  2. Follow the configuration wizard to complete setup"
                echo
                echo "📝 Setup wizard information:"
                echo "  • The wizard guides you through initial configuration"
                echo "  • Configure your first protected service"
                echo "  • Set up SSL/TLS certificates automatically"
                echo "  • Access the management UI after completion"
            else
                echo "Next steps:"
                echo "  1. Edit /etc/bunkerweb/variables.env to configure BunkerWeb"
                echo "  2. Add your server settings and protected services"
                if [ "$DISTRO_ID" = "freebsd" ]; then
                    echo "  3. Restart services: service bunkerweb restart && service bunkerweb_scheduler restart"
                else
                    echo "  3. Restart services: systemctl restart bunkerweb bunkerweb-scheduler"
                fi
                echo
                echo "📝 Manual configuration:"
                if [ -n "$DB_DSN_GENERATED" ]; then
                    case "$DB_INSTALL" in
                        "mariadb")    echo "  • Database: MariaDB (auto-installed; credentials below)" ;;
                        "postgresql") echo "  • Database: PostgreSQL (auto-installed; credentials below)" ;;
                    esac
                else
                    echo "  • Default database: SQLite (upgrade to MariaDB/PostgreSQL for production)"
                fi
                echo "  • Use 'bwcli' for command-line management"
                if [ "$DISTRO_ID" = "freebsd" ]; then
                    echo "  • Check logs: tail -f /var/log/bunkerweb/error.log /var/log/bunkerweb/access.log"
                else
                    echo "  • Check logs: journalctl -u bunkerweb -f"
                fi
                echo "  • Access Web UI (if enabled): http://${_server_ip}:7000"
                if [ "$REDIS_INSTALL" = "yes" ]; then
                    echo "  • ${REDIS_FLAVOR:-redis} is configured: metrics and bans persist across restarts and are shared between workers"
                fi
            fi
            ;;
    esac
    echo

    # RHEL DB-client hints — only when no DB auto-installed.
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]] && [ -z "$DB_DSN_GENERATED" ]; then
        echo "💾 Database clients for external databases:"
        echo "  • MariaDB: dnf install mariadb"
        echo "  • MySQL: dnf install mysql"
        echo "  • PostgreSQL: dnf install postgresql"
        echo
    fi

    # Auto-installed credentials (printed once — save now if needed)
    if [ -n "$DB_DSN_GENERATED" ]; then
        local _db_engine _db_port
        case "$DB_INSTALL" in
            "mariadb")    _db_engine="MariaDB";    _db_port="3306" ;;
            "postgresql") _db_engine="PostgreSQL"; _db_port="5432" ;;
            *)            _db_engine="?";          _db_port="?" ;;
        esac
        # Restore saved stdout fd under --quiet so auto-gen passwords reach the operator.
        {
        echo "💾 Database (auto-installed):"
        echo "  Engine:   ${_db_engine}"
        echo "  Host:     127.0.0.1:${_db_port}"
        echo "  Database: ${DB_NAME_INPUT}"
        echo "  User:     ${DB_USER_INPUT}"
        if [ -n "$DB_PASSWORD_GENERATED" ]; then
            echo "  Password: ${DB_PASSWORD_GENERATED}"
            echo "  ⚠️  This password is stored in /etc/bunkerweb/variables.env. Save it now if you need it elsewhere."
            echo "       Retrieve later with: sudo grep ^DATABASE_URI /etc/bunkerweb/variables.env"
        else
            echo "  Password: (the value you provided)"
        fi
        echo "  DSN:      written to /etc/bunkerweb/variables.env"
        echo
        } >&"${_BW_OUT_FD:-1}"
    fi

    if [ -n "$UI_ADMIN_PASSWORD_GENERATED" ] || [ "$UI_ADMIN_CREATE" = "yes" ]; then
        {
        echo "👤 Web UI admin user:"
        echo "  Username: ${UI_ADMIN_USERNAME_INPUT:-admin}"
        if [ -n "$UI_ADMIN_PASSWORD_GENERATED" ]; then
            echo "  Password: ${UI_ADMIN_PASSWORD_GENERATED}"
            echo "  ⚠️  Save this password now."
        else
            echo "  Password: (the value you provided)"
        fi
        echo
        } >&"${_BW_OUT_FD:-1}"
    fi

    if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
        {
        echo "🔒 Web UI HTTPS (self-signed):"
        echo "  URL:  https://127.0.0.1:7000/   (accept the self-signed warning in your browser)"
        echo "  Cert: /var/lib/bunkerweb/ui-tls/cert.pem"
        echo "  Key:  /var/lib/bunkerweb/ui-tls/key.pem"
        echo
        } >&"${_BW_OUT_FD:-1}"
    fi

    if [ -n "$REDIS_REQUIREPASS_LOCAL" ]; then
        {
        echo "🔑 ${REDIS_FLAVOR:-redis} REQUIREPASS:"
        if [ -n "$REDIS_PASSWORD_GENERATED" ]; then
            echo "  Password: ${REDIS_PASSWORD_GENERATED}   (auto-generated)"
            echo "  Stored in the ${REDIS_FLAVOR:-redis} config and in /etc/bunkerweb/variables.env."
            echo "  ⚠️  Save it now and restrict port 6379 to your worker subnet."
        else
            echo "  Password: (the value you provided)"
            echo "  Stored in the ${REDIS_FLAVOR:-redis} config and in /etc/bunkerweb/variables.env."
            echo "  ⚠️  Restrict port 6379 to your worker subnet."
        fi
        echo "       Example (ufw): sudo ufw allow from 10.0.0.0/24 to any port 6379"
        echo
        } >&"${_BW_OUT_FD:-1}"
    fi

    echo "📚 Resources:"
    echo "  • Documentation: https://docs.bunkerweb.io"
    echo "  • Community support: https://discord.bunkerity.com"
    echo "  • Commercial support: https://panel.bunkerweb.io/store/support"
    echo "========================================="
}

usage() {
    echo "BunkerWeb Easy Install Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -v, --version VERSION    BunkerWeb version to install (default: ${DEFAULT_BUNKERWEB_VERSION})"
    echo "  -w, --enable-wizard      Enable the setup wizard (default in interactive mode)"
    echo "  -n, --no-wizard          Disable the setup wizard"
    echo "  -y, --yes                Non-interactive mode, use defaults"
    echo "      --tui                Force a TUI (gum or whiptail). Hard fail if neither can be installed."
    echo "      --no-tui             Disable all TUI layers and use the legacy plain-read prompts."
    echo "      --api, --enable-api  Enable the FastAPI service (bunkerweb-api.service, port 8888;"
    echo "                           disabled by default on Linux). Distinct from the internal Lua"
    echo "                           API used between scheduler and workers (see --api-https)."
    echo "      --no-api             Explicitly disable the API service"
    echo "  -f, --force              Force installation on unsupported OS versions"
    echo "      --force-type-change  Allow --type X to differ from the detected install type"
    echo "                           on upgrade (use for intentional HA migrations only)"
    echo "  -q, --quiet              Silent installation (suppress output; implies --yes)"
    echo "  -h, --help               Show this help message"
    echo "      --dry-run            Show what would be installed without doing it"
    echo "      --restart-install    Discard any saved state from an interrupted run and start fresh"
    echo
    echo "Installation types (apply to both Linux and Docker):"
    echo "  --full                   Full stack installation (default)"
    echo "  --manager                Manager installation (Scheduler + UI)"
    echo "  --worker                 Worker installation (BunkerWeb only)"
    echo "  --scheduler-only         Scheduler only installation"
    echo "  --ui-only                Web UI only installation"
    echo "  --api-only               FastAPI service only installation (port 8888)"
    echo
    echo "Deployment platform:"
    echo "  --docker                 Deploy as a docker-compose stack instead of host packages"
    echo "                           (combine with an install type, e.g. --docker --manager)"
    echo
    echo "Docker mode options (with --docker):"
    echo "  --autoconf               Add the autoconf integration (full type only)"
    echo "  --no-autoconf            Do not add the autoconf integration (default)"
    echo "  --image-tag TAG          Docker Hub image tag (default: derived from --version)"
    echo "  --compose-dir PATH       Directory for docker-compose.yml + .env (default: current dir)"
    echo "  --overwrite-compose      Back up and overwrite existing compose files without prompting"
    echo "  --install-docker         Install Docker via the official convenience script if missing"
    echo "  --no-pull                Skip 'docker compose pull' before starting the stack"
    echo "  --docker-wait-timeout N  Seconds to wait for the stack to become ready (default: 180)"
    echo "  --http-port N            Host HTTP port      (default: 80;   bunkerweb)"
    echo "  --https-port N           Host HTTPS/QUIC port (default: 443; bunkerweb)"
    echo "  --api-port N             Host worker-API port (default: 5000; worker)"
    echo "  --ui-port N              Host Web UI port    (default: 7000; manager/ui)"
    echo "  --fastapi-port N         Host FastAPI port   (default: 8888; api)"
    echo "                           (remap these to run several stacks on one host)"
    echo "  --api-token TOKEN        Shared API token (required for non-interactive"
    echo "                           --docker manager/worker/scheduler — same on every host)"
    echo "  --database-uri URI       External DATABASE_URI (required for non-interactive"
    echo "                           --docker scheduler/ui/api types)"
    echo
    echo "Security integrations:"
    echo "  --crowdsec               Install and configure CrowdSec"
    echo "  --no-crowdsec            Skip CrowdSec installation"
    echo "  --crowdsec-appsec        Install CrowdSec with AppSec component"
    echo "  --redis                  Install and configure Redis (or Valkey, see --redis-flavor)"
    echo "  --no-redis               Skip Redis installation"
    echo "  --redis-flavor FLAVOR    Local install flavor: redis (default) or valkey"
    echo
    echo "Database (full + manager):"
    echo "  --database ENGINE        DB strategy: mariadb, postgresql (local install),"
    echo "                           external (connect to an existing remote DB), or none (SQLite)"
    echo "  --db-engine ENGINE       External-DB engine: mariadb, mysql, or postgresql"
    echo "  --db-host HOST           External DB host (FQDN or IP)"
    echo "  --db-port PORT           External DB TCP port (default per engine: 3306 / 5432)"
    echo "  --db-name NAME           Database name (default: ${DB_NAME_INPUT})"
    echo "  --db-user USER           Database user (default: ${DB_USER_INPUT})"
    echo "  --db-password PASS       Database password (default: auto-generated for local install,"
    echo "                           required for --database external; rules: 8+ chars, no quotes/backslash/backtick)"
    echo "  --db-ssl                 Use SSL/TLS for the external DB connection"
    echo "  --db-no-ssl              Do not use SSL/TLS for the external DB connection"
    echo "  --db-ssl-verify          Verify the external DB server certificate"
    echo "  --db-no-ssl-verify       Skip server certificate verification (ssl=true but verify=false)"
    echo "  --db-skip-probe          Do not probe external DB connectivity from this host"
    echo "                           (operator asserts DSN is correct — useful when the engine"
    echo "                           client is not installed locally or the DB is only reachable"
    echo "                           from the scheduler's network)"
    echo
    echo "Web UI admin user (full + manager + ui-only):"
    echo "  --ui-admin-user NAME     Create the first Web UI admin user with this name"
    echo "  --ui-admin-password PASS Password for --ui-admin-user (default: auto-generated;"
    echo "                           rules: 8+ chars, one lowercase, one uppercase, one digit, one special)"
    echo "  --no-ui-admin            Skip the admin-user creation prompt"
    echo
    echo "Manager UI hardening (manager only):"
    echo "  --ui-https-selfsigned    Generate a self-signed cert and enable UI HTTPS"
    echo "  --no-ui-https-selfsigned Disable manager UI self-signed HTTPS"
    echo
    echo "Advanced options:"
    echo "  --instances \"IP1 IP2\"    Space-separated list of BunkerWeb instances"
    echo "                           (optional for --manager and --scheduler-only)"
    echo "  --manager-ip IPs         Manager/Scheduler IPs to whitelist (required for --worker in non-interactive mode, overrides auto-detect for --manager)"
    echo "  --server-ip IP|FQDN      Host advertised in post-install URLs (IPv4 or hostname; overrides auto-detection; can also be set via SERVER_IP_INPUT)"
    echo "  --dns-resolvers \"IP1 IP2\"  Custom DNS resolver IPs (for --full, --manager, --worker)"
    echo "  --api-https              Enable HTTPS for the internal Lua API (port 5000, scheduler↔worker;"
    echo "                           default: HTTP only). Unrelated to the FastAPI service (--api)."
    echo "  --backup-dir PATH        Directory to store automatic backup before upgrade"
    echo "  --no-auto-backup         Skip automatic backup (you MUST have done it manually)"
    echo "  --redis-host HOST        Redis host for existing server"
    echo "  --redis-port PORT        Redis port for existing server"
    echo "  --redis-database DB      Redis database number"
    echo "  --redis-username USER    Redis username"
    echo "  --redis-password PASS    Redis password"
    echo "  --redis-bind IP          Redis bind address for local install (manager mode; default 0.0.0.0)"
    echo "  --redis-no-password      Skip the auto-generated REQUIREPASS when binding ≠ loopback"
    echo "  --redis-maxmemory MB     Memory cap in MB (e.g. 128, 256, 512, 1024); 0/unlimited keeps distro default"
    echo "  --redis-maxmemory-policy POLICY  Eviction policy (default volatile-lru). Other valid: allkeys-lru, volatile-ttl, noeviction, ..."
    echo "  --redis-ssl              Enable SSL/TLS for Redis connection"
    echo "  --redis-no-ssl           Disable SSL/TLS for Redis connection"
    echo "  --redis-ssl-verify       Verify Redis SSL certificate"
    echo "  --redis-no-ssl-verify    Do not verify Redis SSL certificate"
    echo "  --epel                   Install epel-release on RHEL-family distros if missing"
    echo "  --no-epel                Do not install epel-release on RHEL-family distros"
    echo
    echo "Examples:"
    echo "  $0                       # Interactive installation"
    echo "  $0 --no-wizard           # Install without setup wizard"
    echo "  $0 --version 1.6.0       # Install specific version"
    echo "  $0 --yes                 # Non-interactive with defaults"
    echo "  $0 --force               # Force install on unsupported OS"
    echo "  $0 --manager --instances \"192.168.1.10 192.168.1.11\""
    echo "                           # Manager setup with worker instances"
    echo "  $0 --worker --manager-ip 10.20.30.40"
    echo "                           # Worker installation with manager IP"
    echo "  $0 --dns-resolvers \"1.1.1.1 1.0.0.1\""
    echo "                           # Use Cloudflare DNS resolvers"
    echo "  $0 --manager --instances \"192.168.1.10 192.168.1.11\" --api-https"
    echo "                           # Manager with workers over HTTPS"
    echo "  $0 --crowdsec-appsec     # Full installation with CrowdSec AppSec"
    echo "  $0 --quiet --yes         # Silent non-interactive installation"
    echo "  $0 --dry-run             # Preview installation without executing"
    echo "  $0 --docker              # Generate and run a full Docker compose stack"
    echo "  $0 --docker --full --autoconf --yes"
    echo "                           # Non-interactive Docker full stack with autoconf"
    echo "  $0 --docker --manager --yes --api-token T --instances \"10.0.0.11 10.0.0.12\""
    echo "                           # Docker manager managing two remote workers"
    echo "  $0 --docker --worker --yes --api-token T --manager-ip 10.0.0.5"
    echo "                           # Docker worker managed by the manager at 10.0.0.5"
    echo
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            # Fix: actually use provided argument for version
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing version after $1"
                exit 1
            fi
            BUNKERWEB_VERSION="$2"
            shift 2
            ;;
        -w|--enable-wizard)
            ENABLE_WIZARD="yes"
            shift
            ;;
        -n|--no-wizard)
            ENABLE_WIZARD="no"
            shift
            ;;
        -y|--yes)
            INTERACTIVE_MODE="no"
            # Default wizard ON unless --no-wizard appeared earlier (unconditional set would overwrite it).
            if [ -z "$ENABLE_WIZARD" ]; then
                ENABLE_WIZARD="yes"
            fi
            shift
            ;;
        --tui)
            USE_TUI="yes"
            shift
            ;;
        --no-tui)
            USE_TUI="no"
            shift
            ;;
        -f|--force)
            FORCE_INSTALL="yes"
            shift
            ;;
        --force-type-change)
            FORCE_TYPE_CHANGE="yes"
            shift
            ;;
        --restart-install)
            RESTART_INSTALL="yes"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --full|--manager|--worker|--scheduler-only|--ui-only|--api-only)
            # All six set INSTALL_TYPE; reject duplicates like `--manager --worker`
            # (silent last-wins would let a typo install the wrong topology).
            # These apply to BOTH platforms — pair with --docker for a container deploy.
            if [ -n "${_INSTALL_TYPE_FLAG:-}" ] && [ "$_INSTALL_TYPE_FLAG" != "$1" ]; then
                print_error "Conflicting install-type flags: $_INSTALL_TYPE_FLAG and $1 (only one allowed)."
                exit 1
            fi
            case "$1" in
                --full)           INSTALL_TYPE="full"      ;;
                --manager)        INSTALL_TYPE="manager"   ;;
                --worker)         INSTALL_TYPE="worker"    ;;
                --scheduler-only) INSTALL_TYPE="scheduler" ;;
                --ui-only)        INSTALL_TYPE="ui"        ;;
                --api-only)       INSTALL_TYPE="api"       ;;
            esac
            _INSTALL_TYPE_FLAG="$1"
            shift
            ;;
        --docker)
            # Deployment platform, orthogonal to the install type — does NOT
            # touch INSTALL_TYPE, so `--docker --manager` is valid.
            DOCKER_MODE="yes"
            shift
            ;;
        --autoconf)
            DOCKER_AUTOCONF="yes"
            shift
            ;;
        --no-autoconf)
            DOCKER_AUTOCONF="no"
            shift
            ;;
        --image-tag)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing tag after $1"
                exit 1
            fi
            DOCKER_IMAGE_TAG="$2"
            shift 2
            ;;
        --compose-dir)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing path after $1"
                exit 1
            fi
            DOCKER_PROJECT_DIR="$2"
            shift 2
            ;;
        --overwrite-compose)
            DOCKER_OVERWRITE_EXISTING="yes"
            shift
            ;;
        --install-docker)
            DOCKER_AUTO_INSTALL="yes"
            shift
            ;;
        --no-pull)
            DOCKER_PULL="no"
            shift
            ;;
        --docker-wait-timeout)
            if [ -z "$2" ] || [[ ! "$2" =~ ^[0-9]+$ ]]; then
                print_error "$1 requires a positive integer (seconds)"
                exit 1
            fi
            DOCKER_WAIT_TIMEOUT="$2"
            shift 2
            ;;
        --api-token)
            # Shared API token for distributed docker installs (manager/worker/
            # scheduler) — must be identical on every host of the cluster.
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing token after $1"
                exit 1
            fi
            DOCKER_API_TOKEN_GENERATED="$2"
            shift 2
            ;;
        --database-uri)
            # External DATABASE_URI for docker scheduler/ui/api types.
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing URI after $1"
                exit 1
            fi
            DOCKER_DATABASE_URI="$2"
            shift 2
            ;;
        --http-port|--https-port|--api-port|--ui-port|--fastapi-port)
            # Host ports for the generated docker stack — let several stacks
            # (e.g. a manager + workers) co-exist on one host.
            if [ -z "$2" ] || [[ ! "$2" =~ ^[0-9]+$ ]] || [ "$2" -lt 1 ] || [ "$2" -gt 65535 ]; then
                print_error "$1 requires a port number between 1 and 65535"
                exit 1
            fi
            case "$1" in
                --http-port)    DOCKER_HTTP_PORT="$2"    ;;
                --https-port)   DOCKER_HTTPS_PORT="$2"   ;;
                --api-port)     DOCKER_API_PORT="$2"     ;;
                --ui-port)      DOCKER_UI_PORT="$2"      ;;
                --fastapi-port) DOCKER_FASTAPI_PORT="$2" ;;
            esac
            shift 2
            ;;
        --crowdsec)
            CROWDSEC_INSTALL="yes"
            shift
            ;;
        --no-crowdsec)
            CROWDSEC_INSTALL="no"
            shift
            ;;
        --crowdsec-appsec)
            CROWDSEC_INSTALL="yes"
            CROWDSEC_APPSEC_INSTALL="yes"
            shift
            ;;
        --redis)
            REDIS_INSTALL="yes"
            shift
            ;;
        --no-redis)
            REDIS_INSTALL="no"
            shift
            ;;
        --redis-host)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing host value after $1"
                exit 1
            fi
            REDIS_HOST_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-port)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing port value after $1"
                exit 1
            fi
            if ! [[ "$2" =~ ^[1-9][0-9]{0,4}$ ]] || [ "$2" -gt 65535 ]; then
                print_error "--redis-port must be a TCP port (1-65535)"
                exit 1
            fi
            REDIS_PORT_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-database)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing database number after $1"
                exit 1
            fi
            REDIS_DATABASE_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-username)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing username value after $1"
                exit 1
            fi
            REDIS_USERNAME_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-password)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing password value after $1"
                exit 1
            fi
            REDIS_PASSWORD_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-ssl)
            REDIS_SSL_INPUT="yes"
            REDIS_INSTALL="no"
            shift
            ;;
        --redis-no-ssl)
            REDIS_SSL_INPUT="no"
            REDIS_INSTALL="no"
            shift
            ;;
        --redis-ssl-verify)
            REDIS_SSL_VERIFY_INPUT="yes"
            REDIS_INSTALL="no"
            shift
            ;;
        --redis-no-ssl-verify)
            REDIS_SSL_VERIFY_INPUT="no"
            REDIS_INSTALL="no"
            shift
            ;;
        --redis-flavor)
            case "$2" in
                redis|valkey) REDIS_FLAVOR="$2" ;;
                *) print_error "--redis-flavor must be 'redis' or 'valkey'"; exit 1 ;;
            esac
            shift 2
            ;;
        --redis-bind)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing bind address after $1"
                exit 1
            fi
            REDIS_BIND_INPUT="$2"
            shift 2
            ;;
        --redis-no-password)
            REDIS_AUTOPASS="no"
            shift
            ;;
        --redis-maxmemory)
            # Accept "0", "unlimited", "256", or "256mb" (case-insensitive); store as MB integer.
            case "$2" in
                0|none|unlimited|skip)
                    REDIS_MAXMEMORY_MB="0"
                    ;;
                *)
                    _mm_value="${2%[mM][bB]}"
                    if [[ "$_mm_value" =~ ^[1-9][0-9]*$ ]]; then
                        REDIS_MAXMEMORY_MB="$_mm_value"
                    else
                        print_error "--redis-maxmemory must be a positive integer in MB (e.g. 256, 1024) or 0/unlimited"
                        exit 1
                    fi
                    ;;
            esac
            shift 2
            ;;
        --redis-maxmemory-policy)
            case "$2" in
                noeviction|allkeys-lru|allkeys-lfu|allkeys-random|volatile-lru|volatile-lfu|volatile-random|volatile-ttl)
                    REDIS_MAXMEMORY_POLICY="$2"
                    ;;
                *)
                    print_error "--redis-maxmemory-policy must be a valid Redis/Valkey eviction policy"
                    exit 1
                    ;;
            esac
            shift 2
            ;;
        --database)
            case "$2" in
                mariadb|MariaDB)       DB_INSTALL="mariadb" ;;
                postgresql|postgres|PostgreSQL) DB_INSTALL="postgresql" ;;
                external|existing|remote) DB_INSTALL="external" ;;
                none|skip|sqlite|SQLite) DB_INSTALL="none" ;;
                *) print_error "--database must be one of: mariadb, postgresql, external, none"; exit 1 ;;
            esac
            shift 2
            ;;
        --db-engine)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing engine value after $1"
                exit 1
            fi
            case "$2" in
                mariadb|MariaDB)               DB_EXTERNAL_ENGINE="mariadb" ;;
                mysql|MySQL)                   DB_EXTERNAL_ENGINE="mysql" ;;
                postgresql|postgres|PostgreSQL) DB_EXTERNAL_ENGINE="postgresql" ;;
                *) print_error "--db-engine must be one of: mariadb, mysql, postgresql"; exit 1 ;;
            esac
            # Implies external mode unless the user explicitly picked something else.
            if [ -z "$DB_INSTALL" ]; then
                DB_INSTALL="external"
            fi
            shift 2
            ;;
        --db-host)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing host value after $1"
                exit 1
            fi
            if ! validate_db_host "$2"; then
                print_error "--db-host '$2' contains characters that would break the DSN. Allowed: letters, digits, dot, hyphen, colon (IPv6), square brackets (IPv6 literal)."
                exit 1
            fi
            DB_HOST_INPUT="$2"
            if [ -z "$DB_INSTALL" ]; then
                DB_INSTALL="external"
            fi
            shift 2
            ;;
        --db-port)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing port value after $1"
                exit 1
            fi
            if ! [[ "$2" =~ ^[1-9][0-9]{0,4}$ ]] || [ "$2" -gt 65535 ]; then
                print_error "--db-port must be a TCP port (1-65535)"
                exit 1
            fi
            DB_PORT_INPUT="$2"
            if [ -z "$DB_INSTALL" ]; then
                DB_INSTALL="external"
            fi
            shift 2
            ;;
        --db-ssl)
            DB_SSL_INPUT="yes"
            shift
            ;;
        --db-no-ssl)
            DB_SSL_INPUT="no"
            shift
            ;;
        --db-ssl-verify)
            DB_SSL_VERIFY_INPUT="yes"
            shift
            ;;
        --db-no-ssl-verify)
            DB_SSL_VERIFY_INPUT="no"
            print_warning "TLS server certificate verification DISABLED for the database connection."
            print_warning "Use --db-ssl-verify in production — the channel is vulnerable to MitM without it."
            shift
            ;;
        --db-skip-probe)
            DB_SKIP_PROBE="yes"
            shift
            ;;
        --db-name)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing database name after $1"
                exit 1
            fi
            if ! validate_db_identifier "$2"; then
                print_error "--db-name '$2' must match ^[A-Za-z_][A-Za-z0-9_]*$ (max 63 chars). SQL identifiers cannot contain spaces, quotes or shell metacharacters."
                exit 1
            fi
            DB_NAME_INPUT="$2"
            shift 2
            ;;
        --db-user)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing database user after $1"
                exit 1
            fi
            if ! validate_db_identifier "$2"; then
                print_error "--db-user '$2' must match ^[A-Za-z_][A-Za-z0-9_]*$ (max 63 chars)."
                exit 1
            fi
            DB_USER_INPUT="$2"
            shift 2
            ;;
        --db-password)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing password value after $1"
                exit 1
            fi
            DB_PASSWORD_INPUT="$2"
            if ! validate_db_password "$DB_PASSWORD_INPUT"; then
                print_error "--db-password fails validation: 8+ chars, no quotes/backslashes."
                exit 1
            fi
            shift 2
            ;;
        --ui-admin-user)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing username value after $1"
                exit 1
            fi
            if ! validate_ui_admin_username "$2"; then
                print_error "--ui-admin-user '$2' must match ^[A-Za-z0-9._-]+$ (max 64 chars)."
                exit 1
            fi
            UI_ADMIN_USERNAME_INPUT="$2"
            UI_ADMIN_CREATE="yes"
            shift 2
            ;;
        --ui-admin-password)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing password value after $1"
                exit 1
            fi
            UI_ADMIN_PASSWORD_INPUT="$2"
            UI_ADMIN_CREATE="yes"
            if ! validate_ui_admin_password "$UI_ADMIN_PASSWORD_INPUT"; then
                print_error "--ui-admin-password fails BunkerWeb rules: 8+ chars, one lowercase, one uppercase, one digit, one special."
                exit 1
            fi
            shift 2
            ;;
        --no-ui-admin)
            UI_ADMIN_CREATE="no"
            shift
            ;;
        --ui-https-selfsigned)
            UI_SELFSIGNED_INPUT="yes"
            shift
            ;;
        --no-ui-https-selfsigned)
            UI_SELFSIGNED_INPUT="no"
            shift
            ;;
        --instances)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing instances value after $1"
                exit 1
            fi
            BUNKERWEB_INSTANCES_INPUT="$2"
            shift 2
            ;;
        --manager-ip)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing IP value after $1"
                exit 1
            fi
            MANAGER_IP_INPUT="$2"
            shift 2
            ;;
        --server-ip)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing IP value after $1"
                exit 1
            fi
            SERVER_IP_INPUT="$2"
            shift 2
            ;;
        --dns-resolvers)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing resolver list after $1"
                exit 1
            fi
            DNS_RESOLVERS_INPUT="$2"
            shift 2
            ;;
        --api-https)
            API_LISTEN_HTTPS_INPUT="yes"
            shift
            ;;
        --api|--enable-api)
            SERVICE_API=yes
            shift
            ;;
        --no-api)
            SERVICE_API=no
            shift
            ;;
        --backup-dir)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing directory path after $1"
                exit 1
            fi
            BACKUP_DIRECTORY="$2"; shift 2 ;;
        --no-auto-backup)
            AUTO_BACKUP="no"; shift ;;
        --epel)
            INSTALL_EPEL="yes"
            shift
            ;;
        --no-epel)
            INSTALL_EPEL="no"
            shift
            ;;
        -q|--quiet)
            # Save original stdout/stderr on fd 3/4 BEFORE redirect — needed to surface
            # auto-gen DB/UI/Redis passwords at end of install (otherwise unrecoverable).
            exec 3>&1 4>&2
            # CLOEXEC fd 3/4: dpkg-preconfigure uses fd 3 for the debconf protocol;
            # a leaked fd 3 confuses its parser and prints debconf chatter on the operator's term.
            if command -v python3 >/dev/null 2>&1; then
                python3 -c '
import fcntl, os
for fd in (3, 4):
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    except OSError:
        pass
' 2>/dev/null || true
            fi
            # shellcheck disable=SC2034  # consumed by show_final_info via :+ check
            QUIET_MODE="yes"
            # --quiet implies non-interactive — TUI prompts would hang waiting on input
            # while their output goes to /dev/null. Default-wizard rule same as --yes.
            INTERACTIVE_MODE="no"
            if [ -z "$ENABLE_WIZARD" ]; then
                ENABLE_WIZARD="yes"
            fi
            # _BW_OUT_FD/_BW_ERR_FD = real terminal for the show_final_info credentials block.
            _BW_OUT_FD=3
            _BW_ERR_FD=4
            export _BW_OUT_FD _BW_ERR_FD QUIET_MODE
            exec >/dev/null 2>&1
            shift
            ;;
        --dry-run)
            # Deferred: render after argv parse + validation so later flags aren't dropped
            # and invalid combos still surface their parse-time errors.
            DRY_RUN="yes"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Post-argv validation — Linux-package install guards. Docker mode runs its own
# per-type validation in ask_docker_preferences, so this whole block is skipped
# when DOCKER_MODE=yes. (Kept un-indented to keep the diff reviewable.)
# ---------------------------------------------------------------------------
if [ "$DOCKER_MODE" != "yes" ]; then

# Force wizard off for manager installations
if [ "$INSTALL_TYPE" = "manager" ]; then
    if [ "$ENABLE_WIZARD" = "yes" ]; then
        print_warning "Setup wizard cannot run in manager mode; disabling it."
    fi
    ENABLE_WIZARD="no"
fi

# Validate instances option usage
if [ -n "$BUNKERWEB_INSTANCES_INPUT" ] && [[ "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "scheduler" ]]; then
    print_error "The --instances option can only be used with --manager or --scheduler-only installation types"
    exit 1
fi

# --ui-https-selfsigned only generates a cert in manager mode (via start_manager_ui).
# Other modes would write UI_HOST=https://... with no cert → broken UI. Reject at parse.
if [ "$UI_SELFSIGNED_INPUT" = "yes" ] && [ -n "$INSTALL_TYPE" ] && [ "$INSTALL_TYPE" != "manager" ]; then
    print_error "--ui-https-selfsigned is only supported with --manager (it generates the cert in start_manager_ui)."
    print_error "For --${INSTALL_TYPE} mode, drop the flag and front the UI with your own reverse proxy if HTTPS is needed."
    exit 1
fi

# Inform about missing instances for manager/scheduler in non-interactive mode
if [ "$INTERACTIVE_MODE" = "no" ] && [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]] && [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
    print_warning "No BunkerWeb instances configured. You can add workers later."
    print_status "See: https://docs.bunkerweb.io/latest/integrations/#linux"
fi

if [ "$INTERACTIVE_MODE" = "no" ] && [ "$INSTALL_TYPE" = "worker" ] && [ -z "$MANAGER_IP_INPUT" ]; then
    print_error "The --manager-ip option is required when using --worker in non-interactive mode"
    print_error "Example: --worker --manager-ip 10.20.30.40"
    exit 1
fi

# Validate CrowdSec options usage
if [[ "$CROWDSEC_INSTALL" = "yes" || "$CROWDSEC_APPSEC_INSTALL" = "yes" ]] && [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
    print_error "CrowdSec options (--crowdsec, --crowdsec-appsec) can only be used with --full or --manager installation types"
    exit 1
fi

if { [ "$REDIS_INSTALL" = "yes" ] || [ -n "$REDIS_HOST_INPUT" ] || [ -n "$REDIS_PORT_INPUT" ] || [ -n "$REDIS_DATABASE_INPUT" ] || [ -n "$REDIS_USERNAME_INPUT" ] || [ -n "$REDIS_PASSWORD_INPUT" ] || [ -n "$REDIS_SSL_INPUT" ] || [ -n "$REDIS_SSL_VERIFY_INPUT" ] || [ -n "$REDIS_FLAVOR" ] || [ -n "$REDIS_BIND_INPUT" ]; } \
    && [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && -n "$INSTALL_TYPE" ]]; then
    print_error "Redis options (--redis, --redis-*) can only be used with --full or --manager installation types"
    exit 1
fi

# --redis-bind is meaningful only for manager mode (full stack stays on loopback).
if [ -n "$REDIS_BIND_INPUT" ] && [ "$INSTALL_TYPE" != "manager" ] && [ -n "$INSTALL_TYPE" ]; then
    print_error "The --redis-bind option only applies to --manager installations"
    exit 1
fi

# --database family — only allowed for full/manager
if [ -n "$DB_INSTALL" ] && [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && -n "$INSTALL_TYPE" ]]; then
    print_error "The --database / --db-* options only apply to --full or --manager installations"
    exit 1
fi

# UI admin creation — allowed for any install type with a UI service (full, manager, ui).
# Self-signed HTTPS still only makes sense on the manager-mode private listener.
if { [ -n "$UI_ADMIN_CREATE" ] || [ -n "$UI_ADMIN_USERNAME_INPUT" ] || [ -n "$UI_ADMIN_PASSWORD_INPUT" ]; } \
    && [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "ui" && -n "$INSTALL_TYPE" ]]; then
    print_error "UI admin options (--ui-admin-*) only apply to --full, --manager or --ui-only installations"
    exit 1
fi

if [ -n "$UI_SELFSIGNED_INPUT" ] && [ "$INSTALL_TYPE" != "manager" ] && [ -n "$INSTALL_TYPE" ]; then
    print_error "Manager UI self-signed HTTPS (--ui-https-selfsigned) only applies to --manager installations"
    exit 1
fi

# External-DB inputs only make sense alongside --database external on full/manager.
if [ -n "$DB_EXTERNAL_ENGINE" ] || [ -n "$DB_HOST_INPUT" ] || [ -n "$DB_PORT_INPUT" ] || [ -n "$DB_SSL_INPUT" ] || [ -n "$DB_SSL_VERIFY_INPUT" ]; then
    if [ -n "$DB_INSTALL" ] && [ "$DB_INSTALL" != "external" ]; then
        print_error "--db-engine/--db-host/--db-port/--db-ssl* require --database external"
        exit 1
    fi
fi

# python3 pre-flight — every DATABASE_URI path uses urlencode_dsn_part (urllib.parse.quote).
# Fail at parse time, not after install_mariadb/install_postgresql has bootstrapped the DB.
case "$DB_INSTALL" in
    external|mariadb|postgresql)
        if ! command -v python3 >/dev/null 2>&1; then
            print_error "--database $DB_INSTALL requires python3 to safely URL-encode database credentials."
            print_error "Install python3 (apt install python3 / dnf install python3) and retry."
            exit 1
        fi
        ;;
esac

# Non-interactive guardrails — silent installs must not end up unusable.
# 1. --yes --database external without min inputs → fail fast.
# 2. --yes --no-wizard + UI install + no --ui-admin-* → auto-create admin (password printed at end).
if [ "$INTERACTIVE_MODE" = "no" ]; then
    if [ "$DB_INSTALL" = "external" ]; then
        _bw_missing=()
        [ -z "$DB_EXTERNAL_ENGINE" ] && _bw_missing+=(--db-engine)
        [ -z "$DB_HOST_INPUT" ]       && _bw_missing+=(--db-host)
        [ -z "$DB_PASSWORD_INPUT" ]   && _bw_missing+=(--db-password)
        if [ "${#_bw_missing[@]}" -gt 0 ]; then
            print_error "--database external in non-interactive mode requires: ${_bw_missing[*]}"
            exit 1
        fi
        unset _bw_missing
    fi

    if [ "$ENABLE_WIZARD" = "no" ] \
        && [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "manager" || -z "$INSTALL_TYPE" ]] \
        && [ "${UI_ADMIN_CREATE:-}" != "no" ] \
        && [ -z "$UI_ADMIN_USERNAME_INPUT" ] \
        && [ -z "$UI_ADMIN_PASSWORD_INPUT" ] \
        && [ "$UI_ADMIN_CREATE" != "yes" ]; then
        print_warning "Wizard disabled + non-interactive + no --ui-admin-* flags."
        print_warning "Auto-creating admin user with a generated password (printed at the end of install)."
        UI_ADMIN_CREATE="yes"
    fi

    # 3. --yes + local DB without --db-password → install_mariadb/install_postgresql will
    #    auto-gen (32 chars). Warn now; final credentials block surfaces it via _BW_OUT_FD under --quiet.
    if { [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; } \
        && [ -z "$DB_PASSWORD_INPUT" ]; then
        print_warning "Local ${DB_INSTALL} install + non-interactive + no --db-password."
        print_warning "Auto-generating database password (printed at the end of install)."
    fi
fi

fi  # end DOCKER_MODE != yes — Linux-package post-argv guards

# Deferred --dry-run summary — after argv parse + guards. Exits 0 on success.
if [ "$DRY_RUN" = "yes" ]; then
    # Restore operator's stdout via _BW_OUT_FD (was /dev/null under --quiet); branch exits after.
    [ -n "${_BW_OUT_FD:-}" ] && exec >&"${_BW_OUT_FD}"
    echo "Dry run mode - would install BunkerWeb $BUNKERWEB_VERSION"
    # Docker mode: report the compose plan and exit. Skip the host-OS gate —
    # docker mode runs on any Linux with Docker installed.
    if [ "$DOCKER_MODE" = "yes" ]; then
        # NOTE: top-level block — no 'local'; _dt is a throwaway global (we exit 0).
        _dt="${INSTALL_TYPE:-full}"
        echo "Deployment platform: docker (compose stack)"
        echo "Installation type: ${_dt}"
        [ "$_dt" = "full" ] && echo "Autoconf integration: ${DOCKER_AUTOCONF:-no}"
        echo "Image tag: $(derive_docker_image_tag "${DOCKER_IMAGE_TAG:-$BUNKERWEB_VERSION}")"
        echo "Compose directory: ${DOCKER_PROJECT_DIR:-$(pwd -P)}"
        case "$_dt" in
            full)      echo "Services: bunkerweb, bw-scheduler, bw-ui, bw-db, redis"
                       [ "${DOCKER_AUTOCONF:-no}" = "yes" ] && echo "         + bw-autoconf, bw-docker"
                       echo "Database: MariaDB (bundled bw-db container)"
                       echo "Host ports: ${DOCKER_HTTP_PORT} (HTTP), ${DOCKER_HTTPS_PORT} (HTTPS/QUIC)" ;;
            manager)   echo "Services: bw-scheduler, bw-ui, bw-db, redis"
                       echo "Database: MariaDB (bundled bw-db container)"
                       echo "Host ports: ${DOCKER_UI_PORT} (Web UI)"
                       echo "Requires: remote worker IPs, shared API token" ;;
            worker)    echo "Services: bunkerweb"
                       echo "Host ports: ${DOCKER_HTTP_PORT} (HTTP), ${DOCKER_HTTPS_PORT} (HTTPS/QUIC), ${DOCKER_API_PORT} (API)"
                       echo "Requires: manager IP(s), shared API token" ;;
            scheduler) echo "Services: bw-scheduler, redis"
                       echo "Database: external (DATABASE_URI required)"
                       echo "Requires: remote worker IPs, shared API token" ;;
            ui)        echo "Services: bw-ui"
                       echo "Host ports: ${DOCKER_UI_PORT} (Web UI)"
                       echo "Database: external (DATABASE_URI required)" ;;
            api)       echo "Services: bw-api"
                       echo "Host ports: ${DOCKER_FASTAPI_PORT} (FastAPI)"
                       echo "Database: external (DATABASE_URI required)" ;;
        esac
        echo "Pull images: ${DOCKER_PULL}"
        echo "Wait timeout: ${DOCKER_WAIT_TIMEOUT}s"
        echo "(dry run — required flags such as --api-token / --database-uri / --manager-ip are not validated here)"
        exit 0
    fi
    detect_os
    check_supported_os
    echo "Installation type: ${INSTALL_TYPE:-full}"
    # Wizard label per mode (manager off, worker/scheduler/api n/a).
    case "${INSTALL_TYPE:-full}" in
        manager)               echo "Setup wizard: disabled (manager mode)" ;;
        worker|scheduler|api)  echo "Setup wizard: n/a (this mode)" ;;
        *)                     echo "Setup wizard: ${ENABLE_WIZARD:-auto}" ;;
    esac
    echo "CrowdSec: ${CROWDSEC_INSTALL:-no}"
    if [ "$REDIS_INSTALL" = "yes" ]; then
        echo "Redis: yes (local install, flavor=${REDIS_FLAVOR:-redis})"
        if [ -n "$REDIS_BIND_INPUT" ]; then
            echo "Redis bind: $REDIS_BIND_INPUT"
        fi
        echo "Redis password: ${REDIS_AUTOPASS}"
    elif [ -n "$REDIS_HOST_INPUT" ]; then
        echo "Redis: yes (existing server)"
    else
        echo "Redis: no"
    fi
    if [ -n "$REDIS_HOST_INPUT" ]; then
        echo "Redis host: $REDIS_HOST_INPUT"
    fi
    echo "Database: ${DB_INSTALL:-prompt}"
    if [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; then
        echo "  db name: $DB_NAME_INPUT"
        echo "  db user: $DB_USER_INPUT"
        if [ -n "$DB_PASSWORD_INPUT" ]; then
            echo "  db password: <provided>"
        else
            echo "  db password: <auto-generate>"
        fi
    elif [ "$DB_INSTALL" = "external" ]; then
        echo "  db engine: ${DB_EXTERNAL_ENGINE:-<prompt>}"
        echo "  db host:   ${DB_HOST_INPUT:-<prompt>}"
        echo "  db port:   ${DB_PORT_INPUT:-<default>}"
        echo "  db name:   $DB_NAME_INPUT"
        echo "  db user:   $DB_USER_INPUT"
        if [ -n "$DB_PASSWORD_INPUT" ]; then
            echo "  db password: <provided>"
        else
            echo "  db password: <prompt>"
        fi
        if [ "$DB_SSL_INPUT" = "yes" ]; then
            if [ "$DB_SSL_VERIFY_INPUT" = "no" ]; then
                echo "  db ssl:    yes (no verify)"
            else
                echo "  db ssl:    yes (verify)"
            fi
        else
            echo "  db ssl:    ${DB_SSL_INPUT:-no}"
        fi
    fi
    echo "UI admin user: ${UI_ADMIN_CREATE:-prompt}${UI_ADMIN_USERNAME_INPUT:+ ($UI_ADMIN_USERNAME_INPUT)}"
    if [ -n "$UI_SELFSIGNED_INPUT" ]; then
        echo "UI HTTPS self-signed: $UI_SELFSIGNED_INPUT"
    fi
    if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
        echo "BunkerWeb instances: $BUNKERWEB_INSTANCES_INPUT"
    fi
    if [ -n "$MANAGER_IP_INPUT" ]; then
        echo "Manager IP: $MANAGER_IP_INPUT"
    fi
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        echo "DNS resolvers: $DNS_RESOLVERS_INPUT"
    fi
    if [ -n "$API_LISTEN_HTTPS_INPUT" ]; then
        echo "API HTTPS: $API_LISTEN_HTTPS_INPUT"
    fi
    exit 0
fi

# Infer install type from systemd unit state on upgrades. Operator's --type CLI override always wins.
# Rules:
#   bunkerweb + scheduler [+ ui]   → full
#   scheduler + ui (no bunkerweb)  → manager
#   bunkerweb only                 → worker
#   scheduler only                 → scheduler
#   ui only                        → ui
#   api only                       → api
# Falls back to empty (treated as full) on ambiguous state.
detect_install_type_from_state() {
    if [ "$DISTRO_ID" = "freebsd" ]; then
        # systemctl unavailable; rely on rc.d enablement (YES = present).
        local _has_bw _has_sch _has_ui _has_api
        _has_bw=$(_freebsd_unit_state bunkerweb)
        _has_sch=$(_freebsd_unit_state bunkerweb_scheduler)
        _has_ui=$(_freebsd_unit_state bunkerweb_ui)
        _has_api=$(_freebsd_unit_state bunkerweb_api)
        _DETECTED_INSTALL_TYPE=$(_classify_install "$_has_bw" "$_has_sch" "$_has_ui" "$_has_api")
        return 0
    fi

    local _bw _sch _ui _api
    _bw=$(_systemd_unit_state bunkerweb)
    _sch=$(_systemd_unit_state bunkerweb-scheduler)
    _ui=$(_systemd_unit_state bunkerweb-ui)
    _api=$(_systemd_unit_state bunkerweb-api)
    _DETECTED_INSTALL_TYPE=$(_classify_install "$_bw" "$_sch" "$_ui" "$_api")
}

# is-enabled OR is-active → "present", else "absent".
# disabled+stopped units (e.g. leftover from prior --full now running --worker) must NOT count as present.
_systemd_unit_state() {
    local unit="$1" _enabled _active
    _enabled=$(systemctl is-enabled "$unit" 2>/dev/null || echo "missing")
    _active=$(systemctl is-active "$unit" 2>/dev/null || echo "inactive")
    case "$_enabled" in
        enabled|enabled-runtime|static|alias)
            echo "present"; return ;;
    esac
    case "$_active" in
        active|activating|reloading)
            echo "present"; return ;;
    esac
    echo "absent"
}

# FreeBSD rc.d: sysrc <unit>_enable=YES OR `service status` → "present".
_freebsd_unit_state() {
    local unit="$1" _enabled _running=1
    _enabled=$(sysrc -n "${unit}_enable" 2>/dev/null || echo "")
    case "$_enabled" in
        [Yy][Ee][Ss]) echo "present"; return ;;
    esac
    if command -v service >/dev/null 2>&1; then
        service "$unit" status >/dev/null 2>&1 && _running=0
    fi
    if [ "$_running" = 0 ]; then echo "present"; else echo "absent"; fi
}

# Classify install type from per-unit "present"/"absent" state. Most-specific first.
# manager-without-UI vs scheduler-only disambiguated by /etc/bunkerweb/ui.env presence
# (manager-mode SERVICE_UI=no still provisions ui.env; scheduler-only never does).
_classify_install() {
    local bw="$1" sch="$2" ui="$3" api="$4"
    local _b _s _u _a
    [ "$bw"  = "present" ] && _b=1 || _b=0
    [ "$sch" = "present" ] && _s=1 || _s=0
    [ "$ui"  = "present" ] && _u=1 || _u=0
    [ "$api" = "present" ] && _a=1 || _a=0

    if [ "$_b" = 1 ] && [ "$_s" = 1 ]; then
        echo "full"; return
    fi
    if [ "$_b" = 0 ] && [ "$_s" = 1 ] && [ "$_u" = 1 ]; then
        echo "manager"; return
    fi
    if [ "$_b" = 1 ] && [ "$_s" = 0 ] && [ "$_u" = 0 ]; then
        echo "worker"; return
    fi
    if [ "$_b" = 0 ] && [ "$_s" = 1 ] && [ "$_u" = 0 ]; then
        # ui.env exists → manager-with-SERVICE_UI=no; absent → true scheduler-only
        # (bunkerweb-ui postinst touches ui.env when SERVICE_UI≠no, so the file marks manager intent).
        if [ -f /etc/bunkerweb/ui.env ]; then
            echo "manager"; return
        fi
        echo "scheduler"; return
    fi
    # ui-only: UI enabled, NO scheduler, NO bunkerweb, NO api. If api is ALSO
    # enabled, fall through to "unknown" rather than silently disabling api
    # on the next upgrade run — the operator likely runs a custom mixed
    # topology not natively supported by --type.
    if [ "$_b" = 0 ] && [ "$_s" = 0 ] && [ "$_u" = 1 ] && [ "$_a" = 0 ]; then
        echo "ui"; return
    fi
    if [ "$_b" = 0 ] && [ "$_s" = 0 ] && [ "$_u" = 0 ] && [ "$_a" = 1 ]; then
        echo "api"; return
    fi
    echo ""
}

# Human-readable label for an install-type tag — used in confirmation prompts
# so the operator sees "Manager" rather than the bare "manager" token.
_install_type_label() {
    case "$1" in
        full)      echo "Full Stack (bunkerweb + scheduler + ui)" ;;
        manager)   echo "Manager (scheduler + ui)" ;;
        worker)    echo "Worker (bunkerweb only)" ;;
        scheduler) echo "Scheduler only" ;;
        ui)        echo "Web UI only" ;;
        api)       echo "API only" ;;
        *)         echo "unknown / mixed" ;;
    esac
}

check_existing_installation() {
    if [ -f /usr/share/bunkerweb/VERSION ]; then
        INSTALLED_VERSION=$(cat /usr/share/bunkerweb/VERSION 2>/dev/null || echo "unknown")
        print_status "Detected existing BunkerWeb installation (version ${INSTALLED_VERSION})"

        # Log detected type on every run (incl. same-version no-op). Operator-flag reconciliation
        # only happens when we know it's an upgrade.
        detect_install_type_from_state
        if [ -n "$_DETECTED_INSTALL_TYPE" ]; then
            print_status "Detected install type: $(_install_type_label "$_DETECTED_INSTALL_TYPE")"
        else
            print_status "Could not deduce install type from systemd state — host topology is ambiguous."
        fi
        if [ "$INSTALLED_VERSION" = "$BUNKERWEB_VERSION" ]; then
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                if tui_yesno "BunkerWeb Already Installed" \
                    "BunkerWeb ${INSTALLED_VERSION} is already installed.\nShow status and exit?" "yes"; then
                    show_final_info; exit 0
                fi
                print_status "BunkerWeb ${INSTALLED_VERSION} already installed. Exiting."; exit 0
            else
                print_status "BunkerWeb ${INSTALLED_VERSION} already installed. Nothing to do."; exit 0
            fi
        else
            print_warning "Requested version ${BUNKERWEB_VERSION} differs from installed version ${INSTALLED_VERSION}. Upgrade will be attempted."
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                if ! tui_yesno "Upgrade BunkerWeb" \
                    "Upgrade BunkerWeb from ${INSTALLED_VERSION} to ${BUNKERWEB_VERSION}?\nProceed with upgrade?" "yes"; then
                    print_status "Upgrade cancelled."; exit 0
                fi
            fi
            UPGRADE_SCENARIO="yes"

            # Reconcile flag vs detection:
            #   no flag + detection → adopt detection silently.
            #   flag = detection    → already aligned.
            #   flag ≠ detection    → fail loud (require --force-type-change). HA migrations only.
            #   both empty          → fall through; ask_user_preferences will prompt.
            if [ -n "$_DETECTED_INSTALL_TYPE" ]; then
                if [ -z "$INSTALL_TYPE" ]; then
                    INSTALL_TYPE="$_DETECTED_INSTALL_TYPE"
                    print_status "Applying detected install type: $(_install_type_label "$INSTALL_TYPE")"
                elif [ "$INSTALL_TYPE" != "$_DETECTED_INSTALL_TYPE" ]; then
                    if [ "$FORCE_TYPE_CHANGE" = "yes" ]; then
                        # Interactive confirm even with the flag — stale shell history must not silently destroy a working install.
                        # --yes path accepts flag at face value (operator authored the script).
                        if [ "$INTERACTIVE_MODE" = "yes" ]; then
                            if ! tui_yesno "Install Type Change" \
"You passed --force-type-change.
Existing install: $(_install_type_label "$_DETECTED_INSTALL_TYPE")
Requested:        $(_install_type_label "$INSTALL_TYPE")

Services from the previous topology will be stopped and NOT
restarted. This is destructive — config files may carry over
but service state will not.

Proceed with topology change?" "no"; then
                                print_status "Topology change cancelled."
                                exit 0
                            fi
                        fi
                        print_warning "Install type change on upgrade: $(_install_type_label "$_DETECTED_INSTALL_TYPE") -> $(_install_type_label "$INSTALL_TYPE") (--force-type-change)."
                        print_warning "Services from the previous topology will be stopped; restart them manually if you intend to keep them."
                    else
                        print_error "Install type mismatch: detected $(_install_type_label "$_DETECTED_INSTALL_TYPE"), but you passed --${INSTALL_TYPE}."
                        print_error "Changing install type during an upgrade is destructive. Pass --force-type-change to confirm, or drop the --${INSTALL_TYPE} flag to upgrade in place."
                        exit 1
                    fi
                fi
            elif [ -z "$INSTALL_TYPE" ]; then
                print_warning "No --type flag and detection inconclusive — operator will be re-prompted."
            fi
        fi
    fi
}

perform_upgrade_backup() {
    [ "$UPGRADE_SCENARIO" != "yes" ] && return 0
    if should_skip_upgrade_backup; then
        return 0
    fi
    if [ "$AUTO_BACKUP" != "yes" ]; then
        print_warning "Automatic backup disabled. Ensure you already performed a manual backup (see https://docs.bunkerweb.io/latest/upgrading)."
        return 0
    fi
    if ! command -v bwcli >/dev/null 2>&1; then
        print_warning "bwcli not found, cannot run automatic backup. Perform manual backup per documentation."
        return 0
    fi
    local scheduler_running="no"
    if [ "$DISTRO_ID" = "freebsd" ]; then
        if service bunkerweb_scheduler status >/dev/null 2>&1; then
            scheduler_running="yes"
        fi
    else
        if systemctl is-active --quiet bunkerweb-scheduler 2>/dev/null; then
            scheduler_running="yes"
        fi
    fi
    if [ "$scheduler_running" = "no" ]; then
        print_warning "Scheduler service not active; starting temporarily for the backup, will stop again afterwards."
        if [ "$DISTRO_ID" = "freebsd" ]; then
            service bunkerweb_scheduler onestart || print_warning "Failed to start scheduler; backup may fail."
        else
            systemctl start bunkerweb-scheduler || print_warning "Failed to start scheduler; backup may fail."
        fi
        TEMP_STARTED="yes"
    fi
    if [ -z "$BACKUP_DIRECTORY" ]; then
        BACKUP_DIRECTORY="/var/tmp/bunkerweb-backup-$(date +%Y%m%d-%H%M%S)"
    fi
    mkdir -p "$BACKUP_DIRECTORY" || {
        print_warning "Unable to create backup directory $BACKUP_DIRECTORY. Skipping automatic backup."; return 0; }
    print_step "Creating pre-upgrade backup in $BACKUP_DIRECTORY"
    if BACKUP_DIRECTORY="$BACKUP_DIRECTORY" bwcli plugin backup save; then
        print_status "Backup completed: $BACKUP_DIRECTORY"
    else
        print_warning "Automatic backup failed. Verify manually before continuing."
    fi
    if [ "$TEMP_STARTED" = "yes" ]; then
        if [ "$DISTRO_ID" = "freebsd" ]; then
            service bunkerweb_scheduler onestop || print_warning "Failed to stop bunkerweb_scheduler after temporary start."
        else
            systemctl stop bunkerweb-scheduler || print_warning "Failed to stop bunkerweb-scheduler after temporary start."
        fi
    fi
}

should_skip_upgrade_backup() {
    if [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
        return 0
    fi
    if ! systemctl list-unit-files --type=service 2>/dev/null | grep -q "^bunkerweb-scheduler.service"; then
        return 0
    fi
    if ! systemctl is-enabled --quiet bunkerweb-scheduler 2>/dev/null && ! systemctl is-active --quiet bunkerweb-scheduler 2>/dev/null; then
        return 0
    fi
    return 1
}

upgrade_only() {
    # FreeBSD upgrade not implemented yet — packages still scaffolding. Bail before backup prompts.
    if [ "$DISTRO_ID" = "freebsd" ]; then
        print_error "Automated FreeBSD upgrade is not supported yet."
        print_error "Manual upgrade procedure:"
        print_error "  1. service bunkerweb stop && service bunkerweb_scheduler stop"
        print_error "  2. pkg unlock -y bunkerweb"
        print_error "  3. pkg upgrade -y bunkerweb"
        print_error "  4. pkg lock -y bunkerweb"
        print_error "  5. service bunkerweb_scheduler start && service bunkerweb start"
        exit 1
    fi
    if should_skip_upgrade_backup; then
        print_status "Skipping pre-upgrade backup (scheduler not enabled; worker/ui/api install)."
    else
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            if [ "$AUTO_BACKUP" = "yes" ]; then
                DEFAULT_BACKUP_DIR="/var/tmp/bunkerweb-backup-$(date +%Y%m%d-%H%M%S)"
                tui_section "💾 Pre-upgrade Backup"
                _tui_explain "A pre-upgrade backup is recommended to preserve
configuration and database state. The backup runs before any
package upgrade and is stored under the path you choose below."
                if tui_yesno "Pre-upgrade Backup" \
                    "💾 Create an automatic backup before upgrade?" "yes"; then
                    # Validate path: absolute, no `..`, restricted charset (no stray $VAR / shell metas).
                    while true; do
                        BACKUP_DIRECTORY_INPUT=$(tui_input "Pre-upgrade Backup" \
                            "Backup directory (absolute path; allowed chars: A-Z a-z 0-9 . _ - / ):" \
                            "$DEFAULT_BACKUP_DIR") || BACKUP_DIRECTORY_INPUT=""
                        BACKUP_DIRECTORY_INPUT="${BACKUP_DIRECTORY_INPUT:-$DEFAULT_BACKUP_DIR}"
                        if [[ "$BACKUP_DIRECTORY_INPUT" == /* ]] \
                            && [[ "$BACKUP_DIRECTORY_INPUT" != *..* ]] \
                            && [[ "$BACKUP_DIRECTORY_INPUT" =~ ^[A-Za-z0-9._/-]+$ ]]; then
                            BACKUP_DIRECTORY="$BACKUP_DIRECTORY_INPUT"
                            break
                        fi
                        tui_msgbox "Pre-upgrade Backup" \
                            "Invalid backup path. Requirements:\n  • absolute (must start with /)\n  • no '..' traversal segments\n  • only [A-Za-z0-9._/-]"
                    done
                else
                    AUTO_BACKUP="no"
                fi
            else
                tui_section "⚠️  Backup Confirmation"
                _tui_explain "Automatic backup is disabled.
Make sure you already performed a manual backup as described in
the documentation before continuing — the upgrade is destructive
to /etc/bunkerweb and the database schema."
                if ! tui_yesno "Backup Confirmation" \
                    "⚠️  Confirm a manual backup was performed?" "no"; then
                    print_error "Upgrade aborted until backup is confirmed."; exit 1
                fi
            fi
        fi
    fi

    print_status "Upgrade mode: $INSTALLED_VERSION -> $BUNKERWEB_VERSION"
    perform_upgrade_backup
    # Remove holds/versionlocks.
    case "$DISTRO_ID" in
        debian|ubuntu)
            if command -v apt-mark >/dev/null 2>&1; then
                print_status "Removing holds (bunkerweb, nginx)"
                apt-mark unhold bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
        fedora|rhel|rocky|almalinux|centos)
            if command -v dnf >/dev/null 2>&1; then
                print_status "Removing versionlock (bunkerweb, nginx)"
                dnf versionlock delete bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
    esac
    # Stop bunkerweb (drain) → api/ui → scheduler LAST. Snapshot active units into
    # _restart_after_upgrade in REVERSE order (scheduler restarts first to render templates).
    # Skipping the snapshot would leave services down — package postinst only restarts if-active.
    print_step "Stopping services prior to upgrade"
    local _restart_after_upgrade=""
    for svc in bunkerweb bunkerweb-api bunkerweb-ui bunkerweb-scheduler; do
        if systemctl list-units --type=service --all | grep -q "^${svc}.service"; then
            if systemctl is-active --quiet "$svc"; then
                _restart_after_upgrade="${svc} ${_restart_after_upgrade}"
                run_cmd systemctl stop "$svc"
            fi
        fi
    done
    # Install new version only — do NOT reinstall nginx.
    print_step "Upgrading BunkerWeb package"
    case "$DISTRO_ID" in
        debian|ubuntu)
            run_cmd apt update
            run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"
            run_cmd apt-mark hold bunkerweb nginx
            ;;
        fedora|rhel|rocky|almalinux|centos)
            if [ "$DISTRO_ID" = "fedora" ]; then
                run_cmd dnf makecache || true
            else
                dnf check-update || true
            fi
            run_cmd dnf install -y --allowerasing "bunkerweb-$BUNKERWEB_VERSION"
            run_cmd dnf versionlock add bunkerweb nginx
            ;;
        *)
            print_error "Upgrade not implemented for $DISTRO_ID — aborting."
            exit 1
            ;;
    esac
    # Restart every unit that was active before the upgrade. The package
    # postinst only auto-restarts CURRENTLY active services, and we stopped
    # them above — so without this loop the operator's services stay down
    # after a successful upgrade.
    if [ -n "$_restart_after_upgrade" ]; then
        print_step "Restarting services that were active before the upgrade"
        for svc in $_restart_after_upgrade; do
            if systemctl is-active --quiet "$svc"; then
                print_status "Service $svc already restarted by postinst, skipping."
                continue
            fi
            run_cmd systemctl start "$svc"
        done
    fi
    show_final_info
    exit 0
}

# Main installation function
main() {
    echo "========================================="
    echo "       BunkerWeb Easy Install Script"
    echo "========================================="
    echo

    check_root
    detect_os
    # tui_init right after $DISTRO_ID so every prompt (incl. continue-anyway guards) uses it.
    tui_init
    detect_architecture

    # Step 0 — deployment platform. Chosen BEFORE the host-capability gates so a
    # distro unsupported for host packages can still pick Docker.
    ask_deployment_platform

    # Host-capability gate. Docker mode checks Docker (and can install it);
    # Linux mode checks the host OS and the save-state/resume machinery (docker
    # mode never checkpoints, so it skips that entirely).
    if [ "$DOCKER_MODE" = "yes" ]; then
        check_docker_prereqs
    else
        check_supported_os
        # Resume detection — before check_existing_installation, which would
        # otherwise early-exit "already installed" once the package phase ran.
        _bw_state_load_and_prompt
    fi

    if [ "$_BW_START_OVER" = "yes" ]; then
        # Explicit start-over: an interrupted install left partial packages on
        # disk. Skip the "already installed" guard (check_existing_installation)
        # — the operator asked to redo the install — but still collect fresh
        # configuration and run every phase. A state file is only ever written
        # by this fresh-install path (upgrade_only never checkpoints), so a
        # discarded state file always implies an interrupted fresh install, not
        # an upgrade; running this as a non-upgrade fresh install is correct.
        print_status "Starting a fresh installation over the interrupted one."
        show_rhel_database_warning
        ask_user_preferences
        check_ports
    elif [ "$_BW_RESUMING" = "yes" ]; then
        print_status "Resuming interrupted installation (completed through: ${_BW_RESUME_AFTER})."
    else
        # Docker mode never checkpoints, so _BW_START_OVER / _BW_RESUMING are
        # always "no" and docker always lands in this branch.
        [ "$DOCKER_MODE" != "yes" ] && check_existing_installation

        if [ "$UPGRADE_SCENARIO" = "yes" ]; then
            upgrade_only
        fi

        [ "$DOCKER_MODE" != "yes" ] && show_rhel_database_warning
        ask_user_preferences
        check_ports
    fi

    # Env vars per install type — ALWAYS runs (fresh + resume); pure variable work.
    case "$INSTALL_TYPE" in
        "manager")
            export MANAGER_MODE=yes
            export ENABLE_WIZARD=no
            ;;
        "worker")
            export WORKER_MODE=yes
            export ENABLE_WIZARD=no
            ;;
        "scheduler")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=yes
            export SERVICE_UI=no
            ;;
        "ui")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            export SERVICE_UI=yes
            ;;
        "api")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            export SERVICE_UI=no
            export SERVICE_API=yes
            ;;
        "full"|"")
            ;;
    esac

    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    print_status "Installing BunkerWeb $BUNKERWEB_VERSION"
    echo

    # Interactive confirm — embed recap in dialog body (single confirm screen).
    # Skipped on resume: the configuration was already confirmed in the original run.
    if [ "$_BW_RESUMING" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ] && [ "$FORCE_INSTALL" != "yes" ]; then
        if [ "$GUM_AVAILABLE" = "yes" ]; then
            # Recap already rendered after ask_user_preferences; show only install/cancel.
            local _rc=0
            gum confirm \
                "Install BunkerWeb $BUNKERWEB_VERSION with this configuration?" \
                --default=true \
                --affirmative "Install" --negative "Cancel" \
                --prompt.foreground "#2eac68" \
                || _rc=$?
            if ! _tui_normalize_rc "$_rc"; then
                print_status "Installation cancelled"
                exit 0
            fi
        elif [ "$WHIPTAIL_AVAILABLE" = "yes" ]; then
            # Whiptail: recap embedded in confirm body (one screen).
            local _confirm_body _summary
            _summary=$(_build_configuration_summary)
            _confirm_body="${_summary}

Install BunkerWeb $BUNKERWEB_VERSION with this configuration?"
            local _lines _h _term_h _max_h
            _lines=$(printf '%s' "$_confirm_body" | awk 'END {print NR}')
            _term_h=$(tput lines 2>/dev/null || echo 24)
            _max_h=$(( _term_h - 2 ))
            [ "$_max_h" -lt 14 ] && _max_h=14
            _h=$(( _lines + 8 ))
            [ "$_h" -gt "$_max_h" ] && _h="$_max_h"
            [ "$_h" -lt 14 ] && _h=14
            if ! whiptail --backtitle "$TUI_BACKTITLE" \
                          --title "Confirm Installation" \
                          --yes-button "Install" --no-button "Cancel" \
                          --scrolltext \
                          --yesno "$_confirm_body" "$_h" 78; then
                print_status "Installation cancelled"
                exit 0
            fi
        else
            if ! tui_yesno "Confirm Installation" \
                "Install BunkerWeb $BUNKERWEB_VERSION (type: ${INSTALL_TYPE:-full}) with the chosen configuration?" "yes"; then
                print_status "Installation cancelled"
                exit 0
            fi
        fi
    fi

    # Docker mode: the operator has now confirmed the configuration (above) —
    # generate the compose stack and bring it up, then exit. The Linux-package
    # phases below are skipped entirely.
    if [ "$DOCKER_MODE" = "yes" ]; then
        docker_install_flow
        exit 0
    fi

    # Gate phase complete — persists the full config snapshot used for resume.
    [ "$_BW_RESUMING" = "yes" ] || _bw_phase_done preferences

    # upgrade_only() exits earlier — everything below runs only on a FRESH install.
    # Each install phase below is checkpointed: on resume the completed phases
    # are skipped and the interrupted one re-runs from scratch (the install
    # functions are idempotent).

    if _bw_phase_pending nginx; then
        case "$DISTRO_ID" in
            "debian"|"ubuntu")
                install_nginx_debian
                ;;
            "fedora")
                install_nginx_fedora
                ;;
            "rhel"|"rocky"|"almalinux"|"centos")
                install_nginx_rhel
                ;;
            "freebsd")
                install_nginx_freebsd
                ;;
        esac
        _bw_phase_done nginx
    fi

    if _bw_phase_pending crowdsec; then
        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            install_crowdsec
        fi
        _bw_phase_done crowdsec
    fi

    if _bw_phase_pending redis; then
        if [ "$REDIS_INSTALL" = "yes" ]; then
            install_redis
        fi
        _bw_phase_done redis
    fi

    if _bw_phase_pending database; then
        # Wire DATABASE_URI into variables.env BEFORE postinstall runs the scheduler.
        if [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ] || [ "$DB_INSTALL" = "external" ]; then
            install_database
        fi
        _bw_phase_done database
    fi

    if _bw_phase_pending host_config; then
        # Wire UI_HOST for every UI-bearing install. Without it the default-server-http/ui.conf
        # template is empty → /setup, /login, /logout unreachable via the BunkerWeb listener.
        case "${INSTALL_TYPE:-full}" in
            full|ui|"")
                apply_ui_host_config
                ;;
            manager)
                if [ "${SERVICE_UI:-yes}" != "no" ] || [ "${MANAGER_UI_DEFERRED:-no}" = "yes" ]; then
                    apply_ui_host_config
                fi
                ;;
            scheduler)
                # Pre-create templates so postinst's minimal versions don't win (writers are idempotent).
                write_default_variables_env_template /etc/bunkerweb/variables.env
                write_default_scheduler_env_template /etc/bunkerweb/scheduler.env
                # Persist --instances / --dns-resolvers / --api-https (no configure_* runs for scheduler-only).
                set_config_kv /etc/bunkerweb/variables.env "SERVER_NAME" ""
                if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
                    set_config_kv /etc/bunkerweb/variables.env "BUNKERWEB_INSTANCES" "$BUNKERWEB_INSTANCES_INPUT"
                fi
                if [ -n "$DNS_RESOLVERS_INPUT" ]; then
                    set_config_kv /etc/bunkerweb/variables.env "DNS_RESOLVERS" "$DNS_RESOLVERS_INPUT"
                fi
                if [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
                    set_config_kv /etc/bunkerweb/variables.env "API_LISTEN_HTTPS" "yes"
                fi
                # Redis/CrowdSec → variables.env (else `--scheduler-only --redis` would silently drop USE_REDIS).
                apply_optional_integrations /etc/bunkerweb/variables.env
                ;;
            api)
                # api.env template carries the FastAPI/biscuit/TLS commented docs the postinst's minimal file lacks.
                write_default_variables_env_template /etc/bunkerweb/variables.env
                write_default_api_env_template /etc/bunkerweb/api.env
                # FastAPI rate limiter reads USE_REDIS/REDIS_HOST from variables.env.
                apply_optional_integrations /etc/bunkerweb/variables.env
                ;;
        esac

        # Pre-create UI admin in ui.env BEFORE bunkerweb-ui starts (gunicorn pre-fork picks it up).
        # Manager's deferred-start path goes through start_manager_ui below. Idempotent.
        if [ "$UI_ADMIN_CREATE" = "yes" ] \
            && { [ "$INSTALL_TYPE" = "full" ] || [ "$INSTALL_TYPE" = "ui" ] || [ -z "$INSTALL_TYPE" ]; }; then
            create_ui_admin_user
        fi
        _bw_phase_done host_config
    fi

    # Prevent postinstall from starting services we still need to configure.
    # ALWAYS runs (fresh + resume): pure SERVICE_* env derivation consumed by the
    # package phase below; SERVICE_* values are not persisted in the state file.
    if [ "$INSTALL_TYPE" = "manager" ]; then
        export SERVICE_SCHEDULER=no
        # Defer UI start when admin creds / self-signed TLS still to provision.
        if [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
            export SERVICE_UI=no
            MANAGER_UI_DEFERRED="yes"
        fi
    elif [ "$INSTALL_TYPE" = "worker" ]; then
        export SERVICE_BUNKERWEB=no
    elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
        # Propagate --api to postinstall — defaults to no otherwise.
        export SERVICE_API="${SERVICE_API:-no}"
        # Only defer start if we have config to apply.
        if [ -n "$DNS_RESOLVERS_INPUT" ] || [ -n "$API_LISTEN_HTTPS_INPUT" ] || [ -n "$REDIS_HOST_INPUT" ] || [ "$REDIS_INSTALL" = "yes" ] || [ -n "$REDIS_PORT_INPUT" ] || [ -n "$REDIS_DATABASE_INPUT" ] || [ -n "$REDIS_USERNAME_INPUT" ] || [ -n "$REDIS_PASSWORD_INPUT" ] || [ -n "$REDIS_SSL_INPUT" ] || [ -n "$REDIS_SSL_VERIFY_INPUT" ] || [ "$CROWDSEC_INSTALL" = "yes" ] || [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ] || [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ] || [ "$DB_INSTALL" = "external" ]; then
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            # Defer API too — boots after DSN/Redis settings land in variables.env.
            if [ "$SERVICE_API" = "yes" ]; then
                FULL_API_DEFERRED="yes"
                export SERVICE_API=no
            fi
        fi
    fi

    if _bw_phase_pending package; then
        case "$DISTRO_ID" in
            "debian"|"ubuntu")
                install_bunkerweb_debian
                ;;
            "fedora")
                install_bunkerweb_rpm
                ;;
            "rhel"|"rocky"|"almalinux"|"centos")
                install_bunkerweb_rpm
                ;;
            "freebsd")
                install_bunkerweb_freebsd
                ;;
        esac
        _bw_phase_done package
    fi

    # UI_HOST + MULTISITE already written pre-install via apply_ui_host_config;
    # postinstall.sh:189 skips its own template on populated variables.env.

    if _bw_phase_pending configure; then
        if [ "$INSTALL_TYPE" = "manager" ]; then
            configure_manager_api_defaults
            if [ "$MANAGER_UI_DEFERRED" = "yes" ]; then
                unset SERVICE_UI
                start_manager_ui
            elif [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
                # Hardening opted in via flags after UI started — apply + restart.
                start_manager_ui
            fi
        elif [ "$INSTALL_TYPE" = "worker" ]; then
            configure_worker_api_whitelist
        elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
            configure_full_config
        fi

        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            if [ "$DISTRO_ID" = "freebsd" ]; then
                sysrc crowdsec_enable=YES >/dev/null 2>&1
                service crowdsec restart || service crowdsec start || print_warning "Could not start crowdsec"
                sleep 2
                service crowdsec status >/dev/null 2>&1 || print_warning "CrowdSec may not be running"
            else
                run_cmd systemctl restart crowdsec
                sleep 2
                systemctl status crowdsec --no-pager -l || print_warning "CrowdSec may not be running"
            fi
        fi
        _bw_phase_done configure
    fi

    show_final_info
    # Install finished — wipe the (secret-bearing) state file.
    _bw_state_clear
}

main "$@"
