/*
 *  RSA/SHA-256 signature creation program
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"
/* md.h is included this early since MD_CAN_XXX macros are defined there. */
#include "mbedtls/md.h"

#if !defined(MBEDTLS_BIGNUM_C) || !defined(MBEDTLS_RSA_C) ||  \
    !defined(MBEDTLS_MD_CAN_SHA256) || !defined(MBEDTLS_MD_C) || \
    !defined(MBEDTLS_FS_IO)
int main(void)
{
    mbedtls_printf("MBEDTLS_BIGNUM_C and/or MBEDTLS_RSA_C and/or "
                   "MBEDTLS_MD_C and/or "
                   "MBEDTLS_MD_CAN_SHA256 and/or MBEDTLS_FS_IO not defined.\n");
    mbedtls_exit(0);
}
#else

#include "mbedtls/rsa.h"

#include <stdio.h>
#include <string.h>


int main(int argc, char *argv[])
{
    FILE *f;
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    size_t i;
    mbedtls_rsa_context rsa;
    unsigned char hash[32];
    unsigned char buf[MBEDTLS_MPI_MAX_SIZE];
    char filename[512];
    mbedtls_mpi N, P, Q, D, E, DP, DQ, QP;

    mbedtls_rsa_init(&rsa);

    mbedtls_mpi_init(&N); mbedtls_mpi_init(&P); mbedtls_mpi_init(&Q);
    mbedtls_mpi_init(&D); mbedtls_mpi_init(&E); mbedtls_mpi_init(&DP);
    mbedtls_mpi_init(&DQ); mbedtls_mpi_init(&QP);

    if (argc != 2) {
        mbedtls_printf("usage: rsa_sign <filename>\n");

#if defined(_WIN32)
        mbedtls_printf("\n");
#endif

        goto exit;
    }

    mbedtls_printf("\n  . Reading private key from rsa_priv.txt");
    fflush(stdout);

    if ((f = fopen("rsa_priv.txt", "rb")) == NULL) {
        mbedtls_printf(" failed\n  ! Could not open rsa_priv.txt\n" \
                       "  ! Please run rsa_genkey first\n\n");
        goto exit;
    }

    if ((ret = mbedtls_mpi_read_file(&N, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&E, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&D, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&P, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&Q, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&DP, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&DQ, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&QP, 16, f)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_read_file returned %d\n\n", ret);
        fclose(f);
        goto exit;
    }
    fclose(f);

    if ((ret = mbedtls_rsa_import(&rsa, &N, &P, &Q, &D, &E)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_rsa_import returned %d\n\n",
                       ret);
        goto exit;
    }

    if ((ret = mbedtls_rsa_complete(&rsa)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_rsa_complete returned %d\n\n",
                       ret);
        goto exit;
    }

    mbedtls_printf("\n  . Checking the private key");
    fflush(stdout);
    if ((ret = mbedtls_rsa_check_privkey(&rsa)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_rsa_check_privkey failed with -0x%0x\n",
                       (unsigned int) -ret);
        goto exit;
    }

    /*
     * Compute the SHA-256 hash of the input file,
     * then calculate the RSA signature of the hash.
     */
    mbedtls_printf("\n  . Generating the RSA/SHA-256 signature");
    fflush(stdout);

    if ((ret = mbedtls_md_file(
             mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
             argv[1], hash)) != 0) {
        mbedtls_printf(" failed\n  ! Could not open or read %s\n\n", argv[1]);
        goto exit;
    }

    if ((ret = mbedtls_rsa_pkcs1_sign(&rsa, NULL, NULL, MBEDTLS_MD_SHA256,
                                      32, hash, buf)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_rsa_pkcs1_sign returned -0x%0x\n\n",
                       (unsigned int) -ret);
        goto exit;
    }

    /*
     * Write the signature into <filename>.sig
     */
    mbedtls_snprintf(filename, sizeof(filename), "%s.sig", argv[1]);

    if ((f = fopen(filename, "wb+")) == NULL) {
        mbedtls_printf(" failed\n  ! Could not create %s\n\n", argv[1]);
        goto exit;
    }

    for (i = 0; i < mbedtls_rsa_get_len(&rsa); i++) {
        mbedtls_fprintf(f, "%02X%s", buf[i],
                        (i + 1) % 16 == 0 ? "\r\n" : " ");
    }

    fclose(f);

    mbedtls_printf("\n  . Done (created \"%s\")\n\n", filename);

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    mbedtls_rsa_free(&rsa);
    mbedtls_mpi_free(&N); mbedtls_mpi_free(&P); mbedtls_mpi_free(&Q);
    mbedtls_mpi_free(&D); mbedtls_mpi_free(&E); mbedtls_mpi_free(&DP);
    mbedtls_mpi_free(&DQ); mbedtls_mpi_free(&QP);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_RSA_C && MBEDTLS_MD_CAN_SHA256 &&
          MBEDTLS_FS_IO */
