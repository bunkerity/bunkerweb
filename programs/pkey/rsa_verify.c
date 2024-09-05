/*
 *  RSA/SHA-256 signature verification program
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
    unsigned c;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    size_t i;
    mbedtls_rsa_context rsa;
    mbedtls_mpi N, E;
    unsigned char hash[32];
    unsigned char buf[MBEDTLS_MPI_MAX_SIZE];
    char filename[512];

    mbedtls_rsa_init(&rsa);
    mbedtls_mpi_init(&N);
    mbedtls_mpi_init(&E);

    if (argc != 2) {
        mbedtls_printf("usage: rsa_verify <filename>\n");

#if defined(_WIN32)
        mbedtls_printf("\n");
#endif

        goto exit;
    }

    mbedtls_printf("\n  . Reading public key from rsa_pub.txt");
    fflush(stdout);

    if ((f = fopen("rsa_pub.txt", "rb")) == NULL) {
        mbedtls_printf(" failed\n  ! Could not open rsa_pub.txt\n" \
                       "  ! Please run rsa_genkey first\n\n");
        goto exit;
    }

    if ((ret = mbedtls_mpi_read_file(&N, 16, f)) != 0 ||
        (ret = mbedtls_mpi_read_file(&E, 16, f)) != 0 ||
        (ret = mbedtls_rsa_import(&rsa, &N, NULL, NULL, NULL, &E) != 0)) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_read_file returned %d\n\n", ret);
        fclose(f);
        goto exit;
    }
    fclose(f);

    /*
     * Extract the RSA signature from the text file
     */
    mbedtls_snprintf(filename, sizeof(filename), "%s.sig", argv[1]);

    if ((f = fopen(filename, "rb")) == NULL) {
        mbedtls_printf("\n  ! Could not open %s\n\n", filename);
        goto exit;
    }

    i = 0;
    while (fscanf(f, "%02X", (unsigned int *) &c) > 0 &&
           i < (int) sizeof(buf)) {
        buf[i++] = (unsigned char) c;
    }

    fclose(f);

    if (i != mbedtls_rsa_get_len(&rsa)) {
        mbedtls_printf("\n  ! Invalid RSA signature format\n\n");
        goto exit;
    }

    /*
     * Compute the SHA-256 hash of the input file and
     * verify the signature
     */
    mbedtls_printf("\n  . Verifying the RSA/SHA-256 signature");
    fflush(stdout);

    if ((ret = mbedtls_md_file(
             mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
             argv[1], hash)) != 0) {
        mbedtls_printf(" failed\n  ! Could not open or read %s\n\n", argv[1]);
        goto exit;
    }

    if ((ret = mbedtls_rsa_pkcs1_verify(&rsa, MBEDTLS_MD_SHA256,
                                        32, hash, buf)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_rsa_pkcs1_verify returned -0x%0x\n\n",
                       (unsigned int) -ret);
        goto exit;
    }

    mbedtls_printf("\n  . OK (the signature is valid)\n\n");

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    mbedtls_rsa_free(&rsa);
    mbedtls_mpi_free(&N);
    mbedtls_mpi_free(&E);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_RSA_C && MBEDTLS_MD_CAN_SHA256 &&
          MBEDTLS_FS_IO */
