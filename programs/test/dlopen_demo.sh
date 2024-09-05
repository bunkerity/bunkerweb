#!/bin/sh

# Run the shared library dynamic loading demo program.
# This is only expected to work when Mbed TLS is built as a shared library.

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

. "${0%/*}/../demo_common.sh"

msg "Test the dynamic loading of libmbed*"

program="$programs_dir/test/dlopen"
library_dir="$root_dir/library"

# Skip this test if we don't have a shared library build. Detect this
# through the absence of the demo program.
if [ ! -e "$program" ]; then
    msg "$0: this demo requires a shared library build."
    # Exit with a success status so that this counts as a pass for run_demos.py.
    exit
fi

# ELF-based Unix-like (Linux, *BSD, Solaris, ...)
if [ -n "${LD_LIBRARY_PATH-}" ]; then
    LD_LIBRARY_PATH="$library_dir:$LD_LIBRARY_PATH"
else
    LD_LIBRARY_PATH="$library_dir"
fi
export LD_LIBRARY_PATH

# OSX/macOS
if [ -n "${DYLD_LIBRARY_PATH-}" ]; then
    DYLD_LIBRARY_PATH="$library_dir:$DYLD_LIBRARY_PATH"
else
    DYLD_LIBRARY_PATH="$library_dir"
fi
export DYLD_LIBRARY_PATH

msg "Running dynamic loading test program: $program"
msg "Loading libraries from: $library_dir"
"$program"
