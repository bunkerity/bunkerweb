#!/bin/bash

# Shared Database Configuration and TLS Certificate Validation Helper
# Sourced by both systemd (bunkerweb-scheduler.sh) and container (entrypoint.sh) deployments
#
# Functions:
#   parse_database_uri()          - Extract connection info from DATABASE_URI
#   validate_db_tls()             - Validate DB TLS connection with system CA fallback
#   validate_db_tls_certificate() - Test TLS connection via openssl s_client
#
# shellcheck disable=SC1091
source /usr/share/bunkerweb/helpers/utils.sh

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# parse_database_uri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Parse DATABASE_URI and extract connection information.
# Outputs key=value pairs suitable for eval or sourcing.
#
# Output format:
#   type=<db_type>
#   database=<db_name>
#   host=<hostname>
#   port=<port_number>
#   user=<username>
#   ssl_enabled=<yes|no>
#   pem_path=<path|none>
#
# Usage:
#   eval "$(parse_database_uri)"  # Imports: type, database, host, port, user, ssl_enabled, pem_path
#
# Returns: 0 always (fails gracefully with safe defaults)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

parse_database_uri() {
    timeout 2s python3 << 'PY'
from os import getenv
from urllib.parse import urlparse, parse_qs, unquote

uri = getenv("DATABASE_URI", "")
db_type = host = user = db_name = port = ""
ssl_enabled = "no"
pem_path = ""

try:
    p = urlparse(uri)
    db_type = (p.scheme or "").split("+", 1)[0]
    host = p.hostname or ""
    port = str(p.port) if p.port else ""
    user = p.username or ""
    if db_type == "sqlite":
        db_name = p.path or ""
    else:
        db_name = (p.path or "").lstrip("/")

    if db_type != "sqlite":
        q = parse_qs(p.query or "", keep_blank_values=True)

        def _q(name: str) -> str:
            vals = q.get(name) or []
            return vals[0] if vals else ""

        ssl_flag = (_q("ssl") or "").strip().lower()
        sslmode = (_q("sslmode") or "").strip().lower()
        pem_path = unquote((_q("ssl_ca") or _q("sslrootcert") or "").strip())

        if pem_path:
            ssl_enabled = "yes"
        elif ssl_flag in ("1", "true", "yes", "on"):
            ssl_enabled = "yes"
        elif sslmode and sslmode not in ("disable", "off", "no", "false", "0"):
            ssl_enabled = "yes"
except Exception:
    pass

print(f'type="{db_type or "(unknown)"}"')
print(f'database="{db_name or "(none)"}"')
print(f'host="{host or "(local)"}"')
print(f'port="{port or "(default)"}"')
print(f'user="{user or "(none)"}"')
print(f'ssl_enabled="{ssl_enabled}"')
print(f'pem_path="{pem_path or "(none)"}"')
PY
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# validate_db_tls
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Comprehensive DB TLS validation with system CA fallback.
# Handles: explicit PEM files, system CA discovery, and graceful fallback.
#
# Arguments:
#   $1: LOG_CONTEXT      - Logging prefix (e.g., "ENTRYPOINT", "SYSTEMCTL")
#   $2: ssl_enabled      - "yes" if SSL is enabled, "no" otherwise
#   $3: pem_path         - Path to PEM file or "(none)"
#   $4: host             - Database server hostname
#   $5: port             - Database server port (or "(default)" to use protocol default)
#   $6: db_type          - Database type (postgres, mysql, etc)
#   $7: run_as_user      - (Optional) "yes" for nginx user execution, "no" or omit for direct
#
# Returns:
#   0 = validation passed or skipped (no SSL)
#   1 = validation failed (continues gracefully)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

validate_db_tls() {
    local LOG_CONTEXT="${1:-UNKNOWN}"
    local ssl_enabled="${2:-no}"
    local pem_path="${3:-(none)}"
    local host="${4:-(none)}"
    local port="${5:-(default)}"
    local db_type="${6:-(none)}"
    local run_as_user="${7:-no}"

    # Log SSL status
    log "$LOG_CONTEXT" "ℹ️" "DB SSL enabled: ${ssl_enabled}"

    # Skip validation if neither SSL nor PEM
    if [ "$ssl_enabled" != "yes" ] && ([ -z "$pem_path" ] || [ "$pem_path" = "(none)" ]); then
        log "$LOG_CONTEXT" "ℹ️" "DB TLS certificate provided: no"
        return 0
    fi

    # If no PEM provided but SSL enabled, try system CA certs
    local is_system_ca="no"
    if [ "$ssl_enabled" = "yes" ] && ([ -z "$pem_path" ] || [ "$pem_path" = "(none)" ]); then
        # Find system CA bundle
        for ca_file in /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-bundle.crt /etc/ssl/certs/ca.crt; do
            if [ -f "$ca_file" ]; then
                pem_path="$ca_file"
                is_system_ca="yes"
                log "$LOG_CONTEXT" "ℹ️" "No PEM provided, using system CA bundle: $pem_path"
                break
            fi
        done
        # If no system CA found, proceed with validation (will use system defaults)
        if [ -z "$pem_path" ] || [ "$pem_path" = "(none)" ]; then
            log "$LOG_CONTEXT" "ℹ️" "No system CA bundle found, proceeding with SSL (system default verification)"
        fi
    else
        [ -n "$pem_path" ] && [ "$pem_path" != "(none)" ] && log "$LOG_CONTEXT" "ℹ️" "DB TLS certificate provided: $pem_path"
    fi

    # Validate TLS connection
    validate_db_tls_certificate "$LOG_CONTEXT" "$host" "$port" "$db_type" "$pem_path" "$run_as_user" "$is_system_ca"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# validate_db_tls_certificate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test TLS connection to database server using openssl s_client.
#
# Arguments:
#   $1: LOG_CONTEXT  - Logging prefix (e.g., "SYSTEMCTL", "ENTRYPOINT")
#   $2: host         - Database server hostname
#   $3: port         - Database server port (or "(default)" to use protocol default)
#   $4: db_type      - Database type (postgres, mysql, etc)
#   $5: pem_path     - Path to CA certificate file or "(none)"
#   $6: run_as_user  - (Optional) "yes" for nginx user, "no" for direct execution
#   $7: is_system_ca - (Optional) "yes" if using system CA bundle, "no" for user cert
#
# Returns:
#   0 = TLS connection successful or skipped
#   1 = TLS connection failed (continues gracefully)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

validate_db_tls_certificate() {
    local LOG_CONTEXT="${1:-UNKNOWN}"
    local host="${2:-(none)}"
    local port="${3:-(default)}"
    local db_type="${4:-(none)}"
    local pem_path="${5:-(none)}"
    local run_as_user="${6:-no}"
    local is_system_ca="${7:-no}"

    # Skip if no host or db_type
    if [ "$host" = "(none)" ] || [ -z "$host" ] || [ "$db_type" = "(none)" ] || [ -z "$db_type" ]; then
        return 0
    fi

    # Skip if no PEM and no certificate to validate
    if [ "$pem_path" = "(none)" ] || [ -z "$pem_path" ]; then
        log "$LOG_CONTEXT" "ℹ️" "No explicit certificate to validate, TLS verification delegated to system"
        return 0
    fi

    # ── PEM File Validation ───────────────────────────────────────────────────
    # Validate the PEM file before testing connections
    log "$LOG_CONTEXT" "ℹ️" "Validating PEM certificate: $pem_path"

    # File existence check
    if [ ! -f "$pem_path" ]; then
        log "$LOG_CONTEXT" "❌" "PEM certificate does not exist: $pem_path"
        return 1
    fi

    # File readability check
    if [ ! -r "$pem_path" ]; then
        log "$LOG_CONTEXT" "❌" "PEM certificate is NOT readable: $pem_path"
        return 1
    fi

    # PEM/DER format validation
    if ! timeout 2s openssl x509 -in "$pem_path" -noout >/dev/null 2>&1; then
        # Try DER format
        if ! timeout 2s openssl x509 -inform DER -in "$pem_path" -noout >/dev/null 2>&1; then
            log "$LOG_CONTEXT" "❌" "PEM certificate is not valid X.509 format: $pem_path"
            return 1
        fi
    fi

    # Certificate expiry validation - skip for system CA bundles (they may contain expired certs)
    if [ "$is_system_ca" != "yes" ]; then
        local cert_check
        cert_check=$(timeout 2s env PEM_FILE="$pem_path" python3 - << 'PY'
from os import getenv
from pathlib import Path
from datetime import datetime, timezone
from cryptography import x509

try:
    pem_file = getenv("PEM_FILE", "")
    data = Path(pem_file).read_bytes()
    certs = x509.load_pem_x509_certificates(data)
    if not certs:
        print("NO_CERTS")
        exit(1)

    now = datetime.now(timezone.utc)
    for idx, cert in enumerate(certs, start=1):
        if now < cert.not_valid_before_utc:
            print(f"NOT_VALID_YET|{idx}")
            exit(1)
        if now > cert.not_valid_after_utc:
            print(f"EXPIRED|{idx}")
            exit(1)

    print("VALID")
except Exception as e:
    print(f"ERROR|{e}")
    exit(1)
PY
)

        if [ "$cert_check" != "VALID" ]; then
            log "$LOG_CONTEXT" "❌" "PEM certificate validation failed: $cert_check"
            return 1
        fi

        log "$LOG_CONTEXT" "✅" "PEM certificate is valid"
    else
        log "$LOG_CONTEXT" "ℹ️" "Skipping expiry validation for system CA bundle (validation delegated to TLS handshake)"
    fi

    # Determine port: use provided port or fall back to database type default
    if [ "$port" = "(default)" ] || [ -z "$port" ]; then
        case "$db_type" in
            postgres) port=5432 ;;
            mysql|mariadb) port=3306 ;;
            *) port=5432 ;; # Default to postgres
        esac
    fi

    # Test TLS connection
    log "$LOG_CONTEXT" "ℹ️" "Testing TLS connection to ${host}:${port} (${db_type})"

    # Resolve hostname to IP addresses
    local ips
    ips=$(getent hosts "$host" 2>/dev/null | awk '{print $1}')

    if [ -z "$ips" ]; then
        # If hostname doesn't resolve, try direct connection to hostname
        local direct_cmd="openssl s_client -connect $host:$port"
        [ -f "$pem_path" ] && direct_cmd="$direct_cmd -CAfile $pem_path"
        case "$db_type" in
            postgres) direct_cmd="$direct_cmd -starttls postgres" ;;
            mysql|mariadb) direct_cmd="$direct_cmd -starttls mysql" ;;
        esac

        log "$LOG_CONTEXT" "ℹ️" "No DNS resolution for ${host}, testing direct connection"
        if echo "Q" | timeout 2s $direct_cmd >/dev/null 2>&1; then
            log "$LOG_CONTEXT" "✅" "TLS connection successful to ${host}:${port}"
            return 0
        else
            log "$LOG_CONTEXT" "❌" "TLS connection failed to ${host}:${port}"
            return 1
        fi
    fi

    # Try each IP address and report all results
    local ip
    local found_success=0
    local success_ips=""
    local failed_ips=""
    local total_ips=0
    local passed_ips=0

    while IFS= read -r ip; do
        ((total_ips++))
        local ip_cmd="openssl s_client -connect $ip:$port"

        # Add CA certificate verification
        if [ -f "$pem_path" ]; then
            ip_cmd="$ip_cmd -CAfile $pem_path"
        fi

        # Add STARTTLS for database protocols
        case "$db_type" in
            postgres)
                ip_cmd="$ip_cmd -starttls postgres"
                ;;
            mysql|mariadb)
                ip_cmd="$ip_cmd -starttls mysql"
                ;;
        esac

        log "$LOG_CONTEXT" "ℹ️" "Testing TLS connection to ${ip}:${port} (resolved from ${host})"
        if echo "Q" | timeout 2s $ip_cmd >/dev/null 2>&1; then
            log "$LOG_CONTEXT" "✅" "TLS connection successful to ${ip}:${port}"
            success_ips="${success_ips}${ip}:${port} "
            found_success=1
            ((passed_ips++))
        else
            log "$LOG_CONTEXT" "❌" "TLS connection failed to ${ip}:${port}"
            failed_ips="${failed_ips}${ip}:${port} "
        fi
    done <<< "$ips"

    # Report overall results
    if [ "$found_success" = "1" ]; then
        log "$LOG_CONTEXT" "✅" "TLS validation passed (${passed_ips}/${total_ips} IPs: ${success_ips%% })"
        return 0
    else
        log "$LOG_CONTEXT" "❌" "TLS validation failed for all IPs (${total_ips} failed: ${failed_ips%% }), continuing startup"
        return 1
    fi
}
