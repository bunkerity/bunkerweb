#!/bin/bash

# BunkerWeb Easy Install Script
# Automatically installs BunkerWeb on supported Linux distributions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
# Hardcoded default version (immutable reference)
DEFAULT_BUNKERWEB_VERSION="1.6.10~rc6"
# Mutable effective version (can be overridden by --version)
BUNKERWEB_VERSION="$DEFAULT_BUNKERWEB_VERSION"
NGINX_VERSION=""
ENABLE_WIZARD=""
FORCE_INSTALL="no"
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
REDIS_FLAVOR=""               # "redis" | "valkey" — both are wire-compatible
REDIS_MAXMEMORY_MB=""         # 0 = unlimited (distro default); >0 = applied as <N>mb
REDIS_MAXMEMORY_POLICY="volatile-lru" # Bounded eviction targeting keys with TTL — protects permanent bans and unexpiring config keys while transient counters evict first
DB_INSTALL=""
DB_NAME_INPUT="bw_db"
DB_USER_INPUT="bunkerweb"
DB_PASSWORD_INPUT=""
DB_PASSWORD_GENERATED=""
DB_DSN_GENERATED=""
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

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to run command with error checking
run_cmd() {
    echo -e "${BLUE}[CMD]${NC} $*"
    if ! "$@"; then
        print_error "Command failed: $*"
        exit 1
    fi
}

set_config_kv() {
    local config_file="$1"
    local key="$2"
    local value="$3"

    if grep -q "^${key}=" "$config_file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$config_file"
    else
        echo "${key}=${value}" >> "$config_file"
    fi
}

ensure_config_file() {
    local config_file="$1"

    if [ ! -d /etc/bunkerweb ]; then
        mkdir -p /etc/bunkerweb
    fi

    if [ ! -f "$config_file" ]; then
        touch "$config_file"
    fi

    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true
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
        # Last-resort fallback (no /dev/urandom and no openssl)
        out=$(date +%s%N | sha256sum 2>/dev/null | head -c "$length")
    fi

    printf '%s' "$out"
}

# Generate a UI admin password that satisfies the BunkerWeb regex
# (>= 8 chars, at least one lower, upper, digit, special). 18 base chars + Aa1!.
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

# ---------------------------------------------------------------------------
# Default env-file templates.
#
# These mirror the templates that the BunkerWeb start scripts write when the
# corresponding env file is absent (see src/linux/scripts/{start,bunkerweb-ui,
# bunkerweb-scheduler,bunkerweb-api}.sh). The installer needs its own copy
# because it creates these files BEFORE the start scripts ever run, so the
# operator would otherwise end up with a sparse file containing only the
# values the installer pinned — losing the helpful commented defaults that
# document every supported knob.
#
# Each helper only writes the template when the file is empty/missing.
# If the file already has content (re-run, manual edit), it's left alone and
# the caller's set_config_kv writes simply patch the relevant lines.
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
detect_os() {
    DISTRO_ID=""
    DISTRO_VERSION=""
    DISTRO_CODENAME=""

    # Check for FreeBSD first
    if [ "$(uname)" = "FreeBSD" ]; then
        DISTRO_ID="freebsd"
        DISTRO_VERSION=$(freebsd-version -u 2>/dev/null | cut -d'-' -f1 || uname -r | cut -d'-' -f1)
        DISTRO_CODENAME=""
        print_status "Detected OS: FreeBSD $DISTRO_VERSION"
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
        print_error "Unable to detect operating system"
        exit 1
    fi

    print_status "Detected OS: $DISTRO_ID $DISTRO_VERSION"
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
            print_warning "Architecture $SYSTEM_ARCH has not been validated with the easy install script."
            if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                read -p "Continue anyway? (y/N): " -r
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    exit 1
                fi
            fi
            ;;
    esac
    export NORMALIZED_ARCH
}

# Function to ask user preferences
ask_user_preferences() {
    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        echo
        print_step "Configuration Options"
        echo

        # Ask about installation type
        if [ -z "$INSTALL_TYPE" ]; then
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}📦 Installation Type${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Choose the type of installation based on your needs:"
            echo "  1) Full Stack (default): All-in-one installation (BunkerWeb, Scheduler, UI)."
            echo "  2) Manager: Installs Scheduler and UI to manage remote BunkerWeb workers."
            echo "  3) Worker: Installs only the BunkerWeb instance, to be managed remotely."
            echo "  4) Scheduler Only: Installs only the Scheduler component."
            echo "  5) Web UI Only: Installs only the Web UI component."
            echo "  6) API Only: Installs only the API service component."
            echo
            while true; do
                echo -e "${YELLOW}Select installation type (1-6) [1]:${NC} "
                read -p "" -r
                REPLY=${REPLY:-1}
                case $REPLY in
                    1) INSTALL_TYPE="full"; break ;;
                    2) INSTALL_TYPE="manager"; break ;;
                    3) INSTALL_TYPE="worker"; break ;;
                    4) INSTALL_TYPE="scheduler"; break ;;
                    5) INSTALL_TYPE="ui"; break ;;
                    6) INSTALL_TYPE="api"; break ;;
                    *) echo "Invalid option. Please choose a number between 1 and 6." ;;
                esac
            done
        fi

        if [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]]; then
            if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🔗 BunkerWeb Instances Configuration${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "Please provide the list of BunkerWeb instances (workers) to manage."
                echo "Format: a space-separated list of IP addresses or hostnames."
                echo "Example: 192.168.1.10 192.168.1.11"
                echo "Leave empty to add workers later."
                echo
                echo -e "${YELLOW}Enter BunkerWeb instances (or press Enter to skip):${NC} "
                read -p "" -r BUNKERWEB_INSTANCES_INPUT
                if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                    print_warning "No instances configured. You can add workers later."
                    print_status "See: https://docs.bunkerweb.io/latest/advanced/#3-manage-workers"
                fi
            fi
        fi

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            local detected_ip=""
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🌐 Manager API Binding${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The manager listens on 0.0.0.0 but only whitelists explicit local IPs for API access."
            echo "We'll detect the best local IPv4 to whitelist, or you can provide one manually."
            echo
            detected_ip=$(get_primary_ipv4)
            if [ -n "$detected_ip" ]; then
                while true; do
                    echo -e "${YELLOW}Whitelist detected IP $detected_ip for API access? (Y/n):${NC}"
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            MANAGER_IP_INPUT="$detected_ip"
                            break
                            ;;
                        [Nn]*)
                            echo
                            echo -e "${BLUE}----------------------------------------${NC}"
                            echo -e "${BLUE}✍️  Manual Manager IP Entry${NC}"
                            echo -e "${BLUE}----------------------------------------${NC}"
                            echo "Enter the IPv4 address you want to whitelist for manager API access."
                            prompt_for_local_ipv4 MANAGER_IP_INPUT
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            else
                print_warning "Unable to detect a local IPv4 automatically."
                echo -e "${BLUE}----------------------------------------${NC}"
                echo -e "${BLUE}✍️  Manual Manager IP Entry${NC}"
                echo -e "${BLUE}----------------------------------------${NC}"
                echo "Enter the IPv4 address you want to whitelist for manager API access."
                prompt_for_local_ipv4 MANAGER_IP_INPUT
            fi
        fi

        if [ "$INSTALL_TYPE" = "worker" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🛡️  Manager API Access${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Provide the IP address (or space-separated list) of the manager/scheduler that will control this worker."
            echo "The worker API listens on 0.0.0.0, and these IPs will be whitelisted automatically."
            echo
            while true; do
                echo -e "${YELLOW}Enter manager IP address(es):${NC} "
                read -p "" -r MANAGER_IP_INPUT
                if [ -n "$MANAGER_IP_INPUT" ]; then
                    break
                else
                    print_warning "This field cannot be empty for Worker installations."
                fi
            done
        fi

        # Ask about custom DNS resolvers for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$DNS_RESOLVERS_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🔍 DNS Resolvers Configuration${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "BunkerWeb needs DNS resolvers for domain resolution."
            echo "Default: 9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4 (Quad9 and Google DNS)"
            echo
            while true; do
                echo -e "${YELLOW}Use custom DNS resolvers? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*)
                        echo -e "${YELLOW}Enter space-separated DNS resolver IPs:${NC} "
                        read -p "" -r DNS_RESOLVERS_INPUT
                        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
                            break
                        else
                            print_warning "DNS resolvers cannot be empty. Please enter at least one resolver."
                        fi
                        ;;
                    [Nn]*|"")
                        DNS_RESOLVERS_INPUT="9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about internal API HTTPS communication for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$API_LISTEN_HTTPS_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🔒 Internal API HTTPS Communication${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The scheduler/manager can communicate with BunkerWeb/worker instances via HTTPS"
            echo "for internal API communication (not the public API service)."
            echo "Default: HTTP only (no HTTPS)"
            echo
            while true; do
                echo -e "${YELLOW}Enable HTTPS for internal API communication? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*)
                        API_LISTEN_HTTPS_INPUT="yes"
                        break
                        ;;
                    [Nn]*|"")
                        API_LISTEN_HTTPS_INPUT="no"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about setup wizard
        if [ "$INSTALL_TYPE" = "manager" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🧙 Setup Wizard Not Available${NC}"
            echo -e "${BLUE}========================================${NC}"
            if [ "$ENABLE_WIZARD" = "yes" ]; then
                print_warning "Setup wizard cannot be enabled for manager mode; it will be disabled."
            fi
            echo "Manager installations are not compatible with the setup wizard."
            echo "The UI can still be started normally without the wizard."
            ENABLE_WIZARD="no"
        elif [ -z "$ENABLE_WIZARD" ]; then
            if [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "scheduler" ] || [ "$INSTALL_TYPE" = "api" ]; then
                ENABLE_WIZARD="no"
            else
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🧙 BunkerWeb Setup Wizard${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "The BunkerWeb setup wizard provides a web-based interface to:"
                echo "  • Complete initial configuration easily"
                echo "  • Set up your first protected service"
                echo "  • Configure SSL/TLS certificates"
                echo "  • Access the management interface"
                echo
                while true; do
                    echo -e "${YELLOW}Would you like to enable the setup wizard? (Y/n):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            ENABLE_WIZARD="yes"
                            break
                            ;;
                        [Nn]*)
                            ENABLE_WIZARD="no"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            fi
        fi

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$SERVICE_UI" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🖥  Manager Web UI${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The setup wizard is disabled, but you can still start the Web UI service."
            echo "Do you want the Web UI to run after installation?"
            while true; do
                echo -e "${YELLOW}Start the Web UI service? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Nn]*)
                        export SERVICE_UI="no"
                        break
                        ;;
                    [Yy]*|"")
                        export SERVICE_UI="yes"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Manager-mode UI hardening: opt-in admin user creation.
        if [ "$INSTALL_TYPE" = "manager" ] && [ "${SERVICE_UI:-yes}" != "no" ] && [ -z "$UI_ADMIN_CREATE" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}👤 Manager Web UI Admin User${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The setup wizard is disabled in manager mode. The installer can create the first"
            echo "admin user for you now and provision the credentials directly into /etc/bunkerweb/ui.env."
            echo
            echo "Note: the Web UI listens on 127.0.0.1:7000 by default — keep it behind a reverse"
            echo "proxy or an SSH tunnel for remote access. (Local-only listening is the BunkerWeb"
            echo "package default; the installer does not change it.)"
            echo
            while true; do
                echo -e "${YELLOW}Create admin user now? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Nn]*)
                        UI_ADMIN_CREATE="no"
                        break
                        ;;
                    [Yy]*|"")
                        UI_ADMIN_CREATE="yes"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done

            if [ "$UI_ADMIN_CREATE" = "yes" ]; then
                if [ -z "$UI_ADMIN_USERNAME_INPUT" ]; then
                    echo -e "${YELLOW}Username [admin]:${NC} "
                    read -p "" -r UI_ADMIN_USERNAME_INPUT
                    UI_ADMIN_USERNAME_INPUT=${UI_ADMIN_USERNAME_INPUT:-admin}
                fi

                if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
                    echo "Password rules: 8+ chars, at least one lowercase, one uppercase, one digit, one special."
                    while true; do
                        echo -e "${YELLOW}Password (leave empty to auto-generate):${NC} "
                        read -p "" -r UI_ADMIN_PASSWORD_INPUT
                        if [ -z "$UI_ADMIN_PASSWORD_INPUT" ]; then
                            break
                        fi
                        if validate_ui_admin_password "$UI_ADMIN_PASSWORD_INPUT"; then
                            break
                        fi
                        print_warning "Password does not meet the rules. Try again or leave empty to auto-generate."
                        UI_ADMIN_PASSWORD_INPUT=""
                    done
                fi
            fi
        fi

        # Manager-mode UI hardening: opt-in self-signed HTTPS.
        if [ "$INSTALL_TYPE" = "manager" ] && [ "${SERVICE_UI:-yes}" != "no" ] && [ -z "$UI_SELFSIGNED_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🔒 Manager Web UI HTTPS (self-signed)${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Enable HTTPS on the local Web UI listener with a self-signed certificate?"
            echo "This is gunicorn-native TLS — no BunkerWeb in front needed."
            echo "  Cert: /var/lib/bunkerweb/ui-tls/cert.pem"
            echo "  Key:  /var/lib/bunkerweb/ui-tls/key.pem"
            echo "  CN:   \$(hostname -f)   Validity: 365 days   RSA 2048"
            echo
            while true; do
                echo -e "${YELLOW}Enable self-signed HTTPS? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Nn]*)
                        UI_SELFSIGNED_INPUT="no"
                        break
                        ;;
                    [Yy]*|"")
                        UI_SELFSIGNED_INPUT="yes"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about CrowdSec installation
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "api" ]]; then
            if [ -z "$CROWDSEC_INSTALL" ] || [ "$CROWDSEC_INSTALL" = "no" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🦙 CrowdSec Intrusion Prevention${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "CrowdSec is a community-powered, open-source intrusion prevention engine that analyzes logs in real time to detect, block and share intelligence on malicious IPs."
                echo "It seamlessly integrates with BunkerWeb for automated threat remediation."
                echo
                while true; do
                    echo -e "${YELLOW}Would you like to automatically install and configure CrowdSec? (Y/n):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            CROWDSEC_INSTALL="yes"
                            break
                            ;;
                        [Nn]*)
                            CROWDSEC_INSTALL="no"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            fi
        else
            # CrowdSec not applicable for manager, worker, scheduler-only, ui-only, or api-only installations
            CROWDSEC_INSTALL="no"
        fi

        # Ask about API service enablement (not applicable for worker, scheduler-only, ui-only, or api-only)
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "api" ]] && [ -z "$SERVICE_API" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🧩 BunkerWeb API Service${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The BunkerWeb API provides a programmatic interface (FastAPI) to manage instances,"
            echo "perform actions (reload/stop), and integrate with external systems."
            echo "It is optional and disabled by default on Linux installations."
            echo
            while true; do
                echo -e "${YELLOW}Enable the API service? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*) SERVICE_API=yes; break ;;
                    ""|[Nn]*) SERVICE_API=no; break ;;
                    *) echo "Please answer yes (y) or no (n)." ;;
                esac
            done
        elif [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
            # API service not applicable for these installation types
            SERVICE_API=no
        fi

        # Ask about AppSec installation if CrowdSec is chosen
        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🛡️ CrowdSec Application Security (AppSec)${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "CrowdSec Application Security Component (AppSec) adds advanced application security, turning CrowdSec into a full WAF."
            echo "It's optional, installs alongside CrowdSec, and integrates seamlessly with the engine."
            echo
            while true; do
                echo -e "${YELLOW}Would you like to install and configure the CrowdSec AppSec Component? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*|"")
                        CROWDSEC_APPSEC_INSTALL="yes"
                        break
                        ;;
                    [Nn]*)
                        CROWDSEC_APPSEC_INSTALL="no"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about Redis configuration
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || -z "$INSTALL_TYPE" ]]; then
            if [ -z "$REDIS_INSTALL" ] || [ "$REDIS_INSTALL" = "no" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🧠 Redis (HA persistence + worker sync)${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "Redis/Valkey is what makes BunkerWeb production-ready:"
                echo "  • Persists metrics and bans across restarts (otherwise kept in memory only)"
                echo "  • Synchronises bans/reports between workers in HA setups"
                echo "  • Stores UI session data so logged-in users survive a UI restart"
                echo "Without Redis this state is lost on restart and not shared between BunkerWeb instances."
                echo "For HA, you can also use Redis Sentinel for automatic failover."
                echo "You can install Redis locally or point to an existing Redis server."
                echo
                while true; do
                    echo -e "${YELLOW}Enable Redis integration? (y/N):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Yy]*)
                            REDIS_INSTALL="yes"
                            break
                            ;;
                        [Nn]*|"")
                            REDIS_INSTALL="no"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            fi

            if [ "$REDIS_INSTALL" = "yes" ]; then
                echo
                echo -e "${BLUE}----------------------------------------${NC}"
                echo -e "${BLUE}🗄️  Redis Instance${NC}"
                echo -e "${BLUE}----------------------------------------${NC}"
                while true; do
                    echo -e "${YELLOW}Install Redis locally on this host? (Y/n):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Nn]*)
                            REDIS_INSTALL="no"
                            break
                            ;;
                        [Yy]*|"")
                            REDIS_INSTALL="yes"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done

                # When installing locally, let the user pick redis vs valkey.
                # Both are wire-compatible — BunkerWeb's USE_REDIS path works with either.
                if [ "$REDIS_INSTALL" = "yes" ] && [ -z "$REDIS_FLAVOR" ]; then
                    echo
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo -e "${BLUE}🔀 Server: Redis or Valkey${NC}"
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo "Both speak the same wire protocol — BunkerWeb works with either."
                    echo "  1. redis  (widest distro coverage; default)"
                    echo "  2. valkey (open-source fork under the Linux Foundation)"
                    echo "If the chosen package is missing from your distro repos, the installer"
                    echo "will warn and fall back to the other one."
                    echo
                    while true; do
                        echo -e "${YELLOW}Choice [1]:${NC} "
                        read -p "" -r
                        case $REPLY in
                            ""|"1"|"redis"|"Redis")
                                REDIS_FLAVOR="redis"
                                break
                                ;;
                            "2"|"valkey"|"Valkey")
                                REDIS_FLAVOR="valkey"
                                break
                                ;;
                            *)
                                echo "Please answer 1 or 2."
                                ;;
                        esac
                    done
                fi

                # Manager mode: ask which interface Redis should bind to so workers can reach it.
                # Full stack: Redis stays on 127.0.0.1 — no prompt.
                if [ "$REDIS_INSTALL" = "yes" ] && [ "$INSTALL_TYPE" = "manager" ] && [ -z "$REDIS_BIND_INPUT" ]; then
                    echo
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo -e "${BLUE}🌐 Redis Bind Address${NC}"
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo "Workers connect to this Redis from the network."
                    echo "  • 0.0.0.0       — accept connections on every interface (default for HA, requires firewall + password)"
                    echo "  • 10.x.y.z      — pin Redis to a specific private interface (recommended for VPC/LAN setups)"
                    echo "  • 127.0.0.1     — local only; workers will NOT be able to reach it"
                    echo
                    echo -e "${YELLOW}Bind address [0.0.0.0]:${NC} "
                    read -p "" -r REDIS_BIND_INPUT
                    REDIS_BIND_INPUT=${REDIS_BIND_INPUT:-0.0.0.0}

                    if [ "$REDIS_BIND_INPUT" = "0.0.0.0" ]; then
                        print_warning "Redis will accept connections from every network interface."
                        print_warning "Strongly recommended: firewall port 6379 to your worker subnet, and set a Redis password."
                    fi

                    if [ "$REDIS_BIND_INPUT" != "127.0.0.1" ] && [ -z "$REDIS_PASSWORD_INPUT" ] && [ "$REDIS_AUTOPASS" = "yes" ]; then
                        while true; do
                            echo -e "${YELLOW}Generate a random password and set REQUIREPASS automatically? (Y/n):${NC} "
                            read -p "" -r
                            case $REPLY in
                                [Nn]*)
                                    REDIS_AUTOPASS="no"
                                    break
                                    ;;
                                [Yy]*|"")
                                    REDIS_AUTOPASS="yes"
                                    break
                                    ;;
                                *)
                                    echo "Please answer yes (y) or no (n)."
                                    ;;
                            esac
                        done
                    fi
                fi

                # Memory cap prompt — runs for BOTH manager and full-stack local installs.
                # Best practice: bound memory + use volatile-lru so transient WAF counters evict
                # cleanly under pressure while permanent bans and unexpiring keys are preserved
                # (default Redis policy = noeviction, which rejects writes when full).
                if [ "$REDIS_INSTALL" = "yes" ] && [ -z "$REDIS_MAXMEMORY_MB" ]; then
                    echo
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo -e "${BLUE}🧠 ${_flavor_label:-Redis/Valkey} Memory Cap${NC}"
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo "Without a cap, ${_flavor_label:-Redis/Valkey} grows until the kernel OOM-kills it."
                    echo "The installer will apply maxmemory-policy=volatile-lru (recommended for"
                    echo "the WAF cache pattern — evicts the least-recently-used keys with TTL first,"
                    echo "preserving permanent bans and protecting recently active sessions)."
                    echo
                    echo "Pick a maximum memory size:"
                    echo "  1. 128 MB    — small/dev VMs (≤ 2 GB RAM)"
                    echo "  2. 256 MB    — recommended for most installs (4–8 GB RAM)"
                    echo "  3. 512 MB    — high-traffic / dedicated nodes (8 GB+ RAM)"
                    echo "  4. Custom    — enter your own value in MB"
                    echo "  5. Unlimited — keep distro defaults (NOT recommended)"
                    echo
                    while true; do
                        echo -e "${YELLOW}Choice [2]:${NC} "
                        read -p "" -r
                        case ${REPLY:-2} in
                            1) REDIS_MAXMEMORY_MB="128"; break ;;
                            2) REDIS_MAXMEMORY_MB="256"; break ;;
                            3) REDIS_MAXMEMORY_MB="512"; break ;;
                            4)
                                while true; do
                                    echo -e "${YELLOW}Memory cap in MB (e.g. 1024):${NC} "
                                    read -p "" -r _custom_mb
                                    if [[ "$_custom_mb" =~ ^[1-9][0-9]*$ ]]; then
                                        REDIS_MAXMEMORY_MB="$_custom_mb"
                                        break
                                    fi
                                    echo "Please enter a positive integer (MB)."
                                done
                                break
                                ;;
                            5)
                                REDIS_MAXMEMORY_MB="0"
                                print_warning "Skipping memory cap — ${_flavor_label:-Redis/Valkey} may consume all system RAM under load."
                                break
                                ;;
                            *)
                                echo "Please answer 1, 2, 3, 4 or 5."
                                ;;
                        esac
                    done
                fi

                if [ "$REDIS_INSTALL" = "no" ]; then
                    echo
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo -e "${BLUE}✍️  Existing Redis Configuration${NC}"
                    echo -e "${BLUE}----------------------------------------${NC}"
                    echo "Provide connection details for your existing Redis server."
                    echo
                    echo -e "${YELLOW}Redis host [127.0.0.1]:${NC} "
                    read -p "" -r REDIS_HOST_INPUT
                    REDIS_HOST_INPUT=${REDIS_HOST_INPUT:-127.0.0.1}
                    echo -e "${YELLOW}Redis port [6379]:${NC} "
                    read -p "" -r REDIS_PORT_INPUT
                    REDIS_PORT_INPUT=${REDIS_PORT_INPUT:-6379}
                    echo -e "${YELLOW}Redis database [0]:${NC} "
                    read -p "" -r REDIS_DATABASE_INPUT
                    REDIS_DATABASE_INPUT=${REDIS_DATABASE_INPUT:-0}
                    echo -e "${YELLOW}Redis username (optional):${NC} "
                    read -p "" -r REDIS_USERNAME_INPUT
                    echo -e "${YELLOW}Redis password (optional):${NC} "
                    read -p "" -r REDIS_PASSWORD_INPUT
                    while true; do
                        echo -e "${YELLOW}Use SSL/TLS for Redis connection? (y/N):${NC} "
                        read -p "" -r
                        case $REPLY in
                            [Yy]*)
                                REDIS_SSL_INPUT="yes"
                                break
                                ;;
                            [Nn]*|"")
                                REDIS_SSL_INPUT="no"
                                break
                                ;;
                            *)
                                echo "Please answer yes (y) or no (n)."
                                ;;
                        esac
                    done
                    if [ "$REDIS_SSL_INPUT" = "yes" ]; then
                        while true; do
                            echo -e "${YELLOW}Verify Redis SSL certificate? (Y/n):${NC} "
                            read -p "" -r
                            case $REPLY in
                                [Nn]*)
                                    REDIS_SSL_VERIFY_INPUT="no"
                                    break
                                    ;;
                                [Yy]*|"")
                                    REDIS_SSL_VERIFY_INPUT="yes"
                                    break
                                    ;;
                                *)
                                    echo "Please answer yes (y) or no (n)."
                                    ;;
                            esac
                        done
                    fi
                fi
            fi
        else
            # Redis only applicable for full or manager installations
            REDIS_INSTALL="no"
        fi

        # Database auto-install (full + manager only)
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || -z "$INSTALL_TYPE" ]]; then
            if [ -z "$DB_INSTALL" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🗄️  Database${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "BunkerWeb stores configuration, services and jobs in a database."
                echo "Without a choice it falls back to SQLite — safe for single-node trials,"
                echo "not recommended for HA or any setup with more than one BunkerWeb instance."
                echo
                echo "  1. MariaDB (recommended)"
                echo "  2. PostgreSQL"
                echo "  3. Skip (keep SQLite, or configure DATABASE_URI manually later)"
                echo
                while true; do
                    echo -e "${YELLOW}Database choice [1]:${NC} "
                    read -p "" -r
                    case $REPLY in
                        ""|"1"|"mariadb"|"MariaDB")
                            DB_INSTALL="mariadb"
                            break
                            ;;
                        "2"|"postgresql"|"postgres"|"PostgreSQL")
                            DB_INSTALL="postgresql"
                            break
                            ;;
                        "3"|"skip"|"none"|"sqlite"|"SQLite")
                            DB_INSTALL="none"
                            break
                            ;;
                        *)
                            echo "Please answer 1, 2 or 3."
                            ;;
                    esac
                done
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
                echo
                echo -e "${BLUE}----------------------------------------${NC}"
                echo -e "${BLUE}✍️  Database Configuration${NC}"
                echo -e "${BLUE}----------------------------------------${NC}"
                echo -e "${YELLOW}Database name [${DB_NAME_INPUT}]:${NC} "
                read -p "" -r _db_answer
                DB_NAME_INPUT=${_db_answer:-$DB_NAME_INPUT}
                echo -e "${YELLOW}Database user [${DB_USER_INPUT}]:${NC} "
                read -p "" -r _db_answer
                DB_USER_INPUT=${_db_answer:-$DB_USER_INPUT}
                if [ -z "$DB_PASSWORD_INPUT" ]; then
                    while true; do
                        echo -e "${YELLOW}Generate a random database password? (Y/n):${NC} "
                        read -p "" -r
                        case $REPLY in
                            [Yy]*|"")
                                DB_PASSWORD_INPUT=""
                                break
                                ;;
                            [Nn]*)
                                echo -e "${YELLOW}Database password (avoid quotes/backslashes):${NC} "
                                read -p "" -r DB_PASSWORD_INPUT
                                if [ -z "$DB_PASSWORD_INPUT" ]; then
                                    echo "Empty password is not allowed."
                                    continue
                                fi
                                break
                                ;;
                            *)
                                echo "Please answer yes (y) or no (n)."
                                ;;
                        esac
                    done
                fi
            fi
        else
            DB_INSTALL="none"
        fi

        echo
        print_status "Configuration summary:"
        echo "  🛡 BunkerWeb version: $BUNKERWEB_VERSION"
        case "$INSTALL_TYPE" in
            "full"|"") echo "  📦 Installation type: Full Stack" ;;
            "manager") echo "  📦 Installation type: Manager" ;;
            "worker") echo "  📦 Installation type: Worker" ;;
            "scheduler") echo "  📦 Installation type: Scheduler Only" ;;
            "ui") echo "  📦 Installation type: Web UI Only" ;;
            "api") echo "  📦 Installation type: API Only" ;;
        esac
        if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
            echo "  🔗 BunkerWeb instances: $BUNKERWEB_INSTANCES_INPUT"
        fi
        if [ -n "$MANAGER_IP_INPUT" ]; then
            echo "  📡 Manager API whitelist: $MANAGER_IP_INPUT"
        fi
        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
            echo "  🔍 DNS resolvers: $DNS_RESOLVERS_INPUT"
        fi
        if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
            echo "  🔒 Internal API HTTPS: Enabled"
        fi
        if [ "$INSTALL_TYPE" = "manager" ]; then
            echo "  🖥 Web UI service: $([ "${SERVICE_UI:-yes}" = "no" ] && echo "Disabled" || echo "Enabled")"
            echo "  🧙 Setup wizard: Disabled (not supported in manager mode)"
        else
            echo "  🧙 Setup wizard: $([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
        fi
        if [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" ]]; then
            echo "  🔌 API service: Not available for this mode"
        elif [ "${SERVICE_API:-no}" = "yes" ]; then
            echo "  🔌 API service: Enabled"
        else
            echo "  🔌 API service: Disabled"
        fi
        echo "  🖥 Operating system: $DISTRO_ID $DISTRO_VERSION"
        echo "  ⚙️ Architecture: ${SYSTEM_ARCH:-unknown}"
        echo "  🟢 NGINX version: $NGINX_VERSION"
        if [ "$INSTALL_TYPE" = "manager" ] || [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "api" ]; then
            echo "  🦙 CrowdSec: Not available for this mode"
        else
            if [ "$CROWDSEC_INSTALL" = "yes" ]; then
                if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
                    echo "  🦙 CrowdSec: Will be installed (with AppSec Component)"
                else
                    echo "  🦙 CrowdSec: Will be installed (without AppSec Component)"
                fi
            else
                echo "  🦙 CrowdSec: Not installed"
            fi
        fi
        if [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && -n "$INSTALL_TYPE" ]]; then
            echo "  🧠 Redis: Not available for this mode"
        else
            if [ "$REDIS_INSTALL" = "yes" ]; then
                _flavor_label="${REDIS_FLAVOR:-redis}"
                if [ "$INSTALL_TYPE" = "manager" ]; then
                    echo "  🧠 ${_flavor_label}: Will be installed locally, bind ${REDIS_BIND_INPUT:-0.0.0.0}"
                else
                    echo "  🧠 ${_flavor_label}: Will be installed and configured locally"
                fi
                if [ "$REDIS_AUTOPASS" = "yes" ] && [ "${REDIS_BIND_INPUT:-127.0.0.1}" != "127.0.0.1" ]; then
                    echo "  🔑 Redis password: Auto-generated (REQUIREPASS)"
                fi
                if [ -n "$REDIS_MAXMEMORY_MB" ]; then
                    if [ "$REDIS_MAXMEMORY_MB" = "0" ]; then
                        echo "  🧠 Memory cap: Unlimited (distro default — not recommended)"
                    else
                        echo "  🧠 Memory cap: ${REDIS_MAXMEMORY_MB} MB (policy: ${REDIS_MAXMEMORY_POLICY:-volatile-lru})"
                    fi
                fi
            elif [ -n "$REDIS_HOST_INPUT" ]; then
                echo "  🧠 Redis: Will use existing server at $REDIS_HOST_INPUT:${REDIS_PORT_INPUT:-6379}"
            else
                echo "  🧠 Redis: Not installed (metrics + bans will be in-memory only, lost on restart)"
            fi
        fi
        if [[ "$INSTALL_TYPE" != "full" && "$INSTALL_TYPE" != "manager" && -n "$INSTALL_TYPE" ]]; then
            : # DB auto-install only relevant for full/manager
        else
            case "$DB_INSTALL" in
                "mariadb")
                    echo "  🗄️  Database: MariaDB (auto-installed locally, db=${DB_NAME_INPUT}, user=${DB_USER_INPUT})"
                    ;;
                "postgresql")
                    echo "  🗄️  Database: PostgreSQL (auto-installed locally, db=${DB_NAME_INPUT}, user=${DB_USER_INPUT})"
                    ;;
                ""|"none")
                    echo "  🗄️  Database: SQLite (default — set DATABASE_URI later for production)"
                    ;;
            esac
        fi
        if [ "$INSTALL_TYPE" = "manager" ] && [ "${SERVICE_UI:-yes}" != "no" ]; then
            if [ "$UI_ADMIN_CREATE" = "yes" ]; then
                echo "  👤 UI admin user: Will be created (${UI_ADMIN_USERNAME_INPUT:-admin})"
            fi
            if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
                echo "  🔒 UI HTTPS: Self-signed certificate will be generated"
            fi
        fi
        echo
    fi
}

# Function to show RHEL database warning
show_rhel_database_warning() {
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]]; then
        echo
        print_warning "Important information for RHEL-based systems:"
        echo
        echo "If you plan to use an external database (recommended for production),"
        echo "you'll need to install the appropriate database client:"
        echo
        echo "  For MariaDB: dnf install mariadb"
        echo "  For MySQL:   dnf install mysql"
        echo "  For PostgreSQL: dnf install postgresql"
        echo
        echo "This is required for the BunkerWeb Scheduler to connect to your database."
        echo
        read -p "Press Enter to continue..." -r
    fi
}

check_supported_os() {
    case "$DISTRO_ID" in
        "freebsd")
            major_version=$(echo "$DISTRO_VERSION" | cut -d. -f1)
            if [[ "$major_version" != "13" && "$major_version" != "14" ]]; then
                print_warning "Only FreeBSD 13 and 14 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
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
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.0-1~$DISTRO_CODENAME"
            ;;
        "ubuntu")
            if [[ "$DISTRO_VERSION" != "22.04" && "$DISTRO_VERSION" != "24.04" ]]; then
                print_warning "Only Ubuntu 22.04 (Jammy) and 24.04 (Noble) are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.0-1~$DISTRO_CODENAME"
            ;;
        "fedora")
            if [[ "$DISTRO_VERSION" != "42" && "$DISTRO_VERSION" != "43" && "$DISTRO_VERSION" != "44" ]]; then
                print_warning "Only Fedora 42, 43 and 44 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.0"
            ;;
        "rhel"|"rocky"|"almalinux")
            major_version=$(echo "$DISTRO_VERSION" | cut -d. -f1)
            if [[ "$major_version" != "8" && "$major_version" != "9" && "$major_version" != "10" ]]; then
                print_warning "Only RHEL 8, 9, and 10 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.30.0"
            ;;
        *)
            print_error "Unsupported operating system: $DISTRO_ID"
            print_error "Supported distributions: Debian 12/13, Ubuntu 22.04/24.04, Fedora 42/43/44, RHEL 8/9/10, FreeBSD 13/14"
            exit 1
            ;;
    esac
}

# Function to check for port conflicts
check_ports() {
    if [[ "$INSTALL_TYPE" == "full" || "$INSTALL_TYPE" == "worker" || -z "$INSTALL_TYPE" ]]; then
        if command -v ss >/dev/null 2>&1; then
            if ss -tulpn | grep -E ":(80|443)\s" >/dev/null 2>&1; then
                print_warning "Port 80 or 443 appears to be in use."
                print_warning "Common conflict: Apache/httpd running."
                print_warning "Please stop conflicting services before proceeding."
                if [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
        fi
    fi
}

# Check if provided IPv4 belongs to a private (LAN) range
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

# Reject loopback (127.0.0.0/8) and link-local (169.254.0.0/16) addresses.
# Used as a last-resort filter when picking up public IPv4s on cloud hosts.
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

# Extract the first IPv4 address from a whitespace-separated list
extract_first_ipv4() {
    local input="$1"
    local token

    for token in $input; do
        if [[ $token =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
            echo "$token"
            return 0
        fi
    done

    # Always return 0 — callers detect "no IP found" by checking emptiness of
    # captured stdout. Returning non-zero here would, under `set -e`, kill the
    # entire script the moment anyone writes `var=$(extract_first_ipv4 "")`.
    echo ""
    return 0
}

# Prompt interactively for a local IPv4 address
prompt_for_local_ipv4() {
    local -n __target_var="$1"
    local answer=""
    local ip=""

    while true; do
        echo -e "${YELLOW}Enter the local IPv4 address to use:${NC} "
        read -p "" -r answer
        ip=$(extract_first_ipv4 "$answer")
        if [ -n "$ip" ]; then
            __target_var="$ip"
            return 0
        fi
        print_warning "Invalid IPv4 address. Please try again."
    done
}

# Function to determine the primary IPv4 address of the current host using only
# locally available routing/interface information (no external queries)
get_primary_ipv4() {
    local primary_ip=""
    local route_output=""
    local host_output=""
    local addr_output=""
    local prev=""
    local token=""
    local line=""
    local candidate=""

    # Best-practice: ask the kernel directly which source address it would use
    # to reach an external destination. This is a pure routing-table lookup
    # (no packet sent), respects policy routing / VRFs / multiple routing
    # tables, and reflects the address the host actually uses for outbound
    # traffic. TEST-NET-1 (RFC 5737, 192.0.2.0/24) is reserved for
    # documentation and is guaranteed to never route to a real host.
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

    # Fallback: no RFC1918 candidate found — accept any non-loopback, non-link-local
    # IPv4 (covers cloud VMs that only have public addresses).
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

    echo "$primary_ip"
}

# Enumerate global-scope IPv4 addresses with their interface names. Filters
# out loopback and link-local. Output format: "<ip> <iface>", one per line,
# with the kernel-chosen primary IP first when known.
enumerate_global_ipv4_candidates() {
    local addr_output line ip iface kernel_choice=""

    if ! command -v ip >/dev/null 2>&1; then
        return 0
    fi

    addr_output=$(ip -4 addr show scope global 2>/dev/null || true)
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

# Decide which IP to advertise in the post-install "Next steps" URLs.
# Order of precedence:
#   1. Explicit operator override (--server-ip / $SERVER_IP_INPUT)
#   2. Single global IPv4 on the host -> use it silently
#   3. No global IPv4 -> empty (caller falls back to the literal placeholder)
#   4. Multiple global IPv4s, non-interactive install -> kernel-chosen primary
#   5. Multiple global IPv4s, interactive install -> menu prompt with the
#      kernel-chosen primary preselected as default
#
# Result is published in $RESOLVED_SERVER_IP (a global, so menu prompts stay
# on stdout for the operator instead of being captured by a $(...) caller).
resolve_display_server_ip() {
    RESOLVED_SERVER_IP=""

    local provided
    provided=$(extract_first_ipv4 "${SERVER_IP_INPUT:-}")
    if [ -n "$provided" ]; then
        RESOLVED_SERVER_IP="$provided"
        return 0
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

    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}🌐 Server IP for the post-install URLs${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Multiple IPv4 addresses detected. Select the one clients will use to reach this server:"

    local i=1 ip iface
    for line in "${candidates[@]}"; do
        ip=${line%% *}
        iface=${line##* }
        if [ "$i" = "1" ]; then
            printf '  %d) %-18s on %-10s (default)\n' "$i" "$ip" "$iface"
        else
            printf '  %d) %-18s on %-10s\n' "$i" "$ip" "$iface"
        fi
        i=$((i + 1))
    done
    printf '  %d) Enter manually\n' "$i"
    local manual=$i
    echo

    local picked manual_ip=""
    while true; do
        echo -en "${YELLOW}Choice [1]: ${NC}"
        read -r picked
        picked=${picked:-1}
        if ! [[ $picked =~ ^[0-9]+$ ]] || [ "$picked" -lt 1 ] || [ "$picked" -gt "$manual" ]; then
            print_warning "Invalid selection, please choose 1-${manual}"
            continue
        fi
        if [ "$picked" = "$manual" ]; then
            prompt_for_local_ipv4 manual_ip
            RESOLVED_SERVER_IP="$manual_ip"
            return 0
        fi
        line=${candidates[$((picked - 1))]}
        RESOLVED_SERVER_IP="${line%% *}"
        return 0
    done
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
    local needs_reload=false

    if should_apply_redis_config; then
        print_status "Applying Redis configuration"
        apply_redis_config "$config_file"
        needs_reload=true
    fi

    if should_apply_crowdsec_config; then
        print_status "Applying CrowdSec configuration"
        apply_crowdsec_config "$config_file"
        needs_reload=true
    fi

    if [ -n "$needs_reload_var" ]; then
        if [ "$needs_reload" = true ]; then
            eval "$needs_reload_var=true"
        fi
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
            prompt_for_local_ipv4 whitelist_ip
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

    # Lay down the canonical variables.env template with commented defaults
    # (only effective on a fresh install — preserves any pre-existing edits),
    # then apply the manager-specific overrides on top via set_config_kv.
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
    # Enable multisite mode when the UI service is used.
    # Note: when manager-mode UI hardening is opted in, SERVICE_UI is forced to "no"
    # earlier in main() so the package postinstall doesn't start the UI before our
    # admin/TLS provisioning. start_manager_ui re-enables it afterwards. In that
    # deferred-UI flow the UI *is* going to run, so we must still write MULTISITE=yes.
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

# Ensure worker installations whitelist the selected manager/scheduler IPs
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

    if grep -q "^API_LISTEN_IP=" "$config_file"; then
        sed -i 's|^API_LISTEN_IP=.*|API_LISTEN_IP=0.0.0.0|' "$config_file"
    else
        echo "API_LISTEN_IP=0.0.0.0" >> "$config_file"
    fi

    if grep -q "^API_WHITELIST_IP=" "$config_file"; then
        sed -i "s|^API_WHITELIST_IP=.*|API_WHITELIST_IP=$whitelist_value|" "$config_file"
    else
        echo "API_WHITELIST_IP=$whitelist_value" >> "$config_file"
    fi

    # Configure custom DNS resolvers if provided
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        if grep -q "^DNS_RESOLVERS=" "$config_file"; then
            sed -i "s|^DNS_RESOLVERS=.*|DNS_RESOLVERS=$DNS_RESOLVERS_INPUT|" "$config_file"
        else
            echo "DNS_RESOLVERS=$DNS_RESOLVERS_INPUT" >> "$config_file"
        fi
    fi

    # Configure internal API HTTPS if enabled
    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        if grep -q "^API_LISTEN_HTTPS=" "$config_file"; then
            sed -i "s|^API_LISTEN_HTTPS=.*|API_LISTEN_HTTPS=yes|" "$config_file"
        else
            echo "API_LISTEN_HTTPS=yes" >> "$config_file"
        fi
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

# Configure full installation settings (DNS resolvers, API HTTPS, multisite)
configure_full_config() {
    local config_file="/etc/bunkerweb/variables.env"
    local needs_reload=false

    # Drop in the canonical variables.env template (with documented commented defaults)
    # only when the file doesn't yet exist; idempotent, preserves user edits on re-run.
    write_default_variables_env_template "$config_file"
    ensure_config_file "$config_file"

    # Configure custom DNS resolvers if provided
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        if grep -q "^DNS_RESOLVERS=" "$config_file"; then
            sed -i "s|^DNS_RESOLVERS=.*|DNS_RESOLVERS=$DNS_RESOLVERS_INPUT|" "$config_file"
        else
            echo "DNS_RESOLVERS=$DNS_RESOLVERS_INPUT" >> "$config_file"
        fi
        needs_reload=true
    fi

    # Configure internal API HTTPS if enabled
    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        if grep -q "^API_LISTEN_HTTPS=" "$config_file"; then
            sed -i "s|^API_LISTEN_HTTPS=.*|API_LISTEN_HTTPS=yes|" "$config_file"
        else
            echo "API_LISTEN_HTTPS=yes" >> "$config_file"
        fi
        needs_reload=true
    fi

    # Enable multisite mode when UI service is used
    if [ "$ENABLE_WIZARD" = "yes" ] || [ "${SERVICE_UI:-no}" = "yes" ]; then
        if grep -q "^MULTISITE=" "$config_file"; then
            sed -i "s|^MULTISITE=.*|MULTISITE=yes|" "$config_file"
        else
            echo "MULTISITE=yes" >> "$config_file"
        fi
        needs_reload=true
    fi

    apply_optional_integrations "$config_file" "needs_reload"

    # Start bunkerweb and the scheduler if any changes were made
    if [ "$needs_reload" = true ]; then
        print_status "Enabling and starting services with configured settings..."
        if [ "$DISTRO_ID" = "freebsd" ]; then
            sysrc bunkerweb_enable=YES >/dev/null 2>&1
            sysrc bunkerweb_scheduler_enable=YES >/dev/null 2>&1
            service bunkerweb start || true
            service bunkerweb_scheduler start || true
            if [ "$FULL_API_DEFERRED" = "yes" ]; then
                sysrc bunkerweb_api_enable=YES >/dev/null 2>&1
                service bunkerweb_api start || true
            fi
        else
            run_cmd systemctl enable --now bunkerweb
            run_cmd systemctl enable --now bunkerweb-scheduler
            if [ "$FULL_API_DEFERRED" = "yes" ]; then
                run_cmd systemctl enable --now bunkerweb-api
            fi
        fi
    fi
}

# Function to install NGINX on Debian/Ubuntu
install_nginx_debian() {
    print_step "Installing NGINX on Debian/Ubuntu"

    # Install prerequisites
    run_cmd apt update
    run_cmd apt install -y curl gnupg2 ca-certificates lsb-release

    if [ "$DISTRO_ID" = "debian" ]; then
        run_cmd apt install -y debian-archive-keyring
    elif [ "$DISTRO_ID" = "ubuntu" ]; then
        run_cmd apt install -y ubuntu-keyring
    fi

    # Add NGINX repository
    curl -fsSL https://nginx.org/keys/nginx_signing.key | gpg --dearmor | tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/$DISTRO_ID $DISTRO_CODENAME nginx" | tee /etc/apt/sources.list.d/nginx.list

    # Update and install NGINX
    run_cmd apt update
    run_cmd apt install -y "nginx=$NGINX_VERSION"

    # Hold NGINX package to prevent upgrades
    run_cmd apt-mark hold nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install NGINX on Fedora
install_nginx_fedora() {
    print_step "Installing NGINX on Fedora"

    # Install versionlock plugin
    run_cmd dnf install -y 'dnf-command(versionlock)'

    # Enable testing repository if needed
    if ! dnf info "nginx-$NGINX_VERSION" >/dev/null 2>&1; then
        print_status "Enabling updates-testing repository"
        run_cmd dnf config-manager setopt updates-testing.enabled=1
    fi

    # Install NGINX
    run_cmd dnf install -y "nginx-$NGINX_VERSION"

    # Lock NGINX version
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install NGINX on RHEL
install_nginx_rhel() {
    print_step "Installing NGINX on RHEL"

    # Install versionlock plugin
    run_cmd dnf install -y 'dnf-command(versionlock)'

    # Create NGINX repository file
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

    # Install NGINX
    run_cmd dnf install -y "nginx-$NGINX_VERSION"

    # Lock NGINX version
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install NGINX on FreeBSD
install_nginx_freebsd() {
    print_step "Installing NGINX on FreeBSD"

    # Update pkg database
    run_cmd pkg update -f

    # Install NGINX from packages
    run_cmd pkg install -y nginx

    # Lock NGINX package version
    run_cmd pkg lock -y nginx

    print_status "NGINX installed successfully"
}

# Function to install BunkerWeb on Debian/Ubuntu
install_bunkerweb_debian() {
    print_step "Installing BunkerWeb on Debian/Ubuntu"

    # Handle testing/dev version
    if [[ "$BUNKERWEB_VERSION" =~ (testing|dev) ]]; then
        print_status "Adding force-bad-version directive for testing/dev version"
        echo "force-bad-version" >> /etc/dpkg/dpkg.cfg
    fi

    # Set environment variables
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # Download and add BunkerWeb repository
    run_cmd curl -fsSL https://repo.bunkerweb.io/install/script.deb.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    run_cmd apt update
    run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"

    # Hold BunkerWeb package to prevent upgrades
    run_cmd apt-mark hold bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

# Function to install BunkerWeb on Fedora/RHEL
install_bunkerweb_rpm() {
    print_step "Installing BunkerWeb on $DISTRO_ID"

    # Offer to install EPEL on RHEL-family distros before installing BunkerWeb
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]] && ! rpm -q epel-release >/dev/null 2>&1; then
        if [ "$INSTALL_EPEL" = "yes" ]; then
            print_step "Installing EPEL repository (epel-release)"
            run_cmd dnf install -y epel-release
        elif [ "$INSTALL_EPEL" = "no" ]; then
            print_warning "EPEL repository not installed; continuing without epel-release."
        elif [ "$INTERACTIVE_MODE" = "yes" ]; then
            print_warning "EPEL repository is not installed."
            read -p "Install epel-release? (y/N): " -r
            if [[ $REPLY =~ ^[Yy]$ ]]; then
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

    # Set environment variables
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # Add BunkerWeb repository and install
    run_cmd curl -fsSL https://repo.bunkerweb.io/install/script.rpm.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    run_cmd dnf makecache
    run_cmd dnf install -y "bunkerweb-$BUNKERWEB_VERSION"

    # Lock BunkerWeb version
    run_cmd dnf versionlock add bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

# Function to install BunkerWeb on FreeBSD
install_bunkerweb_freebsd() {
    print_step "Installing BunkerWeb on FreeBSD"

    # Install required dependencies
    run_cmd pkg install -y bash python311 py311-pip curl libxml2 yajl gd sudo \
        lsof libmaxminddb postgresql16-client mariadb1011-client sqlite3 \
        openssl pcre2 lmdb ssdeep unzip gtar

    # Create nginx user and group if they don't exist
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

    # Download and install BunkerWeb package from GitHub releases or custom repo
    print_status "Installing BunkerWeb..."

    # For FreeBSD, we provide instructions for manual installation until packages are available
    print_warning "FreeBSD packages are currently built from source."
    print_status "Downloading BunkerWeb source..."

    BUNKERWEB_INSTALL_DIR="/usr/share/bunkerweb"

    # Create required directories
    mkdir -p "$BUNKERWEB_INSTALL_DIR"
    mkdir -p /etc/bunkerweb/configs /etc/bunkerweb/plugins
    mkdir -p /var/cache/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb
    mkdir -p /var/log/bunkerweb /var/lib/bunkerweb /var/www/html

    # Clone and setup BunkerWeb (or download release tarball)
    if [ -n "$BUNKERWEB_TARBALL_URL" ]; then
        run_cmd curl -fsSL "$BUNKERWEB_TARBALL_URL" -o /tmp/bunkerweb.tar.gz
        run_cmd tar -xzf /tmp/bunkerweb.tar.gz -C "$BUNKERWEB_INSTALL_DIR" --strip-components=1
        rm -f /tmp/bunkerweb.tar.gz
    else
        print_warning "Please download BunkerWeb from https://github.com/bunkerity/bunkerweb/releases"
        print_status "Then run the FreeBSD postinstall script: /usr/share/bunkerweb/scripts/postinstall-freebsd.sh"
    fi

    # Install Python dependencies
    if [ -d "$BUNKERWEB_INSTALL_DIR/deps" ]; then
        print_status "Python dependencies already bundled"
    else
        print_status "Installing Python dependencies..."
        mkdir -p "$BUNKERWEB_INSTALL_DIR/deps/python"
        python3.11 -m pip install --target "$BUNKERWEB_INSTALL_DIR/deps/python" \
            -r "$BUNKERWEB_INSTALL_DIR/requirements.txt" 2>/dev/null || true
    fi

    # Install rc.d scripts
    print_status "Installing rc.d service scripts..."
    if [ -d "$BUNKERWEB_INSTALL_DIR/rc.d" ]; then
        for script in bunkerweb bunkerweb_scheduler bunkerweb_ui bunkerweb_api; do
            if [ -f "$BUNKERWEB_INSTALL_DIR/rc.d/${script}" ]; then
                cp "$BUNKERWEB_INSTALL_DIR/rc.d/${script}" "/usr/local/etc/rc.d/${script}"
                chmod 555 "/usr/local/etc/rc.d/${script}"
            fi
        done
    fi

    # Set permissions
    chown -R root:nginx "$BUNKERWEB_INSTALL_DIR"
    chown -R nginx:nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb \
        /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb
    chmod 755 /var/log/bunkerweb
    chmod 770 /var/cache/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb
    chmod 2770 /var/tmp/bunkerweb

    # Install CLI
    if [ -f "$BUNKERWEB_INSTALL_DIR/helpers/bwcli" ]; then
        install -m 755 "$BUNKERWEB_INSTALL_DIR/helpers/bwcli" /usr/bin/bwcli
    fi

    # Write integration marker
    echo "FreeBSD" > "$BUNKERWEB_INSTALL_DIR/INTEGRATION"

    # Lock BunkerWeb package
    pkg lock -y bunkerweb 2>/dev/null || true

    print_status "BunkerWeb installed successfully on FreeBSD"
}

# Function to install CrowdSec
install_crowdsec() {
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}CrowdSec Security Engine Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing CrowdSec security engine"

    # Ensure required dependencies
    for dep in curl gnupg2 ca-certificates; do
        if ! command -v $dep >/dev/null 2>&1; then
            print_status "Installing missing dependency: $dep"
            case "$DISTRO_ID" in
                "debian"|"ubuntu")
                    run_cmd apt update
                    run_cmd apt install -y "$dep"
                    ;;
                "fedora"|"rhel"|"rocky"|"almalinux")
                    run_cmd dnf install -y $dep
                    ;;
                "freebsd")
                    run_cmd pkg install -y $dep
                    ;;
                *)
                    print_warning "Automatic install not supported on $DISTRO_ID"
                    ;;
            esac
        fi
    done

    echo -e "${YELLOW}--- Step 1: Add CrowdSec repository and install engine ---${NC}"
    print_step "Adding CrowdSec repository and installing engine"
    run_cmd curl -s https://install.crowdsec.net | sh
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt install -y crowdsec
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux")
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
    ACQ_FILE="/etc/crowdsec/acquis.yaml"
    ACQ_CONTENT="filenames:
  - /var/log/bunkerweb/access.log
  - /var/log/bunkerweb/error.log
  - /var/log/bunkerweb/modsec_audit.log
labels:
  type: bunkerweb
"
    if [ -f "$ACQ_FILE" ]; then
        cp "$ACQ_FILE" "${ACQ_FILE}.bak"
        echo "$ACQ_CONTENT" >> "$ACQ_FILE"
        print_status "Appended BunkerWeb acquisition config to: $ACQ_FILE"
    else
        echo "$ACQ_CONTENT" > "$ACQ_FILE"
        print_status "Created acquisition file: $ACQ_FILE"
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
    BOUNCER_KEY=$(cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --output raw)
    if [ -z "$BOUNCER_KEY" ]; then
        print_warning "Failed to retrieve API key; please register manually: cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6"
    else
        print_status "Bouncer Successfully registered"
    fi

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
        "fedora"|"rhel"|"rocky"|"almalinux")
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

# Locate the redis/valkey config file for the installed flavor.
# Echoes the path to stdout (empty if not found).
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

# Locate the systemd service unit name for the installed flavor.
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

# Idempotent rewrite of a single directive in a Redis-compatible config file.
# Replaces every line beginning with the directive (case-insensitive) and appends
# the new value if no match was found.
_redis_conf_set() {
    local conf="$1"
    local directive="$2"
    local value="$3"
    local tmp

    if [ ! -f "$conf" ]; then
        return 1
    fi

    tmp=$(mktemp) || return 1
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

# Function to install Redis (or Valkey)
install_redis() {
    local label conf service
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

    # Cross-platform service detection and enablement
    if [ "$DISTRO_ID" = "freebsd" ]; then
        if [ "$REDIS_FLAVOR" = "valkey" ]; then
            sysrc valkey_enable=YES >/dev/null 2>&1
            service valkey start || true
        else
            sysrc redis_enable=YES >/dev/null 2>&1
            service redis start || true
        fi
        print_status "${label^} service enabled and started"
    else
        service=$(_locate_redis_service || true)
        if [ -n "$service" ]; then
            run_cmd systemctl enable --now "$service"
            print_status "${label^} service enabled and started ($service)"
        else
            print_warning "${label^} service name not found; start it manually if needed."
        fi
    fi

    # Configure bind / requirepass / protected-mode based on the user's choices.
    conf=$(_locate_redis_conf || true)
    if [ -z "$conf" ]; then
        print_warning "Could not locate the ${label} config file; bind/password configuration skipped."
    else
        local bind_addr password_set=""
        bind_addr="${REDIS_BIND_INPUT:-127.0.0.1}"

        # Generate a password if the user opted in and binding ≠ loopback.
        if [ "$bind_addr" != "127.0.0.1" ] && [ -z "$REDIS_REQUIREPASS_LOCAL" ] && [ "$REDIS_AUTOPASS" = "yes" ]; then
            REDIS_REQUIREPASS_LOCAL=$(generate_secret 32)
        fi

        _redis_conf_set "$conf" "bind" "$bind_addr"

        if [ -n "$REDIS_REQUIREPASS_LOCAL" ]; then
            _redis_conf_set "$conf" "requirepass" "$REDIS_REQUIREPASS_LOCAL"
            _redis_conf_set "$conf" "protected-mode" "no"
            password_set="yes"
        fi

        # Apply memory cap + eviction policy. "0" means "keep distro defaults" — skip the writes.
        local memory_summary=""
        if [ -n "$REDIS_MAXMEMORY_MB" ] && [ "$REDIS_MAXMEMORY_MB" != "0" ]; then
            _redis_conf_set "$conf" "maxmemory" "${REDIS_MAXMEMORY_MB}mb"
            _redis_conf_set "$conf" "maxmemory-policy" "${REDIS_MAXMEMORY_POLICY:-volatile-lru}"
            memory_summary=" maxmemory=${REDIS_MAXMEMORY_MB}mb policy=${REDIS_MAXMEMORY_POLICY:-volatile-lru}"
        fi

        chmod 640 "$conf" 2>/dev/null || true
        print_status "Configured ${label} bind=${bind_addr}${password_set:+ (REQUIREPASS set)}${memory_summary} in ${conf}"

        # Restart the service to pick up new bind/password.
        if [ "$DISTRO_ID" = "freebsd" ]; then
            if [ "$REDIS_FLAVOR" = "valkey" ]; then
                service valkey restart || true
            else
                service redis restart || true
            fi
        else
            if [ -n "$service" ]; then
                run_cmd systemctl restart "$service"
            fi
        fi
    fi

    # Decide which host the BunkerWeb side will connect to.
    # If we bound to 0.0.0.0, BunkerWeb still talks to it via the manager's primary IPv4.
    if [ -z "$REDIS_HOST_INPUT" ]; then
        if [ "${REDIS_BIND_INPUT:-127.0.0.1}" = "0.0.0.0" ]; then
            local primary_ip
            primary_ip=$(get_primary_ipv4)
            REDIS_HOST_INPUT="${primary_ip:-127.0.0.1}"
        else
            REDIS_HOST_INPUT="${REDIS_BIND_INPUT:-127.0.0.1}"
        fi
    fi

    # Push the auto-generated password into the BunkerWeb client config so it can authenticate.
    if [ -n "$REDIS_REQUIREPASS_LOCAL" ] && [ -z "$REDIS_PASSWORD_INPUT" ]; then
        REDIS_PASSWORD_INPUT="$REDIS_REQUIREPASS_LOCAL"
    fi

    echo
    echo -e "${GREEN}${label^} installed and configured successfully${NC}"
    echo "Used by BunkerWeb to persist metrics and bans across restarts and to sync state between workers."
    echo "See BunkerWeb docs for more: https://docs.bunkerweb.io/latest/features/#redis"
    echo -e "${BLUE}========================================${NC}"
}

# Write DATABASE_URI once into the shared variables.env. The scheduler, UI
# and API service start scripts all source variables.env before their own env
# file, so a single write here is sufficient and avoids 3-way duplication.
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

# Install MariaDB locally and bootstrap a BunkerWeb-ready database + user.
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
        "fedora"|"rhel"|"rocky"|"almalinux")
            run_cmd dnf install -y mariadb-server
            ;;
        *)
            print_warning "MariaDB auto-install not supported on $DISTRO_ID. Skipping."
            return 1
            ;;
    esac

    # Drop in BunkerWeb-recommended tuning (max_allowed_packet=64M, bind to loopback).
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

    DB_DSN_GENERATED="mariadb+pymysql://${DB_USER_INPUT}:${DB_PASSWORD_INPUT}@127.0.0.1:3306/${DB_NAME_INPUT}"

    # Pick up our config snippet.
    run_cmd systemctl restart mariadb

    echo
    echo -e "${GREEN}MariaDB installed and bootstrapped${NC}"
    echo -e "${BLUE}========================================${NC}"
    return 0
}

# Install PostgreSQL locally and bootstrap a BunkerWeb-ready database + user.
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
        "rhel"|"rocky"|"almalinux")
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

    # Create or update role idempotently.
    local user_exists db_exists
    user_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER_INPUT}'" 2>/dev/null || true)
    if [ "$user_exists" != "1" ]; then
        sudo -u postgres psql -c "CREATE ROLE \"${DB_USER_INPUT}\" LOGIN PASSWORD '${DB_PASSWORD_INPUT}';"
    else
        sudo -u postgres psql -c "ALTER ROLE \"${DB_USER_INPUT}\" WITH LOGIN PASSWORD '${DB_PASSWORD_INPUT}';"
    fi

    db_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME_INPUT}'" 2>/dev/null || true)
    if [ "$db_exists" != "1" ]; then
        sudo -u postgres psql -c "CREATE DATABASE \"${DB_NAME_INPUT}\" OWNER \"${DB_USER_INPUT}\";"
    fi

    # Make sure pg_hba.conf allows password auth from loopback for our user.
    local pg_hba
    pg_hba=$(sudo -u postgres psql -tAc 'SHOW hba_file' 2>/dev/null || true)
    if [ -n "$pg_hba" ] && [ -f "$pg_hba" ]; then
        if ! grep -qE "^[^#]*${DB_USER_INPUT}[[:space:]]+127\\.0\\.0\\.1/32" "$pg_hba"; then
            printf '\nhost    %s    %s    127.0.0.1/32    md5\n' "$DB_NAME_INPUT" "$DB_USER_INPUT" >> "$pg_hba"
            run_cmd systemctl reload postgresql
        fi
    fi

    DB_DSN_GENERATED="postgresql+psycopg://${DB_USER_INPUT}:${DB_PASSWORD_INPUT}@127.0.0.1:5432/${DB_NAME_INPUT}"

    echo
    echo -e "${GREEN}PostgreSQL installed and bootstrapped${NC}"
    echo -e "${BLUE}========================================${NC}"
    return 0
}

# High-level entry point: runs the right installer based on DB_INSTALL and writes the DSN.
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
        *)
            : # nothing to do
            ;;
    esac
}

# Provision the first manager UI admin user via /etc/bunkerweb/ui.env.
# The bunkerweb-ui gunicorn pre-fork hook reads ADMIN_USERNAME/ADMIN_PASSWORD on first start
# and creates the admin via DB.create_ui_user. OVERRIDE_ADMIN_CREDS=yes makes it idempotent.
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

    print_status "Manager Web UI admin user provisioned (${UI_ADMIN_USERNAME_INPUT})"
}

# Generate a self-signed cert and enable gunicorn-native TLS for the manager UI listener.
setup_ui_selfsigned_tls() {
    local tls_dir=/var/lib/bunkerweb/ui-tls
    local cert="$tls_dir/cert.pem"
    local key="$tls_dir/key.pem"
    local ui_env=/etc/bunkerweb/ui.env
    local fqdn short cn primary_ip san

    # Resolve and sanitize the names that go into the cert.
    # CN must be DN-safe; DNS SANs must match RFC 1035 (alnum/dot/dash only).
    fqdn=$(hostname -f 2>/dev/null || true)
    short=$(hostname 2>/dev/null || true)
    fqdn=${fqdn//[^A-Za-z0-9.-]/}
    short=${short//[^A-Za-z0-9.-]/}
    cn="${fqdn:-${short:-bunkerweb-manager}}"

    primary_ip=$(get_primary_ipv4)

    # Build a SAN list covering every plausible address the operator might use.
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
            "fedora"|"rhel"|"rocky"|"almalinux") run_cmd dnf install -y openssl ;;
            "freebsd") run_cmd pkg install -y openssl ;;
        esac
    fi

    mkdir -p "$tls_dir"
    chmod 750 "$tls_dir"
    chown root:nginx "$tls_dir" 2>/dev/null || true

    print_step "Generating self-signed TLS certificate (CN=${cn}, SAN=${san})"
    run_cmd openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
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

# Apply manager UI hardening and start the UI service explicitly.
# Called for manager mode after configure_manager_api_defaults.
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
        # If hardening writes happened after a previous start, restart so they take effect.
        if [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
            run_cmd systemctl restart bunkerweb-ui
        fi
    fi
}

# Function to show final information
show_final_info() {
    echo
    echo "========================================="
    echo -e "${GREEN}BunkerWeb Installation Complete!${NC}"
    echo "========================================="
    echo
    echo "Services status:"

    # Cross-platform service status display
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
        # Show API service status if present on this system
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

    # Cross-platform API service detection
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

    # FreeBSD-specific instructions
    if [ "$DISTRO_ID" = "freebsd" ]; then
        echo "FreeBSD Notes:"
        echo "  - Services are managed via rc.d: service bunkerweb start|stop|restart"
        echo "  - Enable services in /etc/rc.conf: sysrc bunkerweb_enable=YES"
        echo "  - View logs: tail -f /var/log/bunkerweb/*.log"
        echo
    fi

    # Display next steps based on installation type and wizard status.
    # Honour explicit --server-ip / $SERVER_IP_INPUT, otherwise auto-detect
    # and prompt only when the host has multiple global IPv4 candidates.
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
                echo "  • Check logs: tail -f /var/log/bunkerweb/*.log"
            else
                echo "  • Check logs: journalctl -u bunkerweb -f"
            fi
            ;;
        "scheduler")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/scheduler.env"
            echo "     Set DATABASE_URI for shared configuration storage"
            echo "  2. Verify BUNKERWEB_INSTANCES is set to: $BUNKERWEB_INSTANCES_INPUT"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  3. Restart scheduler: service bunkerweb_scheduler restart"
            else
                echo "  3. Restart scheduler: systemctl restart bunkerweb-scheduler"
            fi
            echo "  4. Use 'bwcli' commands to manage the cluster"
            echo
            echo "📝 Scheduler-only mode information:"
            echo "  • Workers communicate via their API (port 5000 by default)"
            echo "  • Install the Web UI separately for graphical management"
            echo "  • All instances must share the same database backend"
            ;;
        "ui")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/ui.env"
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
            echo "  1. Configure API settings in /etc/bunkerweb/api.env"
            echo "     Set API_LISTEN_IP and API_HTTP_PORT as needed"
            echo "  2. Configure database connection: DATABASE_URI"
            if [ "$DISTRO_ID" = "freebsd" ]; then
                echo "  3. Restart the API: service bunkerweb_api restart"
            else
                echo "  3. Restart the API: systemctl restart bunkerweb-api"
            fi
            echo "  4. The API will be available at: http://${_server_ip}:8000"
            echo
            echo "📝 API-only mode information:"
            echo "  • The API service provides programmatic access to BunkerWeb"
            echo "  • Must connect to the same database as scheduler/UI"
            echo "  • Default API port: 8000 (FastAPI service, not internal API)"
            echo "  • Configure API_KEY for authentication if needed"
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
                    echo "  • Check logs: tail -f /var/log/bunkerweb/*.log"
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

    # Show RHEL database information if applicable (only when no DB was auto-installed)
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
        echo "💾 Database (auto-installed):"
        echo "  Engine:   ${_db_engine}"
        echo "  Host:     127.0.0.1:${_db_port}"
        echo "  Database: ${DB_NAME_INPUT}"
        echo "  User:     ${DB_USER_INPUT}"
        if [ -n "$DB_PASSWORD_GENERATED" ]; then
            echo "  Password: ${DB_PASSWORD_GENERATED}"
            echo "  ⚠️  This password is stored in /etc/bunkerweb/variables.env. Save it now if you need it elsewhere."
        else
            echo "  Password: (the value you provided)"
        fi
        echo "  DSN:      written to /etc/bunkerweb/variables.env"
        echo
    fi

    if [ -n "$UI_ADMIN_PASSWORD_GENERATED" ] || [ "$UI_ADMIN_CREATE" = "yes" ]; then
        echo "👤 Manager Web UI admin user:"
        echo "  Username: ${UI_ADMIN_USERNAME_INPUT:-admin}"
        if [ -n "$UI_ADMIN_PASSWORD_GENERATED" ]; then
            echo "  Password: ${UI_ADMIN_PASSWORD_GENERATED}"
            echo "  ⚠️  Save this password now."
        else
            echo "  Password: (the value you provided)"
        fi
        echo
    fi

    if [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
        echo "🔒 Web UI HTTPS (self-signed):"
        echo "  URL:  https://127.0.0.1:7000/   (accept the self-signed warning in your browser)"
        echo "  Cert: /var/lib/bunkerweb/ui-tls/cert.pem"
        echo "  Key:  /var/lib/bunkerweb/ui-tls/key.pem"
        echo
    fi

    if [ -n "$REDIS_REQUIREPASS_LOCAL" ]; then
        echo "🔑 ${REDIS_FLAVOR:-redis} REQUIREPASS (auto-generated):"
        echo "  Password: ${REDIS_REQUIREPASS_LOCAL}"
        echo "  Stored in the ${REDIS_FLAVOR:-redis} config and in /etc/bunkerweb/variables.env."
        echo "  ⚠️  Save it now and restrict port 6379 to your worker subnet."
        echo
    fi

    echo "📚 Resources:"
    echo "  • Documentation: https://docs.bunkerweb.io"
    echo "  • Community support: https://discord.bunkerity.com"
    echo "  • Commercial support: https://panel.bunkerweb.io/store/support"
    echo "========================================="
}

# Function to show usage
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
    echo "      --api, --enable-api  Enable the API service (disabled by default on Linux)"
    echo "      --no-api             Explicitly disable the API service"
    echo "  -f, --force              Force installation on unsupported OS versions"
    echo "  -q, --quiet              Silent installation (suppress output)"
    echo "  -h, --help               Show this help message"
    echo "      --dry-run            Show what would be installed without doing it"
    echo
    echo "Installation types:"
    echo "  --full                   Full stack installation (default)"
    echo "  --manager                Manager installation (Scheduler + UI)"
    echo "  --worker                 Worker installation (BunkerWeb only)"
    echo "  --scheduler-only         Scheduler only installation"
    echo "  --ui-only                Web UI only installation"
    echo "  --api-only               API service only installation"
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
    echo "  --database ENGINE        Auto-install local DB: mariadb, postgresql, or none"
    echo "  --db-name NAME           Database name (default: ${DB_NAME_INPUT})"
    echo "  --db-user USER           Database user (default: ${DB_USER_INPUT})"
    echo "  --db-password PASS       Database password (default: auto-generated)"
    echo
    echo "Manager UI hardening:"
    echo "  --ui-admin-user NAME     Create the first manager Web UI admin user with this name"
    echo "  --ui-admin-password PASS Password for --ui-admin-user (default: auto-generated)"
    echo "  --no-ui-admin            Skip the admin-user creation prompt"
    echo "  --ui-https-selfsigned    Generate a self-signed cert and enable UI HTTPS"
    echo "  --no-ui-https-selfsigned Disable manager UI self-signed HTTPS"
    echo
    echo "Advanced options:"
    echo "  --instances \"IP1 IP2\"    Space-separated list of BunkerWeb instances"
    echo "                           (optional for --manager and --scheduler-only)"
    echo "  --manager-ip IPs         Manager/Scheduler IPs to whitelist (required for --worker in non-interactive mode, overrides auto-detect for --manager)"
    echo "  --server-ip IP           IP printed in the post-install URLs (overrides auto-detection; can also be set via SERVER_IP_INPUT env var)"
    echo "  --dns-resolvers \"IP1 IP2\"  Custom DNS resolver IPs (for --full, --manager, --worker)"
    echo "  --api-https              Enable HTTPS for internal API communication (default: HTTP only)"
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
    echo "  --redis-maxmemory-policy POLICY  Eviction policy (default volatile-lru). Other valid: allkeys-lru, volatile-ttl, noeviction, …"
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
            ENABLE_WIZARD="yes"  # Default to wizard in non-interactive mode
            shift
            ;;
        -f|--force)
            FORCE_INSTALL="yes"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --full)
            INSTALL_TYPE="full"
            shift
            ;;
        --manager)
            INSTALL_TYPE="manager"
            shift
            ;;
        --worker)
            INSTALL_TYPE="worker"
            shift
            ;;
        --scheduler-only)
            INSTALL_TYPE="scheduler"
            shift
            ;;
        --ui-only)
            INSTALL_TYPE="ui"
            shift
            ;;
        --api-only)
            INSTALL_TYPE="api"
            shift
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
            REDIS_HOST_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-port)
            REDIS_PORT_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-database)
            REDIS_DATABASE_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-username)
            REDIS_USERNAME_INPUT="$2"
            REDIS_INSTALL="no"
            shift 2
            ;;
        --redis-password)
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
                none|skip|sqlite|SQLite) DB_INSTALL="none" ;;
                *) print_error "--database must be one of: mariadb, postgresql, none"; exit 1 ;;
            esac
            shift 2
            ;;
        --db-name)
            DB_NAME_INPUT="$2"
            shift 2
            ;;
        --db-user)
            DB_USER_INPUT="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD_INPUT="$2"
            shift 2
            ;;
        --ui-admin-user)
            UI_ADMIN_USERNAME_INPUT="$2"
            UI_ADMIN_CREATE="yes"
            shift 2
            ;;
        --ui-admin-password)
            UI_ADMIN_PASSWORD_INPUT="$2"
            UI_ADMIN_CREATE="yes"
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
            BUNKERWEB_INSTANCES_INPUT="$2"
            shift 2
            ;;
        --manager-ip)
            MANAGER_IP_INPUT="$2"
            shift 2
            ;;
        --server-ip)
            SERVER_IP_INPUT="$2"
            shift 2
            ;;
        --dns-resolvers)
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
            exec >/dev/null 2>&1
            shift
            ;;
        --dry-run)
            echo "Dry run mode - would install BunkerWeb $BUNKERWEB_VERSION"
            detect_os
            check_supported_os
            echo "Installation type: ${INSTALL_TYPE:-full}"
            echo "Setup wizard: ${ENABLE_WIZARD:-auto}"
            echo "CrowdSec: ${CROWDSEC_INSTALL:-no}"
            if [ "$REDIS_INSTALL" = "yes" ]; then
                echo "Redis: yes (local install, flavor=${REDIS_FLAVOR:-redis})"
                if [ -n "$REDIS_BIND_INPUT" ]; then
                    echo "Redis bind: $REDIS_BIND_INPUT"
                fi
                echo "Redis auto-password: ${REDIS_AUTOPASS}"
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
            fi
            if [ -n "$UI_ADMIN_CREATE" ]; then
                echo "UI admin user: ${UI_ADMIN_CREATE}${UI_ADMIN_USERNAME_INPUT:+ ($UI_ADMIN_USERNAME_INPUT)}"
            fi
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
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

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

# Manager UI hardening — only meaningful for manager mode
if { [ -n "$UI_ADMIN_CREATE" ] || [ -n "$UI_ADMIN_USERNAME_INPUT" ] || [ -n "$UI_ADMIN_PASSWORD_INPUT" ] || [ -n "$UI_SELFSIGNED_INPUT" ]; } \
    && [ "$INSTALL_TYPE" != "manager" ] && [ -n "$INSTALL_TYPE" ]; then
    print_error "Manager UI hardening options (--ui-admin-*, --ui-https-selfsigned) only apply to --manager installations"
    exit 1
fi

# Detect existing installation and handle reinstall/upgrade
check_existing_installation() {
    if [ -f /usr/share/bunkerweb/VERSION ]; then
        INSTALLED_VERSION=$(cat /usr/share/bunkerweb/VERSION 2>/dev/null || echo "unknown")
        print_status "Detected existing BunkerWeb installation (version ${INSTALLED_VERSION})"
        if [ "$INSTALLED_VERSION" = "$BUNKERWEB_VERSION" ]; then
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                echo
                read -p "BunkerWeb ${INSTALLED_VERSION} already installed. Show status and exit? (Y/n): " -r
                case $REPLY in
                    [Nn]*) print_status "Nothing to do."; exit 0 ;;
                    *) show_final_info; exit 0 ;;
                esac
            else
                print_status "BunkerWeb ${INSTALLED_VERSION} already installed. Nothing to do."; exit 0
            fi
        else
            print_warning "Requested version ${BUNKERWEB_VERSION} differs from installed version ${INSTALLED_VERSION}. Upgrade will be attempted."
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                read -p "Proceed with upgrade? (Y/n): " -r
                case $REPLY in
                    [Nn]*) print_status "Upgrade cancelled."; exit 0 ;;
                esac
            fi
            UPGRADE_SCENARIO="yes"
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
    # Check if scheduler service is running using cross-platform helper
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
        print_warning "Scheduler service not active; starting temporarily for backup."
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
    if should_skip_upgrade_backup; then
        print_status "Skipping pre-upgrade backup (scheduler not enabled; worker/ui/api install)."
    else
        # Interactive confirmation about backup (optional, enabled by default)
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            if [ "$AUTO_BACKUP" = "yes" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}💾 Pre-upgrade Backup${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "A pre-upgrade backup is recommended to preserve configuration and database."
                echo "You can change the destination directory or accept the default."
                DEFAULT_BACKUP_DIR="/var/tmp/bunkerweb-backup-$(date +%Y%m%d-%H%M%S)"
                echo
                echo -e "${YELLOW}Create automatic backup before upgrade? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Nn]*) AUTO_BACKUP="no" ;;
                    *)
                        echo -e "${YELLOW}Backup directory [${DEFAULT_BACKUP_DIR}]:${NC} "
                        read -p "" -r BACKUP_DIRECTORY_INPUT
                        if [ -n "$BACKUP_DIRECTORY_INPUT" ]; then
                            BACKUP_DIRECTORY="$BACKUP_DIRECTORY_INPUT"
                        else
                            BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-$DEFAULT_BACKUP_DIR}"
                        fi
                        ;;
                esac
            else
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}⚠️  Backup Confirmation${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "Automatic backup is disabled. Make sure you already performed a manual backup as described in the documentation."
                echo
                echo -e "${YELLOW}Confirm manual backup was performed? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*) ;; * ) print_error "Upgrade aborted until backup is confirmed."; exit 1 ;;
                esac
            fi
        fi
    fi

    print_status "Upgrade mode: $INSTALLED_VERSION -> $BUNKERWEB_VERSION"
    perform_upgrade_backup
    # Remove holds/version locks
    case "$DISTRO_ID" in
        debian|ubuntu)
            if command -v apt-mark >/dev/null 2>&1; then
                print_status "Removing holds (bunkerweb, nginx)"
                apt-mark unhold bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
        fedora|rhel|rocky|almalinux)
            if command -v dnf >/dev/null 2>&1; then
                print_status "Removing versionlock (bunkerweb, nginx)"
                dnf versionlock delete bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
    esac
    # Stop services (best effort)
    print_step "Stopping services prior to upgrade"
    for svc in bunkerweb-ui bunkerweb-scheduler bunkerweb; do
        if systemctl list-units --type=service --all | grep -q "^${svc}.service"; then
            if systemctl is-active --quiet "$svc"; then
                run_cmd systemctl stop "$svc"
            fi
        fi
    done
    # Install new version only (do NOT reinstall nginx)
    print_step "Upgrading BunkerWeb package"
    case "$DISTRO_ID" in
        debian|ubuntu)
            run_cmd apt update
            run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"
            run_cmd apt-mark hold bunkerweb nginx
            ;;
        fedora|rhel|rocky|almalinux)
            if [ "$DISTRO_ID" = "fedora" ]; then
                run_cmd dnf makecache || true
            else
                dnf check-update || true
            fi
            run_cmd dnf install -y --allowerasing "bunkerweb-$BUNKERWEB_VERSION"
            run_cmd dnf versionlock add bunkerweb nginx
            ;;
    esac
    show_final_info
    exit 0
}

# Main installation function
main() {
    echo "========================================="
    echo "       BunkerWeb Easy Install Script"
    echo "========================================="
    echo

    # Preliminary checks
    check_root
    detect_os
    detect_architecture
    check_supported_os
    # New: check if already installed (after OS detection)
    check_existing_installation

    # If upgrade scenario, skip prompts & ancillary installs
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        upgrade_only
    fi

    # Show RHEL database warning early
    show_rhel_database_warning

    # Ask user preferences in interactive mode
    ask_user_preferences

    # Check for port conflicts after knowing the install type
    check_ports

    # Set environment variables based on installation type
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

    # Pass UI_WIZARD to postinstall script
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    print_status "Installing BunkerWeb $BUNKERWEB_VERSION"
    echo

    # Confirmation prompt in interactive mode
    if [ "$INTERACTIVE_MODE" = "yes" ] && [ "$FORCE_INSTALL" != "yes" ]; then
        read -p "Continue with installation? (Y/n): " -r
        case $REPLY in
            [Nn]*)
                print_status "Installation cancelled"
                exit 0
                ;;
        esac
    fi

    # If upgrading, remove holds/versionlocks so upgrade can proceed
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        case "$DISTRO_ID" in
            debian|ubuntu)
                if command -v apt-mark >/dev/null 2>&1; then
                    print_status "Removing holds on bunkerweb & nginx (upgrade scenario)"
                    apt-mark unhold bunkerweb nginx >/dev/null 2>&1 || true
                fi
                ;;
            fedora|rhel|rocky|almalinux)
                if command -v dnf >/dev/null 2>&1; then
                    print_status "Removing versionlock on bunkerweb & nginx (upgrade scenario)"
                    dnf versionlock delete bunkerweb nginx >/dev/null 2>&1 || true
                fi
                ;;
        esac
        # Stop services before upgrading (per upgrading.md procedure)
        print_step "Stopping BunkerWeb services before upgrade"
        for svc in bunkerweb bunkerweb-ui bunkerweb-scheduler; do
            if systemctl list-units --type=service --all | grep -q "^${svc}.service"; then
                if systemctl is-active --quiet "$svc"; then
                    run_cmd systemctl stop "$svc"
                else
                    print_status "Service $svc not active, skipping stop"
                fi
            fi
        done
    fi

    # Install NGINX based on distribution
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            install_nginx_debian
            ;;
        "fedora")
            install_nginx_fedora
            ;;
        "rhel"|"rocky"|"almalinux")
            install_nginx_rhel
            ;;
        "freebsd")
            install_nginx_freebsd
            ;;
    esac

    # Install CrowdSec if chosen
    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        install_crowdsec
    fi

    # Install Redis if chosen (configuration applied later)
    if [ "$REDIS_INSTALL" = "yes" ]; then
        install_redis
    fi

    # Auto-install a local DB before BunkerWeb so DATABASE_URI lands in variables.env
    # in time for the postinstall (and our own configure_*_config) to start the scheduler.
    if [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; then
        install_database
    fi

    # Install BunkerWeb based on distribution
    # Set environment variables to prevent postinstall from starting services we'll configure
    if [ "$INSTALL_TYPE" = "manager" ]; then
        export SERVICE_SCHEDULER=no
        # Defer UI start when we still need to provision admin creds or self-signed TLS.
        if [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
            export SERVICE_UI=no
            MANAGER_UI_DEFERRED="yes"
        fi
    elif [ "$INSTALL_TYPE" = "worker" ]; then
        export SERVICE_BUNKERWEB=no
    elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
        # Propagate the user's API-service choice to the deb/rpm postinstall.
        # (Without this export the postinstall reads ${SERVICE_API:-no} and
        # leaves bunkerweb-api disabled even when the user passed --api.)
        export SERVICE_API="${SERVICE_API:-no}"
        # Only prevent start if we have configuration to apply
        if [ -n "$DNS_RESOLVERS_INPUT" ] || [ -n "$API_LISTEN_HTTPS_INPUT" ] || [ -n "$REDIS_HOST_INPUT" ] || [ "$REDIS_INSTALL" = "yes" ] || [ -n "$REDIS_PORT_INPUT" ] || [ -n "$REDIS_DATABASE_INPUT" ] || [ -n "$REDIS_USERNAME_INPUT" ] || [ -n "$REDIS_PASSWORD_INPUT" ] || [ -n "$REDIS_SSL_INPUT" ] || [ -n "$REDIS_SSL_VERIFY_INPUT" ] || [ "$CROWDSEC_INSTALL" = "yes" ] || [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ] || [ "$DB_INSTALL" = "mariadb" ] || [ "$DB_INSTALL" = "postgresql" ]; then
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            # Defer the API start too so it boots after we've finished writing
            # /etc/bunkerweb/variables.env (DSN, Redis settings, etc.).
            if [ "$SERVICE_API" = "yes" ]; then
                FULL_API_DEFERRED="yes"
                export SERVICE_API=no
            fi
        fi
    fi

    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            install_bunkerweb_debian
            ;;
        "fedora")
            install_bunkerweb_rpm
            ;;
        "rhel"|"rocky"|"almalinux")
            install_bunkerweb_rpm
            ;;
        "freebsd")
            install_bunkerweb_freebsd
            ;;
    esac

    if [ "$INSTALL_TYPE" = "manager" ]; then
        configure_manager_api_defaults
        # Apply UI hardening + start the UI explicitly when deferred.
        if [ "$MANAGER_UI_DEFERRED" = "yes" ]; then
            unset SERVICE_UI
            start_manager_ui
        elif [ "$UI_ADMIN_CREATE" = "yes" ] || [ "$UI_SELFSIGNED_INPUT" = "yes" ]; then
            # Hardening was opted in via flags after the UI already started — apply + restart.
            start_manager_ui
        fi
    elif [ "$INSTALL_TYPE" = "worker" ]; then
        configure_worker_api_whitelist
    elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
        configure_full_config
    fi

    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        run_cmd systemctl restart crowdsec
        sleep 2
        systemctl status crowdsec --no-pager -l || print_warning "CrowdSec may not be running"
    fi

    # Show final information
    show_final_info
}

# Run main function
main "$@"
