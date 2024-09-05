/*
 *  Public key-based simple decryption program
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if defined(MBEDTLS_BIGNUM_C) && defined(MBEDTLS_PK_PARSE_C) && \
    defined(MBEDTLS_FS_IO) && defined(MBEDTLS_ENTROPY_C) && \
    defined(MBEDTLS_CTR_DRBG_C)
#include "mbedtls/error.h"
#include "mbedtls/pk.h"
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <stdio.h>
#include <string.h>
#endif

#if !defined(MBEDTLS_BIGNUM_C) || !defined(MBEDTLS_PK_PARSE_C) ||  \
    !defined(MBEDTLS_FS_IO) || !defined(MBEDTLS_ENTROPY_C) || \
    !defined(MBEDTLS_CTR_DRBG_C)
int main(void)
{
    mbedtls_printf("MBEDTLS_BIGNUM_C and/or MBEDTLS_PK_PARSE_C and/or "
                   "MBEDTLS_FS_IO and/or MBEDTLS_ENTROPY_C and/or "
                   "MBEDTLS_CTR_DRBG_C not defined.\n");
    mbedtls_exit(0);
}
#else


int main(int argc, char *argv[])
{
    FILE *f;
    int ret = 1;
    unsigned c;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    size_t i, olen = 0;
    mbedtls_pk_context pk;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    unsigned char result[1024];
    unsigned char buf[512];
    const char *pers = "mbedtls_pk_decrypt";
    ((void) argv);

    mbedtls_pk_init(&pk);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&ctr_drbg);

    memset(result, 0, sizeof(result));

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        mbedtls_fprintf(stderr, "Failed to initialize PSA Crypto implementation: %d\n",
                        (int) status);
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */

    if (argc != 2) {
        mbedtls_printf("usage: mbedtls_pk_decrypt <key_file>\n");

#if defined(_WIN32)
        mbedtls_printf("\n");
#endif

        goto exit;
    }

    mbedtls_printf("\n  . Seeding the random number generator...");
    fflush(stdout);

    if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func,
                                     &entropy, (const unsigned char *) pers,
                                     strlen(pers))) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ctr_drbg_seed returned -0x%04x\n",
                       (unsigned int) -ret);
        goto exit;
    }

    mbedtls_printf("\n  . Reading private key from '%s'", argv[1]);
    fflush(stdout);

    if ((ret = mbedtls_pk_parse_keyfile(&pk, argv[1], "",
                                        mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_pk_parse_keyfile returned -0x%04x\n",
                       (unsigned int) -ret);
        goto exit;
    }

    /*
     * Extract the RSA encrypted value from the text file
     */
    if ((f = fopen("result-enc.txt", "rb")) == NULL) {
        mbedtls_printf("\n  ! Could not open %s\n\n", "result-enc.txt");
        ret = 1;
        goto exit;
    }

    i = 0;
    while (fscanf(f, "%02X", (unsigned int *) &c) > 0 &&
           i < (int) sizeof(buf)) {
        buf[i++] = (unsigned char) c;
    }

    fclose(f);

    /*
     * Decrypt the encrypted RSA data and print the result.
     */
    mbedtls_printf("\n  . Decrypting the encrypted data");
    fflush(stdout);

    if ((ret = mbedtls_pk_decrypt(&pk, buf, i, result, &olen, sizeof(result),
                                  mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_pk_decrypt returned -0x%04x\n",
                       (unsigned int) -ret);
        goto exit;
    }

    mbedtls_printf("\n  . OK\n\n");

    mbedtls_printf("The decrypted result is: '%s'\n\n", result);

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    mbedtls_pk_free(&pk);
    mbedtls_entropy_free(&entropy);
    mbedtls_ctr_drbg_free(&ctr_drbg);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */

#if defined(MBEDTLS_ERROR_C)
    if (exit_code != MBEDTLS_EXIT_SUCCESS) {
        mbedtls_strerror(ret, (char *) buf, sizeof(buf));
        mbedtls_printf("  !  Last error was: %s\n", buf);
    }
#endif

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_PK_PARSE_C && MBEDTLS_FS_IO &&
          MBEDTLS_ENTROPY_C && MBEDTLS_CTR_DRBG_C */
