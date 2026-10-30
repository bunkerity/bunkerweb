/*
 * Test driver for signature functions.
 * Currently supports signing and verifying precalculated hashes, using
 * only deterministic ECDSA on curves secp256r1, secp384r1 and secp521r1.
 */
/*  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include <test/helpers.h>

#if defined(PSA_CRYPTO_DRIVER_TEST)
#include "psa/crypto.h"
#include "psa_crypto_core.h"
#include "psa_crypto_ecp.h"
#include "psa_crypto_hash.h"
#include "psa_crypto_rsa.h"

#if !defined(MBEDTLS_VERSION_MAJOR) || MBEDTLS_VERSION_MAJOR >= 4
#include "mbedtls/private/ecp.h"
#else
#include "mbedtls/ecp.h"
#endif

#include "test/drivers/hash.h"
#include "test/drivers/signature.h"

#if !defined(MBEDTLS_VERSION_MAJOR) || MBEDTLS_VERSION_MAJOR >= 4
#include "mbedtls/private/ecdsa.h"
#else
#include "mbedtls/ecdsa.h"
#endif

#include "test/random.h"

#if defined(MBEDTLS_TEST_LIBTESTDRIVER1)
#include LIBTESTDRIVER1_PSA_DRIVER_INTERNAL_HEADER(psa_crypto_ecp.h)
#include LIBTESTDRIVER1_PSA_DRIVER_INTERNAL_HEADER(psa_crypto_hash.h)
#include LIBTESTDRIVER1_PSA_DRIVER_INTERNAL_HEADER(psa_crypto_rsa.h)
#endif

/* This file is part of the framework and needs to be compatible with all
 * maintained branches of Mbed TLS and TF-PSA-Crypto.
 *
 * - Until shortly before TF-PSA-Crypto 1.1.0, ML-DSA does not exist at all.
 * - In TF-PSA-Crypto 1.1.0, TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED exists, but
 *   there is no driver dispatch for it yet, so this driver doesn't need to
 *   worry about ML-DSA.
 * - Shortly after TF-PSA-Crypto 1.1.0, in
 *   https://github.com/Mbed-TLS/TF-PSA-Crypto/pull/700, we introduced
 *   driver dispatch for ML-DSA, but the macro PSA_ALG_IS_ML_DSA is not
 *   in the API yet, only in a private header. Including this private header
 *   is a pain due to how our various build scripts set up include paths, so
 *   we don't do it. Instead, define PSA_ALG_IS_ML_DSA manually: it's the
 *   only thing we need.
 * - Later we will add ML-DSA to the API, including the definition of
 *   PSA_ALG_IS_ML_DSA. After that we may also add driver dispatch testing
 *   for ML-DSA.
 */
#if !defined(PSA_ALG_IS_ML_DSA)
/* Pure ML-DSA (hedged or deterministic) */
#define PSA_ALG_IS_ML_DSA(alg)                          \
    ((alg) == 0x06004400u || (alg) == 0x06004500u)
#endif

#include <string.h>

mbedtls_test_driver_signature_hooks_t
    mbedtls_test_driver_signature_sign_hooks = MBEDTLS_TEST_DRIVER_SIGNATURE_INIT;
mbedtls_test_driver_signature_hooks_t
    mbedtls_test_driver_signature_verify_hooks = MBEDTLS_TEST_DRIVER_SIGNATURE_INIT;

static psa_status_t sign_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer,
    size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *hash,
    size_t hash_length,
    uint8_t *signature,
    size_t signature_size,
    size_t *signature_length)
{
    if (attributes->type == PSA_KEY_TYPE_RSA_KEY_PAIR) {
        if (PSA_ALG_IS_RSA_PKCS1V15_SIGN(alg) ||
            PSA_ALG_IS_RSA_PSS(alg)) {
#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
            (defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_RSA_PKCS1V15_SIGN) || \
            defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_RSA_PSS))
            return libtestdriver1_mbedtls_psa_rsa_sign_hash(
                (const libtestdriver1_psa_key_attributes_t *) attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_size, signature_length);
#elif defined(MBEDTLS_PSA_BUILTIN_ALG_RSA_PKCS1V15_SIGN) || \
            defined(MBEDTLS_PSA_BUILTIN_ALG_RSA_PSS)
            return mbedtls_psa_rsa_sign_hash(
                attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_size, signature_length);
#endif
        } else {
            return PSA_ERROR_INVALID_ARGUMENT;
        }
    } else if (PSA_KEY_TYPE_IS_ECC(attributes->type)) {
        if (PSA_ALG_IS_ECDSA(alg)) {
#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
            (defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_ECDSA) || \
            defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_DETERMINISTIC_ECDSA))
            return libtestdriver1_mbedtls_psa_ecdsa_sign_hash(
                (const libtestdriver1_psa_key_attributes_t *) attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_size, signature_length);
#elif defined(MBEDTLS_PSA_BUILTIN_ALG_ECDSA) || \
            defined(MBEDTLS_PSA_BUILTIN_ALG_DETERMINISTIC_ECDSA)
            return mbedtls_psa_ecdsa_sign_hash(
                attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_size, signature_length);
#endif
        } else {
            return PSA_ERROR_INVALID_ARGUMENT;
        }
    }

    (void) attributes;
    (void) key_buffer;
    (void) key_buffer_size;
    (void) alg;
    (void) hash;
    (void) hash_length;
    (void) signature;
    (void) signature_size;
    (void) signature_length;
    return PSA_ERROR_NOT_SUPPORTED;
}

static psa_status_t verify_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer,
    size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *hash,
    size_t hash_length,
    const uint8_t *signature,
    size_t signature_length)
{
    if (PSA_KEY_TYPE_IS_RSA(attributes->type)) {
        if (PSA_ALG_IS_RSA_PKCS1V15_SIGN(alg) ||
            PSA_ALG_IS_RSA_PSS(alg)) {
#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
            (defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_RSA_PKCS1V15_SIGN) || \
            defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_RSA_PSS))
            return libtestdriver1_mbedtls_psa_rsa_verify_hash(
                (const libtestdriver1_psa_key_attributes_t *) attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_length);
#elif defined(MBEDTLS_PSA_BUILTIN_ALG_RSA_PKCS1V15_SIGN) || \
            defined(MBEDTLS_PSA_BUILTIN_ALG_RSA_PSS)
            return mbedtls_psa_rsa_verify_hash(
                attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_length);
#endif
        } else {
            return PSA_ERROR_INVALID_ARGUMENT;
        }
    } else if (PSA_KEY_TYPE_IS_ECC(attributes->type)) {
        if (PSA_ALG_IS_ECDSA(alg)) {
#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
            (defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_ECDSA) || \
            defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_ALG_DETERMINISTIC_ECDSA))
            return libtestdriver1_mbedtls_psa_ecdsa_verify_hash(
                (const libtestdriver1_psa_key_attributes_t *) attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_length);
#elif defined(MBEDTLS_PSA_BUILTIN_ALG_ECDSA) || \
            defined(MBEDTLS_PSA_BUILTIN_ALG_DETERMINISTIC_ECDSA)
            return mbedtls_psa_ecdsa_verify_hash(
                attributes,
                key_buffer, key_buffer_size,
                alg, hash, hash_length,
                signature, signature_length);
#endif
        } else {
            return PSA_ERROR_INVALID_ARGUMENT;
        }
    }

    (void) attributes;
    (void) key_buffer;
    (void) key_buffer_size;
    (void) alg;
    (void) hash;
    (void) hash_length;
    (void) signature;
    (void) signature_length;
    return PSA_ERROR_NOT_SUPPORTED;
}

psa_status_t mbedtls_test_transparent_signature_sign_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer,
    size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *input,
    size_t input_length,
    uint8_t *signature,
    size_t signature_size,
    size_t *signature_length)
{
    psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;
    size_t hash_length;
    uint8_t hash[PSA_HASH_MAX_SIZE];

    ++mbedtls_test_driver_signature_sign_hooks.hits;

    if (mbedtls_test_driver_signature_sign_hooks.forced_status != PSA_SUCCESS) {
        return mbedtls_test_driver_signature_sign_hooks.forced_status;
    }

    if (mbedtls_test_driver_signature_sign_hooks.forced_output != NULL) {
        if (mbedtls_test_driver_signature_sign_hooks.forced_output_length > signature_size) {
            return PSA_ERROR_BUFFER_TOO_SMALL;
        }

        memcpy(signature, mbedtls_test_driver_signature_sign_hooks.forced_output,
               mbedtls_test_driver_signature_sign_hooks.forced_output_length);
        *signature_length = mbedtls_test_driver_signature_sign_hooks.forced_output_length;

        return PSA_SUCCESS;
    }

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)
    /* Pure ML-DSA is not a sign-the-hash algorithm. At the moment, this
     * function only knows how to deal with sign-the-hash algorithms.
     * So give up and let the next driver in the chain handle the algorithm.
     * For pure ML-DSA, this will be the pqcp driver, which does not have
     * a libtestdriver1 variant, meaning that we can't test "driver-only"
     * builds for pure ML-DSA, but we can have ML-DSA enabled in builds that
     * dispatch through the test driver.
     */
    if (PSA_ALG_IS_ML_DSA(alg)) {
        return PSA_ERROR_NOT_SUPPORTED;
    }
#endif

#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
    defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_HASH)
    status = libtestdriver1_mbedtls_psa_hash_compute(
        PSA_ALG_SIGN_GET_HASH(alg), input, input_length,
        hash, sizeof(hash), &hash_length);
#elif defined(MBEDTLS_PSA_BUILTIN_HASH)
    status = mbedtls_psa_hash_compute(
        PSA_ALG_SIGN_GET_HASH(alg), input, input_length,
        hash, sizeof(hash), &hash_length);
#else
    (void) input;
    (void) input_length;
    status = PSA_ERROR_NOT_SUPPORTED;
#endif
    if (status != PSA_SUCCESS) {
        return status;
    }

    return sign_hash(attributes, key_buffer, key_buffer_size,
                     alg, hash, hash_length,
                     signature, signature_size, signature_length);
}

psa_status_t mbedtls_test_opaque_signature_sign_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key,
    size_t key_length,
    psa_algorithm_t alg,
    const uint8_t *input,
    size_t input_length,
    uint8_t *signature,
    size_t signature_size,
    size_t *signature_length)
{
    (void) attributes;
    (void) key;
    (void) key_length;
    (void) alg;
    (void) input;
    (void) input_length;
    (void) signature;
    (void) signature_size;
    (void) signature_length;

    return PSA_ERROR_NOT_SUPPORTED;
}

psa_status_t mbedtls_test_transparent_signature_verify_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer,
    size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *input,
    size_t input_length,
    const uint8_t *signature,
    size_t signature_length)
{
    psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;
    size_t hash_length;
    uint8_t hash[PSA_HASH_MAX_SIZE];

    ++mbedtls_test_driver_signature_verify_hooks.hits;

    if (mbedtls_test_driver_signature_verify_hooks.forced_status != PSA_SUCCESS) {
        return mbedtls_test_driver_signature_verify_hooks.forced_status;
    }

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)
    /* Pure ML-DSA is not a sign-the-hash algorithm. At the moment, this
     * function only knows how to deal with sign-the-hash algorithms.
     * So give up and let the next driver in the chain handle the algorithm.
     * For pure ML-DSA, this will be the pqcp driver, which does not have
     * a libtestdriver1 variant, meaning that we can't test "driver-only"
     * builds for pure ML-DSA, but we can have ML-DSA enabled in builds that
     * dispatch through the test driver.
     */
    if (PSA_ALG_IS_ML_DSA(alg)) {
        return PSA_ERROR_NOT_SUPPORTED;
    }
#endif

#if defined(MBEDTLS_TEST_LIBTESTDRIVER1) && \
    defined(LIBTESTDRIVER1_MBEDTLS_PSA_BUILTIN_HASH)
    status = libtestdriver1_mbedtls_psa_hash_compute(
        PSA_ALG_SIGN_GET_HASH(alg), input, input_length,
        hash, sizeof(hash), &hash_length);
#elif defined(MBEDTLS_PSA_BUILTIN_HASH)
    status = mbedtls_psa_hash_compute(
        PSA_ALG_SIGN_GET_HASH(alg), input, input_length,
        hash, sizeof(hash), &hash_length);
#else
    (void) input;
    (void) input_length;
    status = PSA_ERROR_NOT_SUPPORTED;
#endif
    if (status != PSA_SUCCESS) {
        return status;
    }

    return verify_hash(attributes, key_buffer, key_buffer_size,
                       alg, hash, hash_length,
                       signature, signature_length);
}

psa_status_t mbedtls_test_opaque_signature_verify_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key,
    size_t key_length,
    psa_algorithm_t alg,
    const uint8_t *input,
    size_t input_length,
    const uint8_t *signature,
    size_t signature_length)
{
    (void) attributes;
    (void) key;
    (void) key_length;
    (void) alg;
    (void) input;
    (void) input_length;
    (void) signature;
    (void) signature_length;

    return PSA_ERROR_NOT_SUPPORTED;
}

psa_status_t mbedtls_test_transparent_signature_sign_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *hash, size_t hash_length,
    uint8_t *signature, size_t signature_size, size_t *signature_length)
{
    ++mbedtls_test_driver_signature_sign_hooks.hits;

    if (mbedtls_test_driver_signature_sign_hooks.forced_status != PSA_SUCCESS) {
        return mbedtls_test_driver_signature_sign_hooks.forced_status;
    }

    if (mbedtls_test_driver_signature_sign_hooks.forced_output != NULL) {
        if (mbedtls_test_driver_signature_sign_hooks.forced_output_length > signature_size) {
            return PSA_ERROR_BUFFER_TOO_SMALL;
        }
        memcpy(signature, mbedtls_test_driver_signature_sign_hooks.forced_output,
               mbedtls_test_driver_signature_sign_hooks.forced_output_length);
        *signature_length = mbedtls_test_driver_signature_sign_hooks.forced_output_length;
        return PSA_SUCCESS;
    }

    return sign_hash(attributes, key_buffer, key_buffer_size,
                     alg, hash, hash_length,
                     signature, signature_size, signature_length);
}

psa_status_t mbedtls_test_opaque_signature_sign_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key, size_t key_length,
    psa_algorithm_t alg,
    const uint8_t *hash, size_t hash_length,
    uint8_t *signature, size_t signature_size, size_t *signature_length)
{
    (void) attributes;
    (void) key;
    (void) key_length;
    (void) alg;
    (void) hash;
    (void) hash_length;
    (void) signature;
    (void) signature_size;
    (void) signature_length;

    return PSA_ERROR_NOT_SUPPORTED;
}

psa_status_t mbedtls_test_transparent_signature_verify_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *hash, size_t hash_length,
    const uint8_t *signature, size_t signature_length)
{
    ++mbedtls_test_driver_signature_verify_hooks.hits;

    if (mbedtls_test_driver_signature_verify_hooks.forced_status != PSA_SUCCESS) {
        return mbedtls_test_driver_signature_verify_hooks.forced_status;
    }

    return verify_hash(attributes, key_buffer, key_buffer_size,
                       alg, hash, hash_length,
                       signature, signature_length);
}

psa_status_t mbedtls_test_opaque_signature_verify_hash(
    const psa_key_attributes_t *attributes,
    const uint8_t *key, size_t key_length,
    psa_algorithm_t alg,
    const uint8_t *hash, size_t hash_length,
    const uint8_t *signature, size_t signature_length)
{
    (void) attributes;
    (void) key;
    (void) key_length;
    (void) alg;
    (void) hash;
    (void) hash_length;
    (void) signature;
    (void) signature_length;
    return PSA_ERROR_NOT_SUPPORTED;
}

#endif /* PSA_CRYPTO_DRIVER_TEST */
