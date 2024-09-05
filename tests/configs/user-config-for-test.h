/* MBEDTLS_USER_CONFIG_FILE for testing.
 * Only used for a few test configurations.
 *
 * Typical usage (note multiple levels of quoting):
 *     make CFLAGS="'-DMBEDTLS_USER_CONFIG_FILE=\"../tests/configs/user-config-for-test.h\"'"
 */

/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#if defined(PSA_CRYPTO_DRIVER_TEST_ALL)
/* PSA_CRYPTO_DRIVER_TEST_ALL activates test drivers while keeping the
 * built-in implementations active. Normally setting MBEDTLS_PSA_ACCEL_xxx
 * would disable MBEDTLS_PSA_BUILTIN_xxx unless fallback is activated, but
 * here we arrange to have both active so that psa_crypto_*.c includes
 * the built-in implementations and the driver code can call the built-in
 * implementations.
 *
 * The point of this test mode is to verify that the
 * driver entry points are called when they should be in a lightweight
 * way, without requiring an actual driver. This is different from builds
 * with libtestdriver1, where we make a copy of the library source code
 * and use that as an external driver.
 */

/* Enable the use of the test driver in the library, and build the generic
 * part of the test driver. */
#define PSA_CRYPTO_DRIVER_TEST

/* With MBEDTLS_PSA_CRYPTO_CONFIG, if we set up the acceleration, the
 * built-in implementations won't be enabled. */
#if defined(MBEDTLS_PSA_CRYPTO_CONFIG)
#error \
    "PSA_CRYPTO_DRIVER_TEST_ALL sets up a nonstandard configuration that is incompatible with MBEDTLS_PSA_CRYPTO_CONFIG"
#endif

/* Use the accelerator driver for all cryptographic mechanisms for which
 * the test driver implemented. */
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_AES
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_CAMELLIA
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_ECC_PUBLIC_KEY
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_ECC_KEY_PAIR_BASIC
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_ECC_KEY_PAIR_IMPORT
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_ECC_KEY_PAIR_EXPORT
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_ECC_KEY_PAIR_GENERATE
#define MBEDTLS_PSA_ACCEL_KEY_TYPE_RSA_KEY_PAIR
#define MBEDTLS_PSA_ACCEL_ALG_CBC_NO_PADDING
#define MBEDTLS_PSA_ACCEL_ALG_CBC_PKCS7
#define MBEDTLS_PSA_ACCEL_ALG_CTR
#define MBEDTLS_PSA_ACCEL_ALG_CFB
#define MBEDTLS_PSA_ACCEL_ALG_ECDSA
#define MBEDTLS_PSA_ACCEL_ALG_DETERMINISTIC_ECDSA
#define MBEDTLS_PSA_ACCEL_ALG_MD5
#define MBEDTLS_PSA_ACCEL_ALG_OFB
#define MBEDTLS_PSA_ACCEL_ALG_RIPEMD160
#define MBEDTLS_PSA_ACCEL_ALG_RSA_PKCS1V15_SIGN
#define MBEDTLS_PSA_ACCEL_ALG_RSA_PSS
#define MBEDTLS_PSA_ACCEL_ALG_SHA_1
#define MBEDTLS_PSA_ACCEL_ALG_SHA_224
#define MBEDTLS_PSA_ACCEL_ALG_SHA_256
#define MBEDTLS_PSA_ACCEL_ALG_SHA_384
#define MBEDTLS_PSA_ACCEL_ALG_SHA_512
#define MBEDTLS_PSA_ACCEL_ALG_XTS
#define MBEDTLS_PSA_ACCEL_ALG_CMAC
#define MBEDTLS_PSA_ACCEL_ALG_HMAC

#endif  /* PSA_CRYPTO_DRIVER_TEST_ALL */



#if defined(MBEDTLS_PSA_INJECT_ENTROPY)
/* The #MBEDTLS_PSA_INJECT_ENTROPY feature requires two extra platform
 * functions, which must be configured as #MBEDTLS_PLATFORM_NV_SEED_READ_MACRO
 * and #MBEDTLS_PLATFORM_NV_SEED_WRITE_MACRO. The job of these functions
 * is to read and write from the entropy seed file, which is located
 * in the PSA ITS file whose uid is #PSA_CRYPTO_ITS_RANDOM_SEED_UID.
 * (These could have been provided as library functions, but for historical
 * reasons, they weren't, and so each integrator has to provide a copy
 * of these functions.)
 *
 * Provide implementations of these functions for testing. */
#include <stddef.h>
int mbedtls_test_inject_entropy_seed_read(unsigned char *buf, size_t len);
int mbedtls_test_inject_entropy_seed_write(unsigned char *buf, size_t len);
#define MBEDTLS_PLATFORM_NV_SEED_READ_MACRO mbedtls_test_inject_entropy_seed_read
#define MBEDTLS_PLATFORM_NV_SEED_WRITE_MACRO mbedtls_test_inject_entropy_seed_write
#endif /* MBEDTLS_PSA_INJECT_ENTROPY */
