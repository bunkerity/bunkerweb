/*
 *  Public key-based signature verification program
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"
/* md.h is included this early since MD_CAN_XXX macros are defined there. */
#include "mbedtls/md.h"

#if !defined(MBEDTLS_BIGNUM_C) || !defined(MBEDTLS_MD_C) || \
    !defined(MBEDTLS_MD_CAN_SHA256) || !defined(MBEDTLS_PK_PARSE_C) ||   \
    !defined(MBEDTLS_FS_IO)
int main(void)
{
    mbedtls_printf("MBEDTLS_BIGNUM_C and/or MBEDTLS_MD_C and/or "
                   "MBEDTLS_MD_CAN_SHA256 and/or MBEDTLS_PK_PARSE_C and/or "
                   "MBEDTLS_FS_IO not defined.\n");
    mbedtls_exit(0);
}
#else

#include "mbedtls/error.h"
#include "mbedtls/pk.h"

#include <stdio.h>
#include <string.h>


int main(int argc, char *argv[])
{
    FILE *f;
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    size_t i;
    mbedtls_pk_context pk;
    unsigned char hash[32];
    unsigned char buf[MBEDTLS_PK_SIGNATURE_MAX_SIZE];
    char filename[512];

    mbedtls_pk_init(&pk);

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        mbedtls_fprintf(stderr, "Failed to initialize PSA Crypto implementation: %d\n",
                        (int) status);
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */

    if (argc != 3) {
        mbedtls_printf("usage: mbedtls_pk_verify <key_file> <filename>\n");

#if defined(_WIN32)
        mbedtls_printf("\n");
#endif

        goto exit;
    }

    mbedtls_printf("\n  . Reading public key from '%s'", argv[1]);
    fflush(stdout);

    if ((ret = mbedtls_pk_parse_public_keyfile(&pk, argv[1])) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_pk_parse_public_keyfile returned -0x%04x\n",
                       (unsigned int) -ret);
        goto exit;
    }

    /*
     * Extract the signature from the file
     */
    mbedtls_snprintf(filename, sizeof(filename), "%s.sig", argv[2]);

    if ((f = fopen(filename, "rb")) == NULL) {
        mbedtls_printf("\n  ! Could not open %s\n\n", filename);
        goto exit;
    }

    i = fread(buf, 1, sizeof(buf), f);

    fclose(f);

    /*
     * Compute the SHA-256 hash of the input file and
     * verify the signature
     */
    mbedtls_printf("\n  . Verifying the SHA-256 signature");
    fflush(stdout);

    if ((ret = mbedtls_md_file(
             mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
             argv[2], hash)) != 0) {
        mbedtls_printf(" failed\n  ! Could not open or read %s\n\n", argv[2]);
        goto exit;
    }

    if ((ret = mbedtls_pk_verify(&pk, MBEDTLS_MD_SHA256, hash, 0,
                                 buf, i)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_pk_verify returned -0x%04x\n", (unsigned int) -ret);
        goto exit;
    }

    mbedtls_printf("\n  . OK (the signature is valid)\n\n");

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:
    mbedtls_pk_free(&pk);
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
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_MD_CAN_SHA256 &&
          MBEDTLS_PK_PARSE_C && MBEDTLS_FS_IO */
