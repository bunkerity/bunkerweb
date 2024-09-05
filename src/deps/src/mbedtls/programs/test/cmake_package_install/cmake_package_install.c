/*
 * Simple program to test that Mbed TLS builds correctly as an installable CMake
 * package.
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#include "mbedtls/version.h"

/* The main reason to build this is for testing the CMake build, so the program
 * doesn't need to do very much. It calls a single library function to ensure
 * linkage works, but that is all. */
int main()
{
    /* This version string is 18 bytes long, as advised by version.h. */
    char version[18];

    mbedtls_version_get_string_full(version);

    mbedtls_printf("Built against %s\n", version);

    return 0;
}
