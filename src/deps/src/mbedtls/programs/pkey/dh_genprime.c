/*
 *  Diffie-Hellman-Merkle key exchange (prime generation)
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if !defined(MBEDTLS_BIGNUM_C) || !defined(MBEDTLS_ENTROPY_C) ||   \
    !defined(MBEDTLS_FS_IO) || !defined(MBEDTLS_CTR_DRBG_C) ||     \
    !defined(MBEDTLS_GENPRIME)
int main(void)
{
    mbedtls_printf("MBEDTLS_BIGNUM_C and/or MBEDTLS_ENTROPY_C and/or "
                   "MBEDTLS_FS_IO and/or MBEDTLS_CTR_DRBG_C and/or "
                   "MBEDTLS_GENPRIME not defined.\n");
    mbedtls_exit(0);
}
#else

#include "mbedtls/bignum.h"
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <stdio.h>
#include <string.h>

#define USAGE \
    "\n usage: dh_genprime param=<>...\n"                                   \
    "\n acceptable parameters:\n"                                           \
    "    bits=%%d           default: 2048\n"

#define DFL_BITS    2048

/*
 * Note: G = 4 is always a quadratic residue mod P,
 * so it is a generator of order Q (with P = 2*Q+1).
 */
#define GENERATOR "4"


int main(int argc, char **argv)
{
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    mbedtls_mpi G, P, Q;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    const char *pers = "dh_genprime";
    FILE *fout;
    int nbits = DFL_BITS;
    int i;
    char *p, *q;

    mbedtls_mpi_init(&G); mbedtls_mpi_init(&P); mbedtls_mpi_init(&Q);
    mbedtls_ctr_drbg_init(&ctr_drbg);
    mbedtls_entropy_init(&entropy);

    if (argc < 2) {
usage:
        mbedtls_printf(USAGE);
        goto exit;
    }

    for (i = 1; i < argc; i++) {
        p = argv[i];
        if ((q = strchr(p, '=')) == NULL) {
            goto usage;
        }
        *q++ = '\0';

        if (strcmp(p, "bits") == 0) {
            nbits = atoi(q);
            if (nbits < 0 || nbits > MBEDTLS_MPI_MAX_BITS) {
                goto usage;
            }
        } else {
            goto usage;
        }
    }

    if ((ret = mbedtls_mpi_read_string(&G, 10, GENERATOR)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_read_string returned %d\n", ret);
        goto exit;
    }

    mbedtls_printf("  ! Generating large primes may take minutes!\n");

    mbedtls_printf("\n  . Seeding the random number generator...");
    fflush(stdout);

    if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy,
                                     (const unsigned char *) pers,
                                     strlen(pers))) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ctr_drbg_seed returned %d\n", ret);
        goto exit;
    }

    mbedtls_printf(" ok\n  . Generating the modulus, please wait...");
    fflush(stdout);

    /*
     * This can take a long time...
     */
    if ((ret = mbedtls_mpi_gen_prime(&P, nbits, 1,
                                     mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_gen_prime returned %d\n\n", ret);
        goto exit;
    }

    mbedtls_printf(" ok\n  . Verifying that Q = (P-1)/2 is prime...");
    fflush(stdout);

    if ((ret = mbedtls_mpi_sub_int(&Q, &P, 1)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_sub_int returned %d\n\n", ret);
        goto exit;
    }

    if ((ret = mbedtls_mpi_div_int(&Q, NULL, &Q, 2)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_div_int returned %d\n\n", ret);
        goto exit;
    }

    if ((ret = mbedtls_mpi_is_prime_ext(&Q, 50, mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_is_prime returned %d\n\n", ret);
        goto exit;
    }

    mbedtls_printf(" ok\n  . Exporting the value in dh_prime.txt...");
    fflush(stdout);

    if ((fout = fopen("dh_prime.txt", "wb+")) == NULL) {
        mbedtls_printf(" failed\n  ! Could not create dh_prime.txt\n\n");
        goto exit;
    }

    if (((ret = mbedtls_mpi_write_file("P = ", &P, 16, fout)) != 0) ||
        ((ret = mbedtls_mpi_write_file("G = ", &G, 16, fout)) != 0)) {
        mbedtls_printf(" failed\n  ! mbedtls_mpi_write_file returned %d\n\n", ret);
        fclose(fout);
        goto exit;
    }

    mbedtls_printf(" ok\n\n");
    fclose(fout);

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    mbedtls_mpi_free(&G); mbedtls_mpi_free(&P); mbedtls_mpi_free(&Q);
    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_ENTROPY_C && MBEDTLS_FS_IO &&
          MBEDTLS_CTR_DRBG_C && MBEDTLS_GENPRIME */
