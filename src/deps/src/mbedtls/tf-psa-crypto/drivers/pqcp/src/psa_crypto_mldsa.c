/* PSA driver for ML-DSA using mldsa-native */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include "tf_psa_crypto_common.h"

#if defined(MBEDTLS_PSA_CRYPTO_C) && defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)

#include <psa/crypto.h>
#include "psa_crypto_mldsa.h"
#include "wrap_mldsa_native.h"
#include <mbedtls/platform_util.h>
#include <mbedtls/platform.h>

#if defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE)
#include "../mldsa-native/mldsa/src/fips202/fips202.h"

/* The mldsa-native header defines the SHAKE context types, declares
 * the functions that work on that type, and declares macros mld_xxx.
 *
 * We need to expose the context type in our public headers since it
 * appears in multipart operation structure, but we don't want to
 * expose the function declarations. (Maybe we will in the future, but
 * at the time of writing, it would be a hassle because fips202.h
 * references many headers of mldsa-native that we don't want to
 * install.)
 *
 * Therefore we define a public type which has (at least) the same size
 * and alignment requirements as context type from mldsa-native, but
 * is a distinct type according to the C language. We call the
 * mldsa-native SHAKE functions through a wrapper that puns the
 * pointer type. We pun via a union to a byte array to make the compiler
 * understand that this must be aliasing of memory.
 *
 * In this source file, we want to call the SHAKE256 operations through
 * the same names as when using the PSA callbacks for SHAKE, i.e. the
 * mld_xxx names. So we replace the mld_xxx macros by wrappers that
 * do the necessary pointer punning.
 */

#undef mld_shake256_init
#undef mld_shake256_absorb
#undef mld_shake256_finalize
#undef mld_shake256_squeeze
#undef mld_shake256_release

static inline void mld_shake256_init(tf_psa_crypto_mldsa_shake256_t *state)
{
    MLD_NAMESPACE(shake256_init)((mld_shake256ctx *) &state->bytes);
}

static inline void mld_shake256_absorb(tf_psa_crypto_mldsa_shake256_t *state,
                                       const uint8_t *in, size_t inlen)
{
    MLD_NAMESPACE(shake256_absorb)((mld_shake256ctx *) &state->bytes,
                                   in, inlen);
}

static inline void mld_shake256_finalize(tf_psa_crypto_mldsa_shake256_t *state)
{
    MLD_NAMESPACE(shake256_finalize)((mld_shake256ctx *) &state->bytes);
}

static inline void mld_shake256_squeeze(uint8_t *out, size_t outlen,
                                        tf_psa_crypto_mldsa_shake256_t *state)
{
    MLD_NAMESPACE(shake256_squeeze)(out, outlen,
                                    (mld_shake256ctx *) &state->bytes);
}

static inline void mld_shake256_release(tf_psa_crypto_mldsa_shake256_t *state)
{
    MLD_NAMESPACE(shake256_release)((mld_shake256ctx *) &state->bytes);
}

#else /* TF_PSA_CRYPTO_PQCP_OWN_SHAKE */
#include "fips202_psa.h"
#endif

/* The size of an ML-DSA seed in bytes.
 * The PSA API uses the seed as the private key.
 * (Some other ML-DSA interfaces use the "expanded secret", which is
 * derived from the seed, as the private key.)
 */
#define SEED_SIZE 32

/* We want to expose size values in public headers, but we don't want to
 * expose the header that defines macros for these values in mldsa-native.
 * So we define our own macros in public headers, and check that the
 * values match.
 */
MBEDTLS_STATIC_ASSERT(MLDSA87_BYTES == PSA_MLDSA_SIGNATURE_SIZE(87),
                      "PSA and mldsa-native disagree on the ML-DSA-87 signature size");

/* For now, hard-coded values for MLDSA-87 */
#define TF_PSA_CRYPTO_MLDSA_EXPANDED_SECRET_MAX_SIZE MLDSA87_SECRETKEYBYTES
#define TF_PSA_CRYPTO_MLDSA_PUBLIC_KEY_MAX_SIZE MLDSA87_PUBLICKEYBYTES
#define TF_PSA_CRYPTO_MLDSA_SIGNATURE_MAX_SIZE MLDSA87_BYTES

/* Check that what the API adversises as a sufficient output buffer for
 * sign_message() is enough for the largest signature we might write. */
MBEDTLS_STATIC_ASSERT(
    TF_PSA_CRYPTO_MLDSA_SIGNATURE_MAX_SIZE <= PSA_MLDSA_SIGNATURE_MAX_SIZE,
    "PSA and mldsa-native disagree on the maximum ML-DSA signature size");

static psa_status_t pqcp_to_psa_error(int ret)
{
    if (ret == 0) {
        return PSA_SUCCESS;
    } else if (ret == MLD_ERR_OUT_OF_MEMORY) {
        return PSA_ERROR_INSUFFICIENT_MEMORY;
    } else {
        /* MLD_ERR_RNG_FAIL is intentionally not mapped: we don't install
         * mldsa-native's RNG callback (mu is computed on our side for
         * hedged ML-DSA), so it shouldn't be reachable. It would land
         * here and be reported as a generic driver failure.
         *
         * Not really hardware, but PSA_ERROR_HARDWARE_FAILURE is the
         * fallback error code for something unexpectedly going wrong
         * in a driver. */
        return PSA_ERROR_HARDWARE_FAILURE;
    }
}

static psa_status_t seed_to_public_key(
    size_t bits,
    const uint8_t *key_buffer, size_t key_buffer_size,
    uint8_t *data, size_t data_size, size_t *data_length)
{
    if (key_buffer_size != SEED_SIZE) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }

    if (bits != 87) {
        /* Other parameter sets are not supported yet. */
        return PSA_ERROR_NOT_SUPPORTED;
    }

    size_t public_key_length = MLDSA87_PUBLICKEYBYTES;
    if (data_size < public_key_length) {
        return PSA_ERROR_BUFFER_TOO_SMALL;
    }

    /* Beyond this point, we must go through the cleanup code. */
    uint8_t secret[TF_PSA_CRYPTO_MLDSA_EXPANDED_SECRET_MAX_SIZE];

    int ret = tf_psa_crypto_pqcp_mldsa87_keypair_internal(data,
                                                          secret,
                                                          key_buffer);
    if (ret != 0) {
        goto cleanup;
    }
    ret = 0;
    *data_length = public_key_length;

cleanup:
    mbedtls_platform_zeroize(secret, sizeof(secret));
    return pqcp_to_psa_error(ret);
}

psa_status_t tf_psa_crypto_mldsa_export_public_key(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    uint8_t *data, size_t data_size, size_t *data_length)
{
    *data_length = 0;           /* Safe default */

    if (psa_get_key_type(attributes) != PSA_KEY_TYPE_ML_DSA_KEY_PAIR) {
        return PSA_ERROR_NOT_SUPPORTED;
    }

    return seed_to_public_key(psa_get_key_bits(attributes),
                              key_buffer, key_buffer_size,
                              data, data_size, data_length);
}

psa_status_t tf_psa_crypto_mldsa_sign_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *message, size_t message_length,
    uint8_t *signature, size_t signature_size, size_t *signature_length)
{
    *signature_length = 0;      /* Safe default */

    if (alg != PSA_ALG_DETERMINISTIC_ML_DSA) {
        return PSA_ERROR_NOT_SUPPORTED;
    }

    if (psa_get_key_type(attributes) != PSA_KEY_TYPE_ML_DSA_KEY_PAIR) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }
    if (psa_get_key_bits(attributes) != 87) {
        /* Other parameter sets are not supported yet. */
        return PSA_ERROR_NOT_SUPPORTED;
    }
    size_t actual_signature_length = MLDSA87_BYTES;

    if (key_buffer_size != SEED_SIZE) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }

    if (signature_size < actual_signature_length) {
        return PSA_ERROR_BUFFER_TOO_SMALL;
    }

    /* Beyond this point, we must go through the cleanup code. */
    uint8_t secret[TF_PSA_CRYPTO_MLDSA_EXPANDED_SECRET_MAX_SIZE];
    uint8_t public[TF_PSA_CRYPTO_MLDSA_PUBLIC_KEY_MAX_SIZE];

    int ret = tf_psa_crypto_pqcp_mldsa87_keypair_internal(public,
                                                          secret,
                                                          key_buffer);
    if (ret != 0) {
        goto cleanup;
    }

    const uint8_t prefix[2] = { 0, 0 }; // pure ML-DSA with empty context
    const size_t prefix_length = sizeof(prefix);
    const uint8_t rnd[MLDSA_RNDBYTES] = { 0 };

    ret = tf_psa_crypto_pqcp_mldsa87_signature_internal(signature,
                                                        signature_length,
                                                        message, message_length,
                                                        prefix, prefix_length,
                                                        rnd,
                                                        secret,
                                                        0);

cleanup:
    mbedtls_platform_zeroize(secret, sizeof(secret));
    return pqcp_to_psa_error(ret);
}

psa_status_t tf_psa_crypto_mldsa_verify_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *message, size_t message_length,
    const uint8_t *signature, size_t signature_length)
{
    if (!PSA_ALG_IS_ML_DSA(alg)) {
        return PSA_ERROR_NOT_SUPPORTED;
    }

    if (psa_get_key_type(attributes) != PSA_KEY_TYPE_ML_DSA_PUBLIC_KEY) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }
    if (psa_get_key_bits(attributes) != 87) {
        /* Other parameter sets are not supported yet. */
        return PSA_ERROR_NOT_SUPPORTED;
    }
    if (key_buffer_size != MLDSA87_PUBLICKEYBYTES) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }

    if (signature_length != MLDSA87_BYTES) {
        return PSA_ERROR_INVALID_SIGNATURE;
    }

    int ret = tf_psa_crypto_pqcp_mldsa87_verify(signature, signature_length,
                                                message, message_length,
                                                NULL, 0,
                                                key_buffer);
    if (ret == 0) {
        return PSA_SUCCESS;
    } else {
        /* At the time of writing, invalid signature is the only possible
         * error condition. But this will change when we update mldsa-native
         * with support for heap allocation of intermediate values.
         */
        return PSA_ERROR_INVALID_SIGNATURE;
    }
}

static psa_status_t setup(
    tf_psa_crypto_mldsa_operation_t *operation,
    const psa_key_attributes_t *attributes,
    psa_algorithm_t alg)
{
    memset(operation, 0, sizeof(*operation));

    if (psa_get_key_bits(attributes) != 87) {
        /* Other parameter sets are not supported yet. */
        return PSA_ERROR_NOT_SUPPORTED;
    }
    operation->parameter_set = (uint8_t) psa_get_key_bits(attributes);

    switch (alg) {
        case PSA_ALG_DETERMINISTIC_ML_DSA:
            operation->hedged = 0;
            break;
        case PSA_ALG_ML_DSA:
            operation->hedged = 1;
            break;
        default:
            return PSA_ERROR_NOT_SUPPORTED;
    }

    return PSA_SUCCESS;
}

static void start_pure(tf_psa_crypto_mldsa_shake256_t *shake_ctx,
                       const uint8_t *public_key, size_t public_key_length)
{
    /* Hash the public key */
    mld_shake256_init(shake_ctx);
    mld_shake256_absorb(shake_ctx, public_key, public_key_length);
    mld_shake256_finalize(shake_ctx);
    uint8_t tr[MLDSA_CRHBYTES];
    mld_shake256_squeeze(tr, sizeof(tr), shake_ctx);
    mld_shake256_release(shake_ctx);
    mld_shake256_init(shake_ctx);
    mld_shake256_absorb(shake_ctx, tr, sizeof(tr));

    /* Hash the domain separation prefix */
    tr[0] = 0;                  /* pure ML-DSA (1 for Hash-ML-DSA) */
    tr[1] = 0;                  /* context length */
    mld_shake256_absorb(shake_ctx, tr, 2);
}

psa_status_t tf_psa_crypto_mldsa_sign_setup(
    tf_psa_crypto_mldsa_operation_t *operation,
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg)
{
    psa_status_t status = setup(operation, attributes, alg);
    if (status != PSA_SUCCESS) {
        return status;
    }

    if (operation->hedged) {
        /* not implemented yet */
        return PSA_ERROR_NOT_SUPPORTED;
    }

    if (psa_get_key_type(attributes) != PSA_KEY_TYPE_ML_DSA_KEY_PAIR) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }
    if (key_buffer_size != SEED_SIZE) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }

    /* After this point, we may allocate memory, so we must go through
     * cleanup. */

    /* The signature process needs the (hash of the) public key at the
     * beginning, and the (expanded) private key at the end (finish step).
     * The PSA representation of the key is just the seed, and the same
     * mldsa-native function calculates both the expanded private key and
     * the public key from the seed. We store the expanded private key
     * in the operation object so that the finish step doesn't need to
     * recalculate it. We put both the public key and the expanded private
     * key on the heap because they are very big (multiple kB) on the scale
     * of embedded devices.
     */
    size_t public_key_length = MLDSA87_PUBLICKEYBYTES;
    uint8_t *public_key = mbedtls_calloc(1, public_key_length);
    if (public_key == NULL) {
        status = PSA_ERROR_INSUFFICIENT_MEMORY;
        goto cleanup;
    }
    operation->key = mbedtls_calloc(1, MLDSA87_SECRETKEYBYTES);
    if (operation->key == NULL) {
        status = PSA_ERROR_INSUFFICIENT_MEMORY;
        goto cleanup;
    }
    operation->key_length = MLDSA87_SECRETKEYBYTES;

    int ret = tf_psa_crypto_pqcp_mldsa87_keypair_internal(public_key,
                                                          operation->key,
                                                          key_buffer);
    if (ret != 0) {
        status = pqcp_to_psa_error(ret);
        goto cleanup;
    }

    start_pure(&operation->shake, public_key, public_key_length);

cleanup:
    mbedtls_free(public_key);
    if (status != PSA_SUCCESS) {
        mbedtls_zeroize_and_free(operation->key, operation->key_length);
        mld_shake256_release(&operation->shake);
        mbedtls_platform_zeroize(operation, sizeof(*operation));
    }
    return status;
}

psa_status_t tf_psa_crypto_mldsa_verify_setup(
    tf_psa_crypto_mldsa_operation_t *operation,
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg)
{
    psa_status_t status = setup(operation, attributes, alg);
    if (status != PSA_SUCCESS) {
        return status;
    }

    if (psa_get_key_type(attributes) != PSA_KEY_TYPE_ML_DSA_PUBLIC_KEY) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }
    if (key_buffer_size != MLDSA87_PUBLICKEYBYTES) {
        /* Technically setup() doesn't care about the public key size, only
         * finish() will care. But it's easier for users to debug a wrong-key
         * problem if we complain as soon as the problem is noticeable. */
        return PSA_ERROR_INVALID_ARGUMENT;
    }

    start_pure(&operation->shake, key_buffer, key_buffer_size);

    return PSA_SUCCESS;
}

psa_status_t tf_psa_crypto_mldsa_update(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *input, size_t input_length)
{
    mld_shake256_absorb(&operation->shake, input, input_length);
    return PSA_SUCCESS;
}

psa_status_t tf_psa_crypto_mldsa_sign_finish(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *key_buffer, size_t key_buffer_size,
    uint8_t *signature, size_t signature_size, size_t *signature_length)
{
    *signature_length = 0;

    if (operation->parameter_set != 87) {
        return PSA_ERROR_NOT_SUPPORTED;
    }
    if (signature_size < MLDSA87_BYTES) {
        return PSA_ERROR_BUFFER_TOO_SMALL;
    }

    /* Rely on setup() having stored the expanded private key in the
     * operation structure. This is a performance/memory trade-off:
     * we could instead re-expand the private key from the seed
     * in \p key_buffer here. */
    if (operation->key_length != MLDSA87_SECRETKEYBYTES) {
        return PSA_ERROR_CORRUPTION_DETECTED;
    }
    (void) key_buffer;
    (void) key_buffer_size;

    uint8_t mu[MLDSA_CRHBYTES];
    mld_shake256_finalize(&operation->shake);
    mld_shake256_squeeze(mu, sizeof(mu), &operation->shake);
    mld_shake256_release(&operation->shake);

    uint8_t rnd[MLDSA_RNDBYTES];
    memset(rnd, 0, sizeof(rnd));

    int ret = tf_psa_crypto_pqcp_mldsa87_signature_internal(
        signature, signature_length,
        mu, sizeof(mu),
        NULL, 0, rnd,
        operation->key, 1);

    psa_status_t abort_status = tf_psa_crypto_mldsa_abort(operation);
    if (abort_status != PSA_SUCCESS) {
        return abort_status;
    }
    return pqcp_to_psa_error(ret);
}

psa_status_t tf_psa_crypto_mldsa_verify_finish(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *key_buffer, size_t key_buffer_size,
    const uint8_t *signature, size_t signature_length)
{
    if (operation->parameter_set != 87) {
        return PSA_ERROR_NOT_SUPPORTED;
    }
    if (key_buffer_size != MLDSA87_PUBLICKEYBYTES) {
        return PSA_ERROR_INVALID_ARGUMENT;
    }
    if (signature_length != MLDSA87_BYTES) {
        return PSA_ERROR_INVALID_SIGNATURE;
    }

    uint8_t mu[MLDSA_CRHBYTES];
    mld_shake256_finalize(&operation->shake);
    mld_shake256_squeeze(mu, sizeof(mu), &operation->shake);
    mld_shake256_release(&operation->shake);

    int ret = tf_psa_crypto_pqcp_mldsa87_verify_internal(
        signature, signature_length,
        mu, sizeof(mu),
        NULL, 0,
        key_buffer, 1);

    psa_status_t abort_status = tf_psa_crypto_mldsa_abort(operation);
    if (abort_status != PSA_SUCCESS) {
        return abort_status;
    }

    if (ret == MLD_ERR_FAIL) {
        return PSA_ERROR_INVALID_SIGNATURE;
    } else {
        return pqcp_to_psa_error(ret);
    }
}

psa_status_t tf_psa_crypto_mldsa_abort(
    tf_psa_crypto_mldsa_operation_t *operation)
{
    /* If operation->parameter_set is 0, we may have an operation object
     * that's only partially initialized. This shouldn't happen, since
     * the PSA crypto driver specification says that the core initialized
     * driver contexts to all-bits-zero. But avoid calling free() in that
     * case as an extra bit of robustness. Of course, if the operation
     * object is completely uninitialized, there's no way to detect that.
     */
    if (operation->parameter_set != 0) {
        mbedtls_zeroize_and_free(operation->key, operation->key_length);
        mld_shake256_release(&operation->shake);
    }
    mbedtls_platform_zeroize(operation, sizeof(*operation));
    return PSA_SUCCESS;
}

#endif /* MBEDTLS_PSA_CRYPTO_C && TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED */
