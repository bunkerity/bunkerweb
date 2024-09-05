/**
 *  \brief Use and generate multiple entropies calls into a file
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if defined(MBEDTLS_ENTROPY_C) && defined(MBEDTLS_FS_IO)
#include "mbedtls/entropy.h"

#include <stdio.h>
#endif

#if !defined(MBEDTLS_ENTROPY_C) || !defined(MBEDTLS_FS_IO)
int main(void)
{
    mbedtls_printf("MBEDTLS_ENTROPY_C and/or MBEDTLS_FS_IO not defined.\n");
    mbedtls_exit(0);
}
#else


int main(int argc, char *argv[])
{
    FILE *f;
    int i, k, ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    mbedtls_entropy_context entropy;
    unsigned char buf[MBEDTLS_ENTROPY_BLOCK_SIZE];

    if (argc < 2) {
        mbedtls_fprintf(stderr, "usage: %s <output filename>\n", argv[0]);
        mbedtls_exit(exit_code);
    }

    if ((f = fopen(argv[1], "wb+")) == NULL) {
        mbedtls_printf("failed to open '%s' for writing.\n", argv[1]);
        mbedtls_exit(exit_code);
    }

    mbedtls_entropy_init(&entropy);

    for (i = 0, k = 768; i < k; i++) {
        ret = mbedtls_entropy_func(&entropy, buf, sizeof(buf));
        if (ret != 0) {
            mbedtls_printf("  failed\n  !  mbedtls_entropy_func returned -%04X\n",
                           (unsigned int) ret);
            goto cleanup;
        }

        fwrite(buf, 1, sizeof(buf), f);

        mbedtls_printf("Generating %ldkb of data in file '%s'... %04.1f" \
                       "%% done\r",
                       (long) (sizeof(buf) * k / 1024),
                       argv[1],
                       (100 * (float) (i + 1)) / k);
        fflush(stdout);
    }

    exit_code = MBEDTLS_EXIT_SUCCESS;

cleanup:
    mbedtls_printf("\n");

    fclose(f);
    mbedtls_entropy_free(&entropy);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_ENTROPY_C */
