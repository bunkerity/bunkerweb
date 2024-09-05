/**
 *  \brief Use and generate random data into a file via the CTR_DBRG based on AES
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if defined(MBEDTLS_CTR_DRBG_C) && defined(MBEDTLS_ENTROPY_C) && \
    defined(MBEDTLS_FS_IO)
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <stdio.h>
#endif

#if !defined(MBEDTLS_CTR_DRBG_C) || !defined(MBEDTLS_ENTROPY_C) || \
    !defined(MBEDTLS_FS_IO)
int main(void)
{
    mbedtls_printf("MBEDTLS_CTR_DRBG_C and/or MBEDTLS_ENTROPY_C and/or MBEDTLS_FS_IO not defined.\n");
    mbedtls_exit(0);
}
#else


int main(int argc, char *argv[])
{
    FILE *f;
    int i, k, ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_entropy_context entropy;
    unsigned char buf[1024];

    mbedtls_ctr_drbg_init(&ctr_drbg);

    if (argc < 2) {
        mbedtls_fprintf(stderr, "usage: %s <output filename>\n", argv[0]);
        mbedtls_exit(exit_code);
    }

    if ((f = fopen(argv[1], "wb+")) == NULL) {
        mbedtls_printf("failed to open '%s' for writing.\n", argv[1]);
        mbedtls_exit(exit_code);
    }

    mbedtls_entropy_init(&entropy);
    ret = mbedtls_ctr_drbg_seed(&ctr_drbg,
                                mbedtls_entropy_func,
                                &entropy,
                                (const unsigned char *) "RANDOM_GEN",
                                10);
    if (ret != 0) {
        mbedtls_printf("failed in mbedtls_ctr_drbg_seed: %d\n", ret);
        goto cleanup;
    }
    mbedtls_ctr_drbg_set_prediction_resistance(&ctr_drbg, MBEDTLS_CTR_DRBG_PR_OFF);

#if defined(MBEDTLS_FS_IO)
    ret = mbedtls_ctr_drbg_update_seed_file(&ctr_drbg, "seedfile");

    if (ret == MBEDTLS_ERR_CTR_DRBG_FILE_IO_ERROR) {
        mbedtls_printf("Failed to open seedfile. Generating one.\n");
        ret = mbedtls_ctr_drbg_write_seed_file(&ctr_drbg, "seedfile");
        if (ret != 0) {
            mbedtls_printf("failed in mbedtls_ctr_drbg_write_seed_file: %d\n", ret);
            goto cleanup;
        }
    } else if (ret != 0) {
        mbedtls_printf("failed in mbedtls_ctr_drbg_update_seed_file: %d\n", ret);
        goto cleanup;
    }
#endif

    for (i = 0, k = 768; i < k; i++) {
        ret = mbedtls_ctr_drbg_random(&ctr_drbg, buf, sizeof(buf));
        if (ret != 0) {
            mbedtls_printf("failed!\n");
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
    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_CTR_DRBG_C && MBEDTLS_ENTROPY_C */
