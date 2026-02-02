#!/bin/bash

# Source the utils helper script
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# Get the highest Python version available and export it
PYTHON_BIN=$(get_python_bin)
export PYTHON_BIN

export PYTHONPATH=/usr/share/bunkerweb/deps/python:/usr/share/bunkerweb/api

API_PID_FILE=/var/run/bunkerweb/api.pid

function get_env_var() {
    local var_name=$1
    local default_value=$2
    local value

    # First try api.env
    value=$(grep "^${var_name}=" /etc/bunkerweb/api.env 2>/dev/null | cut -d '=' -f 2)

    # If not found, try variables.env
    if [ -z "$value" ] && [ -f /etc/bunkerweb/variables.env ]; then
        value=$(grep "^${var_name}=" /etc/bunkerweb/variables.env 2>/dev/null | cut -d '=' -f 2)
    fi

    # Return default if still not found
    if [ -z "$value" ]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

start() {
    stop

    echo "Starting API"

    # Create api.env with defaults if missing
    if [ ! -f /etc/bunkerweb/api.env ]; then
        {
            echo "# =============================="
            echo "# BunkerWeb API Configuration"
            echo "# This file lists all supported API environment variables with their defaults."
            echo "# Uncomment and adjust as needed. Lines starting with # are ignored."
            echo "# =============================="
            echo
            echo "# --- Network & Proxy ---"
            echo "# Listen address/port for the API"
            echo "LISTEN_ADDR=127.0.0.1"
            echo "LISTEN_PORT=8888"
            echo "# Trusted proxy IPs for X-Forwarded-* headers (comma-separated)."
            echo "# Default is restricted to loopback for security."
            echo "FORWARDED_ALLOW_IPS=127.0.0.1,::1"
            echo "# Trusted proxy IPs for PROXY protocol (comma-separated)."
            echo "# Defaults to FORWARDED_ALLOW_IPS when unset."
            echo "PROXY_ALLOW_IPS=127.0.0.1,::1"
            echo
            echo "# --- Logging & Runtime ---"
            echo "# LOG_LEVEL affects most components; CUSTOM_LOG_LEVEL overrides when provided."
            echo "# LOG_LEVEL=info"
            echo "LOG_TYPES=file"
            echo "# LOG_FILE_PATH=/var/log/bunkerweb/api.log"
            echo "# Number of workers/threads (auto if unset)."
            echo "# MAX_WORKERS=<auto>"
            echo "# MAX_THREADS=<auto>"
            echo
            echo "# --- Authentication & Authorization ---"
            echo "# Optional admin Bearer token (grants full access when provided)."
            echo "API_TOKEN=changeme"
            echo "# Bootstrap admin user (created/validated on startup if provided)."
            echo "# API_USERNAME="
            echo "# API_PASSWORD="
            echo "# Force re-applying bootstrap admin credentials on startup (use with care)."
            echo "# OVERRIDE_API_CREDS=no"
            echo "# Fine-grained ACLs can be enabled/disabled here."
            echo "# API_ACL_BOOTSTRAP_FILE="
            echo
            echo "# --- IP allowlist ---"
            echo "# Enable and shape inbound IP allowlist for the API."
            echo "# API_WHITELIST_ENABLED=yes"
            echo "WHITELIST_IPS=127.0.0.1"
            echo
            echo "# --- FastAPI surface ---"
            echo "# Customize or disable documentation endpoints. Use 'disabled' to turn off."
            echo "# API_TITLE=BunkerWeb API"
            echo "# API_DOCS_URL=/docs"
            echo "# API_REDOC_URL=/redoc"
            echo "# API_OPENAPI_URL=/openapi.json"
            echo "# Mount the API under a subpath (useful behind reverse proxies)."
            echo "# API_ROOT_PATH="
            echo
            echo "# --- TLS/SSL ---"
            echo "# Enable TLS for the API listener (requires cert and key)."
            echo "# API_SSL_ENABLED=no"
            echo "# Path to PEM-encoded certificate and private key."
            echo "# API_SSL_CERTFILE=/etc/ssl/certs/bunkerweb-api.crt"
            echo "# API_SSL_KEYFILE=/etc/ssl/private/bunkerweb-api.key"
            echo "# Optional chain/CA bundle and cipher suite."
            echo "# API_SSL_CA_CERTS="
            echo "# API_SSL_CIPHERS_CUSTOM="
            echo "# API_SSL_CIPHERS_LEVEL=modern   # choices: modern|intermediate"
            echo
            echo "# --- Biscuit keys & policy ---"
            echo "# Bind token to client IP (except private ranges)."
            echo "# CHECK_PRIVATE_IP=yes"
            echo "# Biscuit token lifetime in seconds (0 disables expiry)."
            echo "# API_BISCUIT_TTL_SECONDS=3600"
            echo "# Provide Biscuit keys via env (hex) instead of files."
            echo "# BISCUIT_PUBLIC_KEY="
            echo "# BISCUIT_PRIVATE_KEY="
            echo
            echo "# --- Rate limiting ---"
            echo "# Enable/disable and shape rate limiting."
            echo "# API_RATE_LIMIT_ENABLED=yes"
            echo "# API_RATE_LIMIT_HEADERS_ENABLED=yes"
            echo "# Global default limit (times per seconds)."
            echo "# API_RATE_LIMIT_TIMES=100"
            echo "# API_RATE_LIMIT_SECONDS=60"
            echo "# Authentication endpoint limit."
            echo "# API_RATE_LIMIT_AUTH_TIMES=10"
            echo "# API_RATE_LIMIT_AUTH_SECONDS=60"
            echo "# Advanced limits and rules (CSV/JSON/YAML)."
            echo "# API_RATE_LIMIT_DEFAULTS=\"200/minute\""
            echo "# API_RATE_LIMIT_APPLICATION_LIMITS="
            echo "# API_RATE_LIMIT_RULES="
            echo "# Strategy: fixed-window | moving-window | sliding-window-counter"
            echo "# API_RATE_LIMIT_STRATEGY=fixed-window"
            echo "# Key selector: ip | user | path | method | header:<Name>"
            echo "# API_RATE_LIMIT_KEY=ip"
            echo "# Exempt IPs (space or comma-separated CIDRs)."
            echo "# API_RATE_LIMIT_EXEMPT_IPS="
            echo "# Storage options in JSON (merged with Redis settings if USE_REDIS=yes)."
            echo "# API_RATE_LIMIT_STORAGE_OPTIONS="
            echo
            echo "# --- Redis (optional, for rate limiting storage) ---"
            echo "# USE_REDIS=no"
            echo "# REDIS_HOST="
            echo "# REDIS_PORT=6379"
            echo "# REDIS_DATABASE=0"
            echo "# REDIS_USERNAME="
            echo "# REDIS_PASSWORD="
            echo "# REDIS_SSL=no"
            echo "# REDIS_SSL_VERIFY=yes"
            echo "# REDIS_TIMEOUT=1000"
            echo "# REDIS_KEEPALIVE_POOL=10"
            echo "# REDIS_SENTINEL_HOSTS=sentinel1:26379 sentinel2:26379"
            echo "# REDIS_SENTINEL_MASTER=mymaster"
            echo "# REDIS_SENTINEL_USERNAME="
            echo "# REDIS_SENTINEL_PASSWORD="
        } > /etc/bunkerweb/api.env
        chown root:nginx /etc/bunkerweb/api.env
        chmod 660 /etc/bunkerweb/api.env
    fi

    if [ ! -f /etc/bunkerweb/api.yml ]; then
        touch /etc/bunkerweb/api.yml
        chown root:nginx /etc/bunkerweb/api.yml
        chmod 660 /etc/bunkerweb/api.yml
    fi

    # Create PID folder
    if [ ! -f /var/run/bunkerweb ] ; then
        mkdir -p /var/run/bunkerweb
        chown nginx:nginx /var/run/bunkerweb
    fi

    # Create TMP folder
    if [ ! -f /var/tmp/bunkerweb ] ; then
        mkdir -p /var/tmp/bunkerweb
        chown nginx:nginx /var/tmp/bunkerweb
        chmod 2770 /var/tmp/bunkerweb
    fi

    # Create LOG folder
    if [ ! -f /var/log/bunkerweb ] ; then
        mkdir -p /var/log/bunkerweb
        chown nginx:nginx /var/log/bunkerweb
    fi

    # Extract environment variables with fallback
    LISTEN_ADDR=$(get_env_var "API_LISTEN_ADDR" "")
    if [ -z "$LISTEN_ADDR" ]; then
        LISTEN_ADDR=$(get_env_var "LISTEN_ADDR" "127.0.0.1")
    fi
    export LISTEN_ADDR

    LISTEN_PORT=$(get_env_var "API_LISTEN_PORT" "")
    if [ -z "$LISTEN_PORT" ]; then
        LISTEN_PORT=$(get_env_var "LISTEN_PORT" "8888")
    fi
    export LISTEN_PORT

    FORWARDED_ALLOW_IPS=$(get_env_var "API_FORWARDED_ALLOW_IPS" "")
    if [ -z "$FORWARDED_ALLOW_IPS" ]; then
        FORWARDED_ALLOW_IPS=$(get_env_var "FORWARDED_ALLOW_IPS" "127.0.0.1,::1")
    fi
    export FORWARDED_ALLOW_IPS

    PROXY_ALLOW_IPS=$(get_env_var "API_PROXY_ALLOW_IPS" "")
    if [ -z "$PROXY_ALLOW_IPS" ]; then
        PROXY_ALLOW_IPS=$(get_env_var "PROXY_ALLOW_IPS" "$FORWARDED_ALLOW_IPS")
    fi
    export PROXY_ALLOW_IPS

    API_WHITELIST_IPS=$(get_env_var "API_WHITELIST_IPS" "")
    if [ -z "$API_WHITELIST_IPS" ]; then
        API_WHITELIST_IPS=$(get_env_var "WHITELIST_IPS" "127.0.0.1")
    fi
    export API_WHITELIST_IPS

    LOG_TYPES=$(get_env_var "API_LOG_TYPES" "")
    if [ -z "$LOG_TYPES" ]; then
        LOG_TYPES=$(get_env_var "LOG_TYPES" "file")
    fi
    export LOG_TYPES

    LOG_FILE_PATH=$(get_env_var "API_LOG_FILE_PATH" "")
    if [ -z "$LOG_FILE_PATH" ]; then
        LOG_FILE_PATH=$(get_env_var "LOG_FILE_PATH" "/var/log/bunkerweb/api.log")
    fi
    export LOG_FILE_PATH

    LOG_SYSLOG_TAG=$(get_env_var "API_LOG_SYSLOG_TAG" "")
    if [ -z "$LOG_SYSLOG_TAG" ]; then
        LOG_SYSLOG_TAG=$(get_env_var "LOG_SYSLOG_TAG" "bw-api")
    fi
    export LOG_SYSLOG_TAG

    export CAPTURE_OUTPUT="yes"

    export_env_file /etc/bunkerweb/variables.env
    export_env_file /etc/bunkerweb/api.env

    if ! run_as_nginx env PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m gunicorn \
        --chdir /usr/share/bunkerweb/api \
        --logger-class utils.logger.APILogger \
        --config /usr/share/bunkerweb/api/utils/gunicorn.conf.py; then
        echo "Failed to start API service (nginx user execution error)"
        exit 1
    fi
}

stop() {
    echo "Stopping API service..."
    if [ -f "$API_PID_FILE" ]; then
        pid=$(cat "$API_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -s TERM "$pid"
        fi
        # Wait up to 10s for graceful stop
        for _ in $(seq 1 10); do
            if kill -0 "$pid" 2>/dev/null; then
                sleep 1
            else
                break
            fi
        done
        rm -f "$API_PID_FILE"
    else
        echo "API service is not running or the pid file doesn't exist."
    fi
}

reload() {
    echo "Reloading API service..."
    stop
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    reload)
        reload
        ;;
    *)
        echo "Usage: $0 {start|stop|reload}"
        exit 1
        ;;
esac
