#!/bin/bash

print_usage()
{
    cat <<EOF
Usage: $0 [OPTION]...
Prepare the source tree for a release.

Options:
  -u    Prepare for development (undo the release preparation)
EOF
}

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

set -eu

if [ $# -ne 0 ] && [ "$1" = "--help" ]; then
    print_usage
    exit
fi

unrelease= # if non-empty, we're in undo-release mode
while getopts u OPTLET; do
    case $OPTLET in
        u) unrelease=1;;
        \?)
            echo 1>&2 "$0: unknown option: -$OPTLET"
            echo 1>&2 "Try '$0 --help' for more information."
            exit 3;;
    esac
done



#### .gitignore processing ####

GITIGNORES=$(find . -name ".gitignore")
for GITIGNORE in $GITIGNORES; do
    if [ -n "$unrelease" ]; then
        sed -i '/###START_COMMENTED_GENERATED_FILES###/,/###END_COMMENTED_GENERATED_FILES###/s/^#//' $GITIGNORE
        sed -i 's/###START_COMMENTED_GENERATED_FILES###/###START_GENERATED_FILES###/' $GITIGNORE
        sed -i 's/###END_COMMENTED_GENERATED_FILES###/###END_GENERATED_FILES###/' $GITIGNORE
    else
        sed -i '/###START_GENERATED_FILES###/,/###END_GENERATED_FILES###/s/^/#/' $GITIGNORE
        sed -i 's/###START_GENERATED_FILES###/###START_COMMENTED_GENERATED_FILES###/' $GITIGNORE
        sed -i 's/###END_GENERATED_FILES###/###END_COMMENTED_GENERATED_FILES###/' $GITIGNORE
    fi
done



#### Build scripts ####

# GEN_FILES defaults on (non-empty) in development, off (empty) in releases
if [ -n "$unrelease" ]; then
    r=' yes'
else
    r=''
fi
sed -i 's/^\(GEN_FILES[ ?:]*=\)\([^#]*\)/\1'"$r/" Makefile */Makefile

# GEN_FILES defaults on in development, off in releases
if [ -n "$unrelease" ]; then
    r='ON'
else
    r='OFF'
fi
sed -i '/[Oo][Ff][Ff] in development/! s/^\( *option *( *GEN_FILES  *"[^"]*"  *\)\([A-Za-z0-9][A-Za-z0-9]*\)/\1'"$r/" CMakeLists.txt
