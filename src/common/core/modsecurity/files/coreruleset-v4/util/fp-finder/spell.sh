#!/bin/bash

# This program uses WordNet to find English words. The WordNet license:

# WordNet Release 3.0 This software and database is being provided to you,
# the LICENSEE, by Princeton University under the following license.
# By obtaining, using and/or copying this software and database, you agree that you have read,
# understood, and will comply with these terms and conditions.: Permission to use, copy,
# modify and distribute this software and database and its documentation for any purpose and
# without fee or royalty is hereby granted, provided that you agree to comply with
# the following copyright notice and statements, including the disclaimer, and that the same
# appear on ALL copies of the software, database and documentation, including modifications
# that you make for internal use or for distribution.
# WordNet 3.0 Copyright 2006 by Princeton University.
# All rights reserved.
# THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON UNIVERSITY MAKES NO REPRESENTATIONS
# OR WARRANTIES, EXPRESS OR IMPLIED. BY WAY OF EXAMPLE, BUT NOT LIMITATION, PRINCETON UNIVERSITY
# MAKES NO REPRESENTATIONS OR WARRANTIES OF MERCHANT- ABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE
# OR THAT THE USE OF THE LICENSED SOFTWARE, DATABASE OR DOCUMENTATION WILL NOT INFRINGE ANY THIRD
# PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR OTHER RIGHTS.
# The name of Princeton University or Princeton may not be used in advertising or publicity
# pertaining to distribution of the software and/or database. Title to copyright in this
# software, database and any associated documentation shall at all times remain with
# Princeton University and LICENSEE agrees to preserve same.

if ! command -v wn > /dev/null 2>&1; then
    cat <<EOF
This program requires WordNet to be installed. Aborting.

The WordNet shell utility 'wn' can be obtained via the package
manager of your choice (the package is usually called 'wordnet').
EOF

    exit 1
fi

check() {
    if ! ${MACHINE_READABLE}; then
        echo "-> checking ${datafile_name}"
    fi

    local datafile="${1}"
    local datafile_name

    if [ "${1}" = "-" ]; then
        datafile="/dev/stdin"
        datafile_name="stdin"
    else
        datafile_name="${datafile##*/}"
    fi

    local datafile="${1}"
    local datafile_name

    if [ "${1}" = "-" ]; then
        datafile="/dev/stdin"
        datafile_name="stdin"
    else
        datafile_name="${datafile##*/}"
    fi

    while read -r word; do
        # wordnet exit code is equal to number of search results
        if [ -n "${SUFFIX}" ]; then
            word="$(sed -E "s/(.*)${SUFFIX}/\1/" <<<"${word}")"
        fi
        if ! grep -qE '^[A-Za-z]+$' <<<"${word}"; then
            continue
        fi

        if ! wn "${word}" >/dev/null 2>&1; then
            if ! ${MACHINE_READABLE}; then
                printf "   \`- found English word via wn: "
            fi
            echo "${word}"
        else
            if ${USE_EXTENDED}; then
                # shellcheck disable=SC2046
                if [ $(grep -c -E "^$word$" "$EXTENDED_WORDS_LIST_PATH") -ne 0 ]; then
                    if ! ${MACHINE_READABLE}; then
                        printf "   \`- found English word via extended list: "
                    fi
                    echo "${word}"
                fi
            fi
        fi
    done <<<"$(sort "${datafile}" | uniq)"

    if ! ${MACHINE_READABLE}; then
        echo ""
    fi
}

usage() {
    cat <<EOF
usage: spell.sh [-mhe] [file]
    Finds English words in files that contain word lists.

    The optional file argument is the path to a file you want to check. If omitted,
    all files with the .data suffix in the rules directory will be searched.

    -h, --help      Show this message and exit
    -m, --machine   Print machine readable output
    -e, --extended  English words are extended by a manual list
    -s, --suffix    Regular expression for suffix to strip off words passed to wordnet
EOF
}

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
EXTENDED_WORDS_LIST_PATH="${SCRIPT_DIR}/english-extended.txt"
RULES_DIR="${SCRIPT_DIR}/../../rules/"

MACHINE_READABLE=false
USE_EXTENDED=false

POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    # shellcheck disable=SC2221,SC2222
    case $1 in
        -m|--machine)
        MACHINE_READABLE=true
        shift
        ;;
        -e|--extended)
        USE_EXTENDED=true
        shift
        ;;
        -s|--suffix)
        shift
        SUFFIX="${1}"
        shift
        ;;
        -h|--help)
        usage
        exit 1
        ;;
        -*|--*)
        if [ $# -eq 1 ]; then
            POSITIONAL_ARGS+=("$1") # save positional arg
            shift # past argument
        else
            echo "Unknown option $1"
            usage
            exit 1
        fi
        ;;
        *)
        POSITIONAL_ARGS+=("$1") # save positional arg
        shift
        ;;
    esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters


if [ -n "${1}" ]; then
    check "${1}"
else
    for datafile in "${RULES_DIR}"*.data; do
        check "${datafile}"
    done
fi
