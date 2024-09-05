/*
 *  Key reading application
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if defined(MBEDTLS_BIGNUM_C) && \
    defined(MBEDTLS_PK_PARSE_C) && defined(MBEDTLS_FS_IO) && \
    defined(MBEDTLS_ENTROPY_C) && defined(MBEDTLS_CTR_DRBG_C)
#include "mbedtls/error.h"
#include "mbedtls/rsa.h"
#include "mbedtls/pk.h"
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <string.h>
#endif

#define MODE_NONE               0
#define MODE_PRIVATE            1
#define MODE_PUBLIC             2

#define DFL_MODE                MODE_NONE
#define DFL_FILENAME            "keyfile.key"
#define DFL_PASSWORD            ""
#define DFL_PASSWORD_FILE       ""
#define DFL_DEBUG_LEVEL         0

#define USAGE \
    "\n usage: key_app param=<>...\n"                   \
    "\n acceptable parameters:\n"                       \
    "    mode=private|public default: none\n"           \
    "    filename=%%s         default: keyfile.key\n"   \
    "    password=%%s         default: \"\"\n"          \
    "    password_file=%%s    default: \"\"\n"          \
    "\n"

#if !defined(MBEDTLS_BIGNUM_C) ||                                  \
    !defined(MBEDTLS_PK_PARSE_C) || !defined(MBEDTLS_FS_IO) || \
    !defined(MBEDTLS_ENTROPY_C) || !defined(MBEDTLS_CTR_DRBG_C)
int main(void)
{
    mbedtls_printf("MBEDTLS_BIGNUM_C and/or "
                   "MBEDTLS_PK_PARSE_C and/or MBEDTLS_FS_IO and/or "
                   "MBEDTLS_ENTROPY_C and/or MBEDTLS_CTR_DRBG_C not defined.\n");
    mbedtls_exit(0);
}
#else


#if defined(MBEDTLS_ECP_C)
static int show_ecp_key(const mbedtls_ecp_keypair *ecp, int has_private)
{
    int ret = 0;

    const mbedtls_ecp_curve_info *curve_info =
        mbedtls_ecp_curve_info_from_grp_id(
            mbedtls_ecp_keypair_get_group_id(ecp));
    mbedtls_printf("curve: %s\n", curve_info->name);

    mbedtls_ecp_group grp;
    mbedtls_ecp_group_init(&grp);
    mbedtls_mpi D;
    mbedtls_mpi_init(&D);
    mbedtls_ecp_point pt;
    mbedtls_ecp_point_init(&pt);
    mbedtls_mpi X, Y;
    mbedtls_mpi_init(&X); mbedtls_mpi_init(&Y);

    MBEDTLS_MPI_CHK(mbedtls_ecp_export(ecp, &grp,
                                       (has_private ? &D : NULL),
                                       &pt));

    unsigned char point_bin[MBEDTLS_ECP_MAX_PT_LEN];
    size_t len = 0;
    MBEDTLS_MPI_CHK(mbedtls_ecp_point_write_binary(
                        &grp, &pt, MBEDTLS_ECP_PF_UNCOMPRESSED,
                        &len, point_bin, sizeof(point_bin)));
    switch (mbedtls_ecp_get_type(&grp)) {
        case MBEDTLS_ECP_TYPE_SHORT_WEIERSTRASS:
            if ((len & 1) == 0 || point_bin[0] != 0x04) {
                /* Point in an unxepected format. This shouldn't happen. */
                ret = -1;
                goto cleanup;
            }
            MBEDTLS_MPI_CHK(
                mbedtls_mpi_read_binary(&X, point_bin + 1, len / 2));
            MBEDTLS_MPI_CHK(
                mbedtls_mpi_read_binary(&Y, point_bin + 1 + len / 2, len / 2));
            mbedtls_mpi_write_file("X_Q:   ", &X, 16, NULL);
            mbedtls_mpi_write_file("Y_Q:   ", &Y, 16, NULL);
            break;
        case MBEDTLS_ECP_TYPE_MONTGOMERY:
            MBEDTLS_MPI_CHK(mbedtls_mpi_read_binary(&X, point_bin, len));
            mbedtls_mpi_write_file("X_Q:   ", &X, 16, NULL);
            break;
        default:
            mbedtls_printf(
                "This program does not yet support listing coordinates for this curve type.\n");
            break;
    }

    if (has_private) {
        mbedtls_mpi_write_file("D:     ", &D, 16, NULL);
    }

cleanup:
    mbedtls_ecp_group_free(&grp);
    mbedtls_mpi_free(&D);
    mbedtls_ecp_point_free(&pt);
    mbedtls_mpi_free(&X); mbedtls_mpi_free(&Y);
    return ret;
}
#endif

/*
 * global options
 */
struct options {
    int mode;                   /* the mode to run the application in   */
    const char *filename;       /* filename of the key file             */
    const char *password;       /* password for the private key         */
    const char *password_file;  /* password_file for the private key    */
} opt;

int main(int argc, char *argv[])
{
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    char buf[1024];
    int i;
    char *p, *q;

    const char *pers = "pkey/key_app";
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;

    mbedtls_pk_context pk;
    mbedtls_mpi N, P, Q, D, E, DP, DQ, QP;

    /*
     * Set to sane values
     */
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&ctr_drbg);

    mbedtls_pk_init(&pk);
    memset(buf, 0, sizeof(buf));

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        mbedtls_fprintf(stderr, "Failed to initialize PSA Crypto implementation: %d\n",
                        (int) status);
        goto cleanup;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */

    mbedtls_mpi_init(&N); mbedtls_mpi_init(&P); mbedtls_mpi_init(&Q);
    mbedtls_mpi_init(&D); mbedtls_mpi_init(&E); mbedtls_mpi_init(&DP);
    mbedtls_mpi_init(&DQ); mbedtls_mpi_init(&QP);

    if (argc < 2) {
usage:
        mbedtls_printf(USAGE);
        goto cleanup;
    }

    opt.mode                = DFL_MODE;
    opt.filename            = DFL_FILENAME;
    opt.password            = DFL_PASSWORD;
    opt.password_file       = DFL_PASSWORD_FILE;

    for (i = 1; i < argc; i++) {
        p = argv[i];
        if ((q = strchr(p, '=')) == NULL) {
            goto usage;
        }
        *q++ = '\0';

        if (strcmp(p, "mode") == 0) {
            if (strcmp(q, "private") == 0) {
                opt.mode = MODE_PRIVATE;
            } else if (strcmp(q, "public") == 0) {
                opt.mode = MODE_PUBLIC;
            } else {
                goto usage;
            }
        } else if (strcmp(p, "filename") == 0) {
            opt.filename = q;
        } else if (strcmp(p, "password") == 0) {
            opt.password = q;
        } else if (strcmp(p, "password_file") == 0) {
            opt.password_file = q;
        } else {
            goto usage;
        }
    }

    if (opt.mode == MODE_PRIVATE) {
        if (strlen(opt.password) && strlen(opt.password_file)) {
            mbedtls_printf("Error: cannot have both password and password_file\n");
            goto usage;
        }

        if (strlen(opt.password_file)) {
            FILE *f;

            mbedtls_printf("\n  . Loading the password file ...");
            if ((f = fopen(opt.password_file, "rb")) == NULL) {
                mbedtls_printf(" failed\n  !  fopen returned NULL\n");
                goto cleanup;
            }
            if (fgets(buf, sizeof(buf), f) == NULL) {
                fclose(f);
                mbedtls_printf("Error: fgets() failed to retrieve password\n");
                goto cleanup;
            }
            fclose(f);

            i = (int) strlen(buf);
            if (buf[i - 1] == '\n') {
                buf[i - 1] = '\0';
            }
            if (buf[i - 2] == '\r') {
                buf[i - 2] = '\0';
            }
            opt.password = buf;
        }

        /*
         * 1.1. Load the key
         */
        mbedtls_printf("\n  . Loading the private key ...");
        fflush(stdout);

        if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy,
                                         (const unsigned char *) pers,
                                         strlen(pers))) != 0) {
            mbedtls_printf(" failed\n  !  mbedtls_ctr_drbg_seed returned -0x%04x\n",
                           (unsigned int) -ret);
            goto cleanup;
        }

        ret = mbedtls_pk_parse_keyfile(&pk, opt.filename, opt.password,
                                       mbedtls_ctr_drbg_random, &ctr_drbg);

        if (ret != 0) {
            mbedtls_printf(" failed\n  !  mbedtls_pk_parse_keyfile returned -0x%04x\n",
                           (unsigned int) -ret);
            goto cleanup;
        }

        mbedtls_printf(" ok\n");

        /*
         * 1.2 Print the key
         */
        mbedtls_printf("  . Key information    ...\n");
#if defined(MBEDTLS_RSA_C)
        if (mbedtls_pk_get_type(&pk) == MBEDTLS_PK_RSA) {
            mbedtls_rsa_context *rsa = mbedtls_pk_rsa(pk);

            if ((ret = mbedtls_rsa_export(rsa, &N, &P, &Q, &D, &E)) != 0 ||
                (ret = mbedtls_rsa_export_crt(rsa, &DP, &DQ, &QP))      != 0) {
                mbedtls_printf(" failed\n  ! could not export RSA parameters\n\n");
                goto cleanup;
            }

            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("N:  ", &N, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("E:  ", &E, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("D:  ", &D, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("P:  ", &P, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("Q:  ", &Q, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("DP: ", &DP, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("DQ:  ", &DQ, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("QP:  ", &QP, 16, NULL));
        } else
#endif
#if defined(MBEDTLS_ECP_C)
        if (mbedtls_pk_get_type(&pk) == MBEDTLS_PK_ECKEY) {
            if (show_ecp_key(mbedtls_pk_ec(pk), 1) != 0) {
                mbedtls_printf(" failed\n  ! could not export ECC parameters\n\n");
                goto cleanup;
            }
        } else
#endif
        {
            mbedtls_printf("Do not know how to print key information for this type\n");
            goto cleanup;
        }
    } else if (opt.mode == MODE_PUBLIC) {
        /*
         * 1.1. Load the key
         */
        mbedtls_printf("\n  . Loading the public key ...");
        fflush(stdout);

        ret = mbedtls_pk_parse_public_keyfile(&pk, opt.filename);

        if (ret != 0) {
            mbedtls_printf(" failed\n  !  mbedtls_pk_parse_public_keyfile returned -0x%04x\n",
                           (unsigned int) -ret);
            goto cleanup;
        }

        mbedtls_printf(" ok\n");

        mbedtls_printf("  . Key information    ...\n");
#if defined(MBEDTLS_RSA_C)
        if (mbedtls_pk_get_type(&pk) == MBEDTLS_PK_RSA) {
            mbedtls_rsa_context *rsa = mbedtls_pk_rsa(pk);

            if ((ret = mbedtls_rsa_export(rsa, &N, NULL, NULL,
                                          NULL, &E)) != 0) {
                mbedtls_printf(" failed\n  ! could not export RSA parameters\n\n");
                goto cleanup;
            }
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("N:  ", &N, 16, NULL));
            MBEDTLS_MPI_CHK(mbedtls_mpi_write_file("E:  ", &E, 16, NULL));
        } else
#endif
#if defined(MBEDTLS_ECP_C)
        if (mbedtls_pk_get_type(&pk) == MBEDTLS_PK_ECKEY) {
            if (show_ecp_key(mbedtls_pk_ec(pk), 0) != 0) {
                mbedtls_printf(" failed\n  ! could not export ECC parameters\n\n");
                goto cleanup;
            }
        } else
#endif
        {
            mbedtls_printf("Do not know how to print key information for this type\n");
            goto cleanup;
        }
    } else {
        goto usage;
    }

    exit_code = MBEDTLS_EXIT_SUCCESS;

cleanup:

#if defined(MBEDTLS_ERROR_C)
    if (exit_code != MBEDTLS_EXIT_SUCCESS) {
        mbedtls_strerror(ret, buf, sizeof(buf));
        mbedtls_printf("  !  Last error was: %s\n", buf);
    }
#endif

    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);
    mbedtls_pk_free(&pk);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    mbedtls_mpi_free(&N); mbedtls_mpi_free(&P); mbedtls_mpi_free(&Q);
    mbedtls_mpi_free(&D); mbedtls_mpi_free(&E); mbedtls_mpi_free(&DP);
    mbedtls_mpi_free(&DQ); mbedtls_mpi_free(&QP);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_BIGNUM_C && MBEDTLS_PK_PARSE_C && MBEDTLS_FS_IO &&
          MBEDTLS_ENTROPY_C && MBEDTLS_CTR_DRBG_C */
