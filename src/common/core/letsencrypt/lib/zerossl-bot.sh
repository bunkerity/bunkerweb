#!/bin/bash
# Source: https://github.com/zerossl/zerossl-bot/commit/be1d6df0fb233e3393d2b317985987875a52c163

CERTBOT_EXEC="${CERTBOT_BIN:-}"
if [ -n "$CERTBOT_EXEC" ]; then
    if [ ! -x "$CERTBOT_EXEC" ]; then
        echo "Configured CERTBOT_BIN is not executable: $CERTBOT_EXEC"
        exit 1
    fi
else
    CERTBOT_EXEC="$(command -v certbot)"
    if [ -z "$CERTBOT_EXEC" ] || [ ! -x "$CERTBOT_EXEC" ]; then
        echo You have to install certbot
        exit 1
    fi
fi

CERTBOT_ARGS=()
USER_AGENT="BunkerWeb"

if [ -z "${BUNKERWEB_VERSION:-}" ] && [ -r "/usr/share/bunkerweb/VERSION" ]; then
    BUNKERWEB_VERSION="$(tr -d '\n\r' < /usr/share/bunkerweb/VERSION)"
fi
if [ -n "${BUNKERWEB_VERSION:-}" ]; then
    USER_AGENT="BunkerWeb/${BUNKERWEB_VERSION}"
fi

function normalize_non_negative_int()
{
    local value=$1
    local default_value=$2
    if [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "$value"
    else
        echo "$default_value"
    fi
}

function normalize_positive_int()
{
    local value=$1
    local default_value=$2
    if [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "$value"
    else
        echo "$default_value"
    fi
}

ZEROSSL_API_RETRY_EFFECTIVE="$(normalize_non_negative_int "${ZEROSSL_API_RETRY:-${LETS_ENCRYPT_ZEROSSL_API_RETRY:-3}}" "3")"
ZEROSSL_API_RETRY_DELAY_EFFECTIVE="$(normalize_non_negative_int "${ZEROSSL_API_RETRY_DELAY:-${LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY:-2}}" "2")"
ZEROSSL_API_CONNECT_TIMEOUT_EFFECTIVE="$(normalize_positive_int "${ZEROSSL_API_CONNECT_TIMEOUT:-${LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT:-5}}" "5")"
ZEROSSL_API_MAX_TIME_EFFECTIVE="$(normalize_positive_int "${ZEROSSL_API_MAX_TIME:-${LETS_ENCRYPT_ZEROSSL_API_MAX_TIME:-20}}" "20")"
ZEROSSL_BOT_DEBUG_EFFECTIVE="${ZEROSSL_BOT_DEBUG:-${CUSTOM_LOG_LEVEL:-${LOG_LEVEL:-INFO}}}"
ZEROSSL_API_KEY="${LETS_ENCRYPT_ZEROSSL_API_KEY:-}"

function is_debug_enabled()
{
    case "${ZEROSSL_BOT_DEBUG_EFFECTIVE,,}" in
        1|true|yes|on|debug|trace) return 0 ;;
        *) return 1 ;;
    esac
}

function is_trace_enabled()
{
    case "${ZEROSSL_BOT_DEBUG_EFFECTIVE,,}" in
        trace) return 0 ;;
        *) return 1 ;;
    esac
}

function log_debug()
{
    if is_debug_enabled; then
        echo "[zerossl-bot][debug] $*" >&2
    fi
}

function extract_zerossl_error_message()
{
    local json_payload=$1
    local python
    python=$(command -v python3 || command -v python)
    if [ -z "$python" ]; then
        return 0
    fi
    PYTHONIOENCODING=utf8 "$python" -c '
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

error = payload.get("error")
if isinstance(error, dict):
    msg = error.get("details") or error.get("message") or ""
    if msg:
        print(str(msg))
        sys.exit(0)

msg = payload.get("message")
if msg:
    print(str(msg))
' "$json_payload"
}

function zerossl_api_request()
{
    local method=$1
    local safe_url=$2
    local curl_url=$2
    shift 2

    local response http_code body
    if ! is_trace_enabled && [[ "$safe_url" == *"access_key="* ]]; then
        safe_url="${safe_url%%access_key=*}access_key=***"
    fi
    log_debug "Requesting ZeroSSL API (method=${method}, url=${safe_url}, user_agent=${USER_AGENT})"
    curl_url="${curl_url//\\/\\\\}"
    curl_url="${curl_url//\"/\\\"}"
    response="$(
        curl \
            --silent \
            --show-error \
            --location \
            --retry "${ZEROSSL_API_RETRY_EFFECTIVE}" \
            --retry-delay "${ZEROSSL_API_RETRY_DELAY_EFFECTIVE}" \
            --retry-all-errors \
            --connect-timeout "${ZEROSSL_API_CONNECT_TIMEOUT_EFFECTIVE}" \
            --max-time "${ZEROSSL_API_MAX_TIME_EFFECTIVE}" \
            --request "$method" \
            --user-agent "$USER_AGENT" \
            --header "Accept: application/json" \
            --write-out $'\n%{http_code}' \
            --config <(printf 'url = "%s"\n' "$curl_url") \
            "$@"
    )"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
        echo "ZeroSSL API request failed (network or curl error)." >&2
        log_debug "curl failed while calling ZeroSSL API."
        return 1
    fi

    http_code="${response##*$'\n'}"
    body="${response%$'\n'*}"
    log_debug "ZeroSSL API response status=${http_code}, body_length=${#body}"

    if [[ "$http_code" != 2* ]]; then
        echo "ZeroSSL API request failed with HTTP status ${http_code}." >&2
        local err_message
        err_message="$(extract_zerossl_error_message "$body")"
        if [ -n "$err_message" ]; then
            echo "ZeroSSL API error: $err_message" >&2
        fi
        return 1
    fi

    printf '%s' "$body"
}

function parse_eab_credentials()
{
    local python
    local eab_output
    local parse_status
    local ZEROSSL_EAB_KID=""
    local ZEROSSL_EAB_HMAC_KEY=""

    log_debug "Parsing ZeroSSL EAB credentials payload."
    python=$(command -v python3 || command -v python)
    case "$("$python" -V)" in
      ('Python 3'*) ;;
      (*) echo 'No python3 detected'; exit 1 ;;
    esac
    pyprog='import sys, json
try:
    js = json.loads(sys.argv[1])
except Exception as exc:
    print(f"Invalid ZeroSSL API response: {exc}", file=sys.stderr)
    raise SystemExit(1)
kid = js.get("eab_kid")
hmac = js.get("eab_hmac_key")
if not kid or not hmac:
    err = js.get("error")
    if isinstance(err, dict):
        message = err.get("details") or err.get("message")
        if message:
            print(f"ZeroSSL API returned an error: {message}", file=sys.stderr)
    print("ZeroSSL API response did not include EAB credentials.", file=sys.stderr)
    raise SystemExit(1)
print(kid)
print(hmac)
';
    eab_output="$(PYTHONIOENCODING=utf8 "$python" -c "$pyprog" "$1")"
    parse_status=$?
    if [ $parse_status -ne 0 ]; then
        echo "Failed to parse ZeroSSL EAB credentials." >&2
        log_debug "EAB credentials parsing failed."
        return 1
    fi

    {
      IFS= read -r ZEROSSL_EAB_KID &&
      IFS= read -r ZEROSSL_EAB_HMAC_KEY
    } <<< "$eab_output"

    if [ -z "$ZEROSSL_EAB_KID" ] || [ -z "$ZEROSSL_EAB_HMAC_KEY" ]; then
        echo "ZeroSSL API response did not include complete EAB credentials." >&2
        log_debug "EAB credentials payload was incomplete."
        return 1
    fi

    log_debug "Parsed EAB credentials successfully (kid_length=${#ZEROSSL_EAB_KID}, hmac_length=${#ZEROSSL_EAB_HMAC_KEY})."
    CERTBOT_ARGS+=(--eab-kid "$ZEROSSL_EAB_KID" --eab-hmac-key "$ZEROSSL_EAB_HMAC_KEY" --server "https://acme.zerossl.com/v2/DV90")
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --zerossl-email=*)
            ZEROSSL_EMAIL=${1#*=}
        ;;
        --email|--zerossl-email|-m)
           ZEROSSL_EMAIL=$2
           CERTBOT_ARGS+=(-m "$2")
           shift
        ;;
        *) CERTBOT_ARGS+=("$1") ;;
    esac
    shift
done

set -- "${CERTBOT_ARGS[@]}"
log_debug "zerossl-bot initialized (certbot_exec=${CERTBOT_EXEC}, user_agent=${USER_AGENT})."
log_debug "ZeroSSL API controls (retry=${ZEROSSL_API_RETRY_EFFECTIVE}, retry_delay=${ZEROSSL_API_RETRY_DELAY_EFFECTIVE}, connect_timeout=${ZEROSSL_API_CONNECT_TIMEOUT_EFFECTIVE}, max_time=${ZEROSSL_API_MAX_TIME_EFFECTIVE})."

if [[ -n $ZEROSSL_API_KEY ]]; then
    log_debug "Using ZeroSSL API key flow to fetch EAB credentials."
    api_response="$(zerossl_api_request "POST" "https://api.zerossl.com/acme/eab-credentials?access_key=$ZEROSSL_API_KEY")" || exit 1
    parse_eab_credentials "$api_response" || exit 1
elif [[ -n $ZEROSSL_EMAIL ]]; then
    log_debug "Using ZeroSSL email flow to fetch EAB credentials."
    api_response="$(
        zerossl_api_request \
            "POST" \
            "https://api.zerossl.com/acme/eab-credentials-email" \
            --header "Content-Type: application/x-www-form-urlencoded" \
            --data-urlencode "email=$ZEROSSL_EMAIL"
    )" || exit 1
    parse_eab_credentials "$api_response" || exit 1
else
    log_debug "No ZeroSSL API key or email provided; continuing without EAB prefetch."
fi

# Prevent ZeroSSL API credentials from propagating to certbot's process environment.
unset LETS_ENCRYPT_ZEROSSL_API_KEY

if is_debug_enabled; then
    if is_trace_enabled; then
        log_debug "Launching certbot with full arguments."
        printf '%s ' "$CERTBOT_EXEC" "${CERTBOT_ARGS[@]}"; echo
    else
        redacted_args=()
        redact_next="no"
        for arg in "${CERTBOT_ARGS[@]}"; do
            if [ "$redact_next" = "yes" ]; then
                redacted_args+=("***")
                redact_next="no"
                continue
            fi
            case "$arg" in
                --eab-kid|--eab-hmac-key)
                    redacted_args+=("$arg")
                    redact_next="yes"
                ;;
                *)
                    redacted_args+=("$arg")
                ;;
            esac
        done
        log_debug "Launching certbot with redacted arguments."
        printf '%s ' "$CERTBOT_EXEC" "${redacted_args[@]}"; echo
    fi
fi

"$CERTBOT_EXEC" "${CERTBOT_ARGS[@]}"
