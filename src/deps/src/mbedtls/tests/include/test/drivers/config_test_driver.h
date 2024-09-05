/*
 * Mbed TLS configuration for PSA test driver libraries. It includes:
 * . the minimum set of modules needed by the PSA core.
 * . the Mbed TLS configuration options that may need to be additionally
 *   enabled for the purpose of a specific test.
 * . the PSA configuration file for the Mbed TLS library and its test drivers.
 */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef MBEDTLS_CONFIG_H
#define MBEDTLS_CONFIG_H

#if defined(_MSC_VER) && !defined(_CRT_SECURE_NO_DEPRECATE)
#define _CRT_SECURE_NO_DEPRECATE 1
#endif

#define MBEDTLS_PSA_CRYPTO_C
#define MBEDTLS_PSA_CRYPTO_CONFIG

/* PSA core mandatory configuration options */
#define MBEDTLS_CIPHER_C
#define MBEDTLS_AES_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_PSA_BUILTIN_ALG_SHA_256 1
#define MBEDTLS_CTR_DRBG_C
#define MBEDTLS_ENTROPY_C
#define MBEDTLS_ENTROPY_FORCE_SHA256

/*
 * Configuration options that may need to be additionally enabled for the
 * purpose of a specific set of tests.
 */
//#define MBEDTLS_SHA1_C
//#define MBEDTLS_SHA224_C
//#define MBEDTLS_SHA384_C
//#define MBEDTLS_SHA512_C
//#define MBEDTLS_MD_C
//#define MBEDTLS_PEM_PARSE_C
//#define MBEDTLS_BASE64_C
//#define MBEDTLS_THREADING_C
//#define MBEDTLS_THREADING_PTHREAD

#endif /* MBEDTLS_CONFIG_H */
