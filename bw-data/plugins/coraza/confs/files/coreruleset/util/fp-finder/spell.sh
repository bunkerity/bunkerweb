#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

RULES_DIR="${SCRIPT_DIR}/../../rules/"

for datafile in "$RULES_DIR"*.data; do
    DATAFILE_NAME=${datafile##*/}
    
    echo "-> checking ${DATAFILE_NAME}"

    for word in $(grep -E '^[a-z]+$' "${datafile}" | uniq | sort); do
        IS_NOT_ENGLISH=$(echo "${word}" | spell | wc -l)
        if [ "${IS_NOT_ENGLISH}" -lt 1 ]; then
            echo "   \`- found English word: ${word}"
        fi
    done

    echo ""
done
