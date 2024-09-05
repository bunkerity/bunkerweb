/*
 *  Key writing application
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if !defined(MBEDTLS_PK_PARSE_C) || \
    !defined(MBEDTLS_PK_WRITE_C) || \
    !defined(MBEDTLS_FS_IO)      || \
    !defined(MBEDTLS_ENTROPY_C)  || \
    !defined(MBEDTLS_CTR_DRBG_C) || \
    !defined(MBEDTLS_BIGNUM_C)
int main(void)
{
    mbedtls_printf("MBEDTLS_PK_PARSE_C and/or MBEDTLS_PK_WRITE_C and/or "
                   "MBEDTLS_ENTROPY_C and/or MBEDTLS_CTR_DRBG_C and/or "
                   "MBEDTLS_FS_IO and/or MBEDTLS_BIGNUM_C not defined.\n");
    mbedtls_exit(0);
}
#else

#include "mbedtls/error.h"
#include "mbedtls/pk.h"
#include "mbedtls/error.h"

#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <stdio.h>
#include <string.h>

#if defined(MBEDTLS_PEM_WRITE_C)
#define USAGE_OUT \
    "    output_file=%%s      default: keyfile.pem\n"   \
    "    output_format=pem|der default: pem\n"
#else
#define USAGE_OUT \
    "    output_file=%%s      default: keyfile.der\n"   \
    "    output_format=der     default: der\n"
#endif

#if defined(MBEDTLS_PEM_WRITE_C)
#define DFL_OUTPUT_FILENAME     "keyfile.pem"
#define DFL_OUTPUT_FORMAT       OUTPUT_FORMAT_PEM
#else
#define DFL_OUTPUT_FILENAME     "keyfile.der"
#define DFL_OUTPUT_FORMAT       OUTPUT_FORMAT_DER
#endif

#define DFL_MODE                MODE_NONE
#define DFL_FILENAME            "keyfile.key"
#define DFL_DEBUG_LEVEL         0
#define DFL_OUTPUT_MODE         OUTPUT_MODE_NONE

#define MODE_NONE               0
#define MODE_PRIVATE            1
#define MODE_PUBLIC             2

#define OUTPUT_MODE_NONE               0
#define OUTPUT_MODE_PRIVATE            1
#define OUTPUT_MODE_PUBLIC             2

#define OUTPUT_FORMAT_PEM              0
#define OUTPUT_FORMAT_DER              1

#define USAGE \
    "\n usage: key_app_writer param=<>...\n"            \
    "\n acceptable parameters:\n"                       \
    "    mode=private|public default: none\n"           \
    "    filename=%%s         default: keyfile.key\n"   \
    "    output_mode=private|public default: none\n"    \
    USAGE_OUT                                           \
    "\n"


/*
 * global options
 */
struct options {
    int mode;                   /* the mode to run the application in   */
    const char *filename;       /* filename of the key file             */
    int output_mode;            /* the output mode to use               */
    const char *output_file;    /* where to store the constructed key file  */
    int output_format;          /* the output format to use             */
} opt;

static int write_public_key(mbedtls_pk_context *key, const char *output_file)
{
    int ret;
    FILE *f;
    unsigned char output_buf[16000];
    unsigned char *c = output_buf;
    size_t len = 0;

    memset(output_buf, 0, 16000);

#if defined(MBEDTLS_PEM_WRITE_C)
    if (opt.output_format == OUTPUT_FORMAT_PEM) {
        if ((ret = mbedtls_pk_write_pubkey_pem(key, output_buf, 16000)) != 0) {
            return ret;
        }

        len = strlen((char *) output_buf);
    } else
#endif
    {
        if ((ret = mbedtls_pk_write_pubkey_der(key, output_buf, 16000)) < 0) {
            return ret;
        }

        len = ret;
        c = output_buf + sizeof(output_buf) - len;
    }

    if ((f = fopen(output_file, "w")) == NULL) {
        return -1;
    }

    if (fwrite(c, 1, len, f) != len) {
        fclose(f);
        return -1;
    }

    fclose(f);

    return 0;
}

static int write_private_key(mbedtls_pk_context *key, const char *output_file)
{
    int ret;
    FILE *f;
    unsigned char output_buf[16000];
    unsigned char *c = output_buf;
    size_t len = 0;

    memset(output_buf, 0, 16000);

#if defined(MBEDTLS_PEM_WRITE_C)
    if (opt.output_format == OUTPUT_FORMAT_PEM) {
        if ((ret = mbedtls_pk_write_key_pem(key, output_buf, 16000)) != 0) {
            return ret;
        }

        len = strlen((char *) output_buf);
    } else
#endif
    {
        if ((ret = mbedtls_pk_write_key_der(key, output_buf, 16000)) < 0) {
            return ret;
        }

        len = ret;
        c = output_buf + sizeof(output_buf) - len;
    }

    if ((f = fopen(output_file, "w")) == NULL) {
        return -1;
    }

    if (fwrite(c, 1, len, f) != len) {
        fclose(f);
        return -1;
    }

    fclose(f);

    return 0;
}

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

int main(int argc, char *argv[])
{
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
#if defined(MBEDTLS_ERROR_C)
    char buf[200];
#endif
    int i;
    char *p, *q;

    const char *pers = "pkey/key_app";
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;

    mbedtls_pk_context key;
#if defined(MBEDTLS_RSA_C)
    mbedtls_mpi N, P, Q, D, E, DP, DQ, QP;
#endif /* MBEDTLS_RSA_C */

    /*
     * Set to sane values
     */
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&ctr_drbg);

    mbedtls_pk_init(&key);
#if defined(MBEDTLS_ERROR_C)
    memset(buf, 0, sizeof(buf));
#endif

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        mbedtls_fprintf(stderr, "Failed to initialize PSA Crypto implementation: %d\n",
                        (int) status);
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */

#if defined(MBEDTLS_RSA_C)
    mbedtls_mpi_init(&N); mbedtls_mpi_init(&P); mbedtls_mpi_init(&Q);
    mbedtls_mpi_init(&D); mbedtls_mpi_init(&E); mbedtls_mpi_init(&DP);
    mbedtls_mpi_init(&DQ); mbedtls_mpi_init(&QP);
#endif /* MBEDTLS_RSA_C */

    if (argc < 2) {
usage:
        mbedtls_printf(USAGE);
        goto exit;
    }

    opt.mode                = DFL_MODE;
    opt.filename            = DFL_FILENAME;
    opt.output_mode         = DFL_OUTPUT_MODE;
    opt.output_file         = DFL_OUTPUT_FILENAME;
    opt.output_format       = DFL_OUTPUT_FORMAT;

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
        } else if (strcmp(p, "output_mode") == 0) {
            if (strcmp(q, "private") == 0) {
                opt.output_mode = OUTPUT_MODE_PRIVATE;
            } else if (strcmp(q, "public") == 0) {
                opt.output_mode = OUTPUT_MODE_PUBLIC;
            } else {
                goto usage;
            }
        } else if (strcmp(p, "output_format") == 0) {
#if defined(MBEDTLS_PEM_WRITE_C)
            if (strcmp(q, "pem") == 0) {
                opt.output_format = OUTPUT_FORMAT_PEM;
            } else
#endif
            if (strcmp(q, "der") == 0) {
                opt.output_format = OUTPUT_FORMAT_DER;
            } else {
                goto usage;
            }
        } else if (strcmp(p, "filename") == 0) {
            opt.filename = q;
        } else if (strcmp(p, "output_file") == 0) {
            opt.output_file = q;
        } else {
            goto usage;
        }
    }

    if (opt.mode == MODE_NONE && opt.output_mode != OUTPUT_MODE_NONE) {
        mbedtls_printf("\nCannot output a key without reading one.\n");
        goto exit;
    }

    if (opt.mode == MODE_PUBLIC && opt.output_mode == OUTPUT_MODE_PRIVATE) {
        mbedtls_printf("\nCannot output a private key from a public key.\n");
        goto exit;
    }

    if (opt.mode == MODE_PRIVATE) {
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
            goto exit;
        }

        ret = mbedtls_pk_parse_keyfile(&key, opt.filename, NULL,
                                       mbedtls_ctr_drbg_random, &ctr_drbg);
        if (ret != 0) {
            mbedtls_printf(" failed\n  !  mbedtls_pk_parse_keyfile returned -0x%04x",
                           (unsigned int) -ret);
            goto exit;
        }

        mbedtls_printf(" ok\n");

        /*
         * 1.2 Print the key
         */
        mbedtls_printf("  . Key information    ...\n");

#if defined(MBEDTLS_RSA_C)
        if (mbedtls_pk_get_type(&key) == MBEDTLS_PK_RSA) {
            mbedtls_rsa_context *rsa = mbedtls_pk_rsa(key);

            if ((ret = mbedtls_rsa_export(rsa, &N, &P, &Q, &D, &E)) != 0 ||
                (ret = mbedtls_rsa_export_crt(rsa, &DP, &DQ, &QP))      != 0) {
                mbedtls_printf(" failed\n  ! could not export RSA parameters\n\n");
                goto exit;
            }

            mbedtls_mpi_write_file("N:  ",  &N,  16, NULL);
            mbedtls_mpi_write_file("E:  ",  &E,  16, NULL);
            mbedtls_mpi_write_file("D:  ",  &D,  16, NULL);
            mbedtls_mpi_write_file("P:  ",  &P,  16, NULL);
            mbedtls_mpi_write_file("Q:  ",  &Q,  16, NULL);
            mbedtls_mpi_write_file("DP: ",  &DP, 16, NULL);
            mbedtls_mpi_write_file("DQ:  ", &DQ, 16, NULL);
            mbedtls_mpi_write_file("QP:  ", &QP, 16, NULL);
        } else
#endif
#if defined(MBEDTLS_ECP_C)
        if (mbedtls_pk_get_type(&key) == MBEDTLS_PK_ECKEY) {
            if (show_ecp_key(mbedtls_pk_ec(key), 1) != 0) {
                mbedtls_printf(" failed\n  ! could not export ECC parameters\n\n");
                goto exit;
            }
        } else
#endif
        mbedtls_printf("key type not supported yet\n");

    } else if (opt.mode == MODE_PUBLIC) {
        /*
         * 1.1. Load the key
         */
        mbedtls_printf("\n  . Loading the public key ...");
        fflush(stdout);

        ret = mbedtls_pk_parse_public_keyfile(&key, opt.filename);

        if (ret != 0) {
            mbedtls_printf(" failed\n  !  mbedtls_pk_parse_public_key returned -0x%04x",
                           (unsigned int) -ret);
            goto exit;
        }

        mbedtls_printf(" ok\n");

        /*
         * 1.2 Print the key
         */
        mbedtls_printf("  . Key information    ...\n");

#if defined(MBEDTLS_RSA_C)
        if (mbedtls_pk_get_type(&key) == MBEDTLS_PK_RSA) {
            mbedtls_rsa_context *rsa = mbedtls_pk_rsa(key);

            if ((ret = mbedtls_rsa_export(rsa, &N, NULL, NULL,
                                          NULL, &E)) != 0) {
                mbedtls_printf(" failed\n  ! could not export RSA parameters\n\n");
                goto exit;
            }
            mbedtls_mpi_write_file("N: ", &N, 16, NULL);
            mbedtls_mpi_write_file("E: ", &E, 16, NULL);
        } else
#endif
#if defined(MBEDTLS_ECP_C)
        if (mbedtls_pk_get_type(&key) == MBEDTLS_PK_ECKEY) {
            if (show_ecp_key(mbedtls_pk_ec(key), 0) != 0) {
                mbedtls_printf(" failed\n  ! could not export ECC parameters\n\n");
                goto exit;
            }
        } else
#endif
        mbedtls_printf("key type not supported yet\n");
    } else {
        goto usage;
    }

    if (opt.output_mode == OUTPUT_MODE_PUBLIC) {
        write_public_key(&key, opt.output_file);
    }
    if (opt.output_mode == OUTPUT_MODE_PRIVATE) {
        write_private_key(&key, opt.output_file);
    }

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    if (exit_code != MBEDTLS_EXIT_SUCCESS) {
#ifdef MBEDTLS_ERROR_C
        mbedtls_strerror(ret, buf, sizeof(buf));
        mbedtls_printf(" - %s\n", buf);
#else
        mbedtls_printf("\n");
#endif
    }

#if defined(MBEDTLS_RSA_C)
    mbedtls_mpi_free(&N); mbedtls_mpi_free(&P); mbedtls_mpi_free(&Q);
    mbedtls_mpi_free(&D); mbedtls_mpi_free(&E); mbedtls_mpi_free(&DP);
    mbedtls_mpi_free(&DQ); mbedtls_mpi_free(&QP);
#endif /* MBEDTLS_RSA_C */

    mbedtls_pk_free(&key);

    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */

    mbedtls_exit(exit_code);
}
#endif /* program viability conditions */
