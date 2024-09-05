#! /usr/bin/env sh

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
#
# Purpose
#
# Check if generated files are up-to-date.

set -eu

if [ $# -ne 0 ] && [ "$1" = "--help" ]; then
    cat <<EOF
$0 [-l | -u]
This script checks that all generated file are up-to-date. If some aren't, by
default the scripts reports it and exits in error; with the -u option, it just
updates them instead.

  -u    Update the files rather than return an error for out-of-date files.
  -l    List generated files, but do not update them.
EOF
    exit
fi

in_mbedtls_repo () {
    test -d include -a -d library -a -d programs -a -d tests
}

in_tf_psa_crypto_repo () {
    test -d include -a -d core -a -d drivers -a -d programs -a -d tests
}

if in_mbedtls_repo; then
    library_dir='library'
elif in_tf_psa_crypto_repo; then
    library_dir='core'
else
    echo "Must be run from Mbed TLS root or TF-PSA-Crypto root" >&2
    exit 1
fi

UPDATE=
LIST=
while getopts lu OPTLET; do
    case $OPTLET in
      l) LIST=1;;
      u) UPDATE=1;;
    esac
done

# check SCRIPT FILENAME[...]
# check SCRIPT DIRECTORY
# Run SCRIPT and check that it does not modify any of the specified files.
# In the first form, there can be any number of FILENAMEs, which must be
# regular files.
# In the second form, there must be a single DIRECTORY, standing for the
# list of files in the directory. Running SCRIPT must not modify any file
# in the directory and must not add or remove files either.
# If $UPDATE is empty, abort with an error status if a file is modified.
check()
{
    SCRIPT=$1
    shift

    if [ -n "$LIST" ]; then
        printf '%s\n' "$@"
        return
    fi

    directory=
    if [ -d "$1" ]; then
        directory="$1"
        rm -f "$directory"/*.bak
        set -- "$1"/*
    fi

    for FILE in "$@"; do
        if [ -e "$FILE" ]; then
            cp -p "$FILE" "$FILE.bak"
        else
            rm -f "$FILE.bak"
        fi
    done

    "$SCRIPT"

    # Compare the script output to the old files and remove backups
    for FILE in "$@"; do
        if diff "$FILE" "$FILE.bak" >/dev/null 2>&1; then
            # Move the original file back so that $FILE's timestamp doesn't
            # change (avoids spurious rebuilds with make).
            mv "$FILE.bak" "$FILE"
        else
            echo "'$FILE' was either modified or deleted by '$SCRIPT'"
            if [ -z "$UPDATE" ]; then
                exit 1
            else
                rm -f "$FILE.bak"
            fi
        fi
    done

    if [ -n "$directory" ]; then
        old_list="$*"
        set -- "$directory"/*
        new_list="$*"
        # Check if there are any new files
        if [ "$old_list" != "$new_list" ]; then
            echo "Files were deleted or created by '$SCRIPT'"
            echo "Before: $old_list"
            echo "After: $new_list"
            if [ -z "$UPDATE" ]; then
                exit 1
            fi
        fi
    fi
}

# Note: if the format of calls to the "check" function changes, update
# scripts/code_style.py accordingly. For generated C source files (*.h or *.c),
# the format must be "check SCRIPT FILENAME...". For other source files,
# any shell syntax is permitted (including e.g. command substitution).

# Note: Instructions to generate those files are replicated in:
#   - **/Makefile (to (re)build them with make)
#   - **/CMakeLists.txt (to (re)build them with cmake)
#   - scripts/make_generated_files.bat (to generate them under Windows)

# These checks are common to Mbed TLS and TF-PSA-Crypto
check scripts/generate_psa_constants.py programs/psa/psa_constant_names_generated.c
check framework/scripts/generate_bignum_tests.py $(framework/scripts/generate_bignum_tests.py --list)
check framework/scripts/generate_config_tests.py $(framework/scripts/generate_config_tests.py --list)
check framework/scripts/generate_ecp_tests.py $(framework/scripts/generate_ecp_tests.py --list)
check framework/scripts/generate_psa_tests.py $(framework/scripts/generate_psa_tests.py --list)
check framework/scripts/generate_test_keys.py tests/src/test_keys.h
check scripts/generate_driver_wrappers.py $library_dir/psa_crypto_driver_wrappers.h $library_dir/psa_crypto_driver_wrappers_no_static.c

# Additional checks for Mbed TLS only
if in_mbedtls_repo; then
    check scripts/generate_errors.pl library/error.c
    check scripts/generate_query_config.pl programs/test/query_config.c
    check scripts/generate_features.pl library/version_features.c
    check scripts/generate_ssl_debug_helpers.py library/ssl_debug_helpers_generated.c
    check framework/scripts/generate_test_cert_macros.py tests/src/test_certs.h
    # generate_visualc_files enumerates source files (library/*.c). It doesn't
    # care about their content, but the files must exist. So it must run after
    # the step that creates or updates these files.
    check scripts/generate_visualc_files.pl visualc/VS2017
fi

# Generated files that are present in the repository even in the development
# branch. (This is intended to be temporary, until the generator scripts are
# fully reviewed and the build scripts support a generated header file.)
check framework/scripts/generate_psa_wrappers.py tests/include/test/psa_test_wrappers.h tests/src/psa_test_wrappers.c
