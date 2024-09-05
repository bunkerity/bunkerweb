/*
 *  Example ECDHE with Curve25519 program
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "mbedtls/build_info.h"

#include "mbedtls/platform.h"

#if !defined(MBEDTLS_ECDH_C) || \
    !defined(MBEDTLS_ECP_DP_CURVE25519_ENABLED) || \
    !defined(MBEDTLS_ENTROPY_C) || !defined(MBEDTLS_CTR_DRBG_C)
int main(void)
{
    mbedtls_printf("MBEDTLS_ECDH_C and/or "
                   "MBEDTLS_ECP_DP_CURVE25519_ENABLED and/or "
                   "MBEDTLS_ENTROPY_C and/or MBEDTLS_CTR_DRBG_C "
                   "not defined\n");
    mbedtls_exit(0);
}
#else

#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/ecdh.h"

#include <string.h>


int main(int argc, char *argv[])
{
    int ret = 1;
    int exit_code = MBEDTLS_EXIT_FAILURE;
    mbedtls_ecdh_context ctx_cli, ctx_srv;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    unsigned char cli_to_srv[36], srv_to_cli[33];
    const char pers[] = "ecdh";

    size_t srv_olen;
    size_t cli_olen;
    unsigned char secret_cli[32] = { 0 };
    unsigned char secret_srv[32] = { 0 };
    const unsigned char *p_cli_to_srv = cli_to_srv;

    ((void) argc);
    ((void) argv);

    mbedtls_ecdh_init(&ctx_cli);
    mbedtls_ecdh_init(&ctx_srv);
    mbedtls_ctr_drbg_init(&ctr_drbg);

    /*
     * Initialize random number generation
     */
    mbedtls_printf("  . Seed the random number generator...");
    fflush(stdout);

    mbedtls_entropy_init(&entropy);
    if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func,
                                     &entropy,
                                     (const unsigned char *) pers,
                                     sizeof(pers))) != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ctr_drbg_seed returned %d\n",
                       ret);
        goto exit;
    }

    mbedtls_printf(" ok\n");

    /*
     * Client: initialize context and generate keypair
     */
    mbedtls_printf("  . Set up client context, generate EC key pair...");
    fflush(stdout);

    ret = mbedtls_ecdh_setup(&ctx_cli, MBEDTLS_ECP_DP_CURVE25519);
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_setup returned %d\n", ret);
        goto exit;
    }

    ret = mbedtls_ecdh_make_params(&ctx_cli, &cli_olen, cli_to_srv,
                                   sizeof(cli_to_srv),
                                   mbedtls_ctr_drbg_random, &ctr_drbg);
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_make_params returned %d\n",
                       ret);
        goto exit;
    }

    mbedtls_printf(" ok\n");

    /*
     * Server: initialize context and generate keypair
     */
    mbedtls_printf("  . Server: read params, generate public key...");
    fflush(stdout);

    ret = mbedtls_ecdh_read_params(&ctx_srv, &p_cli_to_srv,
                                   p_cli_to_srv + sizeof(cli_to_srv));
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_read_params returned %d\n",
                       ret);
        goto exit;
    }

    ret = mbedtls_ecdh_make_public(&ctx_srv, &srv_olen, srv_to_cli,
                                   sizeof(srv_to_cli),
                                   mbedtls_ctr_drbg_random, &ctr_drbg);
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_make_public returned %d\n",
                       ret);
        goto exit;
    }

    mbedtls_printf(" ok\n");

    /*
     * Client: read public key
     */
    mbedtls_printf("  . Client: read public key...");
    fflush(stdout);

    ret = mbedtls_ecdh_read_public(&ctx_cli, srv_to_cli,
                                   sizeof(srv_to_cli));
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_read_public returned %d\n",
                       ret);
        goto exit;
    }

    mbedtls_printf(" ok\n");

    /*
     * Calculate secrets
     */
    mbedtls_printf("  . Calculate secrets...");
    fflush(stdout);

    ret = mbedtls_ecdh_calc_secret(&ctx_cli, &cli_olen, secret_cli,
                                   sizeof(secret_cli),
                                   mbedtls_ctr_drbg_random, &ctr_drbg);
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_calc_secret returned %d\n",
                       ret);
        goto exit;
    }

    ret = mbedtls_ecdh_calc_secret(&ctx_srv, &srv_olen, secret_srv,
                                   sizeof(secret_srv),
                                   mbedtls_ctr_drbg_random, &ctr_drbg);
    if (ret != 0) {
        mbedtls_printf(" failed\n  ! mbedtls_ecdh_calc_secret returned %d\n",
                       ret);
        goto exit;
    }

    mbedtls_printf(" ok\n");

    /*
     * Verification: are the computed secrets equal?
     */
    mbedtls_printf("  . Check if both calculated secrets are equal...");
    fflush(stdout);

    ret = memcmp(secret_srv, secret_cli, srv_olen);
    if (ret != 0 || (cli_olen != srv_olen)) {
        mbedtls_printf(" failed\n  ! Shared secrets not equal.\n");
        goto exit;
    }

    mbedtls_printf(" ok\n");

    exit_code = MBEDTLS_EXIT_SUCCESS;

exit:

    mbedtls_ecdh_free(&ctx_srv);
    mbedtls_ecdh_free(&ctx_cli);
    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);

    mbedtls_exit(exit_code);
}
#endif /* MBEDTLS_ECDH_C && MBEDTLS_ECP_DP_CURVE25519_ENABLED &&
          MBEDTLS_ENTROPY_C && MBEDTLS_CTR_DRBG_C */
