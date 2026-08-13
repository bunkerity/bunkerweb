#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"
release="${3:-}"
category="${4:-}"

if [ -z "$release" ] ; then
    log "RUN" "❌" "Please provide a release as 3rd argument"
    exit 1
elif [ -z "$category" ] ; then
    log "RUN" "❌" "Please provide a category as 4th argument"
    exit 1
fi

if redis-cli ping | grep -q "PONG" ; then
    log "RUN" "ℹ️ " "💽 Redis server is healthy ✅"
else
    log "RUN" "❌" "💽 Redis server is not healthy"
    exit 1
fi

redis-cli set end 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set end flag in redis server"
    exit 1
fi

redis-cli set full_clean 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set full_clean flag in redis server"
    exit 1
fi

redis-cli set restart_stack 1 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set restart_stack flag in redis server"
    exit 1
fi

redis-cli set restart_whole_stack 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set restart_whole_stack flag in redis server"
    exit 1
fi

redis-cli set restart_services 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set restart_services flag in redis server"
    exit 1
fi

redis-cli set need_socket 0 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set need_socket flag in redis server"
    exit 1
fi

# Clear previous version tracking to start fresh
redis-cli del previous_bw_version > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to clear previous_bw_version in redis server"
    exit 1
fi

first_run=true
restart_stack=1
full_clean=0

if [[ "$category" =~ ";" ]] ; then
    category=$(echo "$category" | cut -d ";" -f 1)
fi

if [ "$integration" == "Linux" ] ; then
    cleanup_stack
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        exit 1
    fi
fi

tests=$(redis-cli lrange tests 0 -1)
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to get tests from redis server"
    exit 1
fi

run_before=false

for test in $tests ; do
    log "RUN" "ℹ️ " "🧑‍🔧 Generating test \"$test\" ..."

    if [ "$integration" == "Linux" ] ; then
        if $IS_FREEBSD ; then
            chmod 777 /etc/bunkerweb/variables.env
        else
            docker exec -u 0 bunkerweb-linux chmod 777 /etc/bunkerweb/variables.env
        fi
    fi

    if [ -f "tests/scripts/before/$category.sh" ] && ! $run_before ; then
        log "RUN" "ℹ️ " "🔧 Running before script for \"$category\" and importing variables ..."

        chmod +x "tests/scripts/before/$category.sh"

        # shellcheck disable=SC1090
        source ./tests/scripts/before/"$category".sh "$integration" "$release" "$category"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            exit 1
        fi
        run_before=true
    fi

    if [ "$release" == "dev" ] ; then
        python3 tests/generate.py "$integration" "$type" "$test" --dev
    else
        python3 tests/generate.py "$integration" "$type" "$test"
    fi

    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        log "RUN" "❌" "🧑‍🔧 Failed to generate test \"$test\""
        exit 1
    fi

    first_try=true
    retries=$(redis-cli get retries)
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] || [ -z "$retries" ] ; then
        log "RUN" "❌" "💽 Failed to get retries from redis server"
        exit 1
    fi

    while $first_try || [ "$retries" -gt 0 ] ; do
        if [ "$restart_stack" -eq 1 ] ; then
            if $first_run || [ "$full_clean" -eq 1 ] ; then
                ./tests/scripts/start.sh "$integration" "$type"
                ret=$?
                # shellcheck disable=SC2181
                if [ $ret -ne 0 ] ; then
                    exit $ret
                fi
            else
                restart_stack
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    exit 1
                fi
            fi

            ./tests/scripts/wait.sh "$integration" "$type"
            ret=$?
            # shellcheck disable=SC2181
            if [ $ret -ne 0 ] ; then
                exit $ret
            fi
        fi

        python3 "tests/$type.py" "$test" "$integration"
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            log "RUN" "❌" "Test \"$test\" failed"
            retries=$((retries - 1))
            if [ "$retries" -gt 0 ] ; then
                log "RUN" "⚠️" "Retrying test \"$test\" ($retries retries left)"
            else
                exit 1
            fi
        else
            retries=0
        fi

        if [[ -n ${DEBUG:-} ]] ; then
            log_stack
        fi

        restart_stack=$(redis-cli get restart_stack)
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] || [ -z "$restart_stack" ] ; then
            log "RUN" "❌" "💽 Failed to get restart_stack from redis server"
            exit 1
        fi

        full_clean=$(redis-cli get full_clean)
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] || [ -z "$full_clean" ] ; then
            log "RUN" "❌" "💽 Failed to get full_clean from redis server"
            exit 1
        fi

        first_try=false
        first_run=false

        if [ "$restart_stack" -eq 1 ] ; then
            if [ "$full_clean" -eq 1 ] ; then
                cleanup_stack
                # shellcheck disable=SC2181
                if [ $? -ne 0 ] ; then
                    exit 1
                fi
            fi

            redis-cli set last_test "$(date '+%Y-%m-%dT%H:%M:%S%z')" > /dev/null
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                log "UTILS" "❌" "💽 Failed to set last test date to redis server"
                exit 1
            fi
        fi
    done

    log "RUN" "ℹ️ " "Test \"$test\" passed ✅"
    echo " "
done

log "RUN" "ℹ️ " "All tests passed ✅"

redis-cli set end 1 > /dev/null
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    log "RUN" "❌" "💽 Failed to set end flag in redis server"
    exit 1
fi
