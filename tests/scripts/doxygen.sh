#!/bin/sh

# Make sure the doxygen documentation builds without warnings
#
# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

# Abort on errors (and uninitialised variables)
set -eu

if [ -d library -a -d include -a -d tests ]; then :; else
    echo "Must be run from Mbed TLS root" >&2
    exit 1
fi

if scripts/apidoc_full.sh > doc.out 2>doc.err; then :; else
    cat doc.err
    echo "FAIL" >&2
    exit 1;
fi

cat doc.out doc.err | \
    grep -v "warning: ignoring unsupported tag" \
    > doc.filtered

if grep -E "(warning|error):" doc.filtered; then
    echo "FAIL" >&2
    exit 1;
fi

make apidoc_clean
rm -f doc.out doc.err doc.filtered
