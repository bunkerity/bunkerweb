/* PSA driver for ML-DSA using mldsa-native */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef TF_PSA_CRYPTO_PSA_CRYPTO_MLDSA_H
#define TF_PSA_CRYPTO_PSA_CRYPTO_MLDSA_H

#include <psa/crypto.h>

/* Define macros for key types and algorithms here in a private header,
 * rather than in a public header, because ML-DSA is not yet supported
 * through the API. In particular, the size macros in <psa/crypto_sizes.h>
 * do not yet take ML-DSA into account.
 */

/** The type of an ML-DSA key pair.
 *
 * It is represented as just the 32-byte seed.
 *
 * The `bits` attribute of the key indicates the parameter set:
 * 44, 56 or 87.
 */
#define PSA_KEY_TYPE_ML_DSA_KEY_PAIR ((psa_key_type_t) 0x7002)

/** The type of an ML-DSA public key.
 *
 * The `bits` attribute of the key indicates the parameter set:
 * 44, 56 or 87.
 */
#define PSA_KEY_TYPE_ML_DSA_PUBLIC_KEY ((psa_key_type_t) 0x6002)

/** Whether the key type is an ML-DSA key (key pair or public key). */
#define PSA_KEY_TYPE_IS_ML_DSA(type)                                    \
    ((type) == PSA_KEY_TYPE_ML_DSA_PUBLIC_KEY ||                        \
     (type) == PSA_KEY_TYPE_ML_DSA_KEY_PAIR)

/** Hedged pure ML-DSA (without pre-hashing). */
#define PSA_ALG_ML_DSA ((psa_algorithm_t) 0x06004400)

/** Deterministic pure ML-DSA (without pre-hashing). */
#define PSA_ALG_DETERMINISTIC_ML_DSA ((psa_algorithm_t) 0x06004500)

/** Whether the given algorithm is a pure ML-DSA algorithm
 * (without pre-hashing).
 */
#define PSA_ALG_IS_ML_DSA(alg)                \
    ((alg) == PSA_ALG_DETERMINISTIC_ML_DSA || \
     (alg) == PSA_ALG_ML_DSA)

#define PSA_MLDSA_SIGNATURE_SIZE(bits)          \
    ((bits) == 44 ? 2420u :                     \
     (bits) == 65 ? 3309u :                     \
     (bits) == 87 ? 4627u :                     \
     0u)
#define PSA_MLDSA_SIGNATURE_MAX_SIZE (PSA_MLDSA_SIGNATURE_SIZE(87))

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)

/** Export the public key of an ML-DSA key pair.
 *
 * \param[in] attributes        The key attributes.
 * \param[in] key_buffer        The key material. This must be a key pair
 *                              in the standard representation, i.e.
 *                              just the 32-byte seed.
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param[out] data             On success, the exported key.
 * \param data_size             The size of \p data, in bytes.
 * \param[out] data_length      On success, the length of the data written
 *                              to \p data.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_NOT_SUPPORTED
 *         The key type or size registered in \p attributes is not supported.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material is invalid.
 * \retval #PSA_ERROR_BUFFER_TOO_SMALL
 *         \p data_size is too small.
 */
psa_status_t tf_psa_crypto_mldsa_export_public_key(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    uint8_t *data, size_t data_size, size_t *data_length);

/** Sign a message using pure-ML-DSA (without pre-hashing).
 *
 * \param[in] attributes        The key attributes.
 * \param[in] key_buffer        The key material. This must be a key pair
 *                              in the standard representation, i.e.
 *                              just the 32-byte seed.
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param alg                   The algorithm:
 *                              #PSA_ALG_ML_DSA (not implemented yet) or
 *                              #PSA_ALG_DETERMINISTIC_ML_DSA.
 * \param[in] message           The message to sign.
 * \param message_length        The length of \p message, in bytes.
 * \param[out] signature        On success, the exported key.
 * \param signature_size        The size of \p signature, in bytes.
 * \param[out] signature_length On success, the length of the data written
 *                              to \p signature.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_NOT_SUPPORTED
 *         The key type or size registered in \p attributes is not supported,
 *         or the algorithm is not supported.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material is invalid, or the key type is invalid for the
 *         given algorithm.
 * \retval #PSA_ERROR_BUFFER_TOO_SMALL
 *         \p signature_size is too small.
 */
psa_status_t tf_psa_crypto_mldsa_sign_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *message, size_t message_length,
    uint8_t *signature, size_t signature_size, size_t *signature_length);

/** Verify a message using pure-ML-DSA (without pre-hashing).
 *
 * \param[in] attributes        The key attributes.
 * \param[in] key_buffer        The key material. This must be a public key
 *                              in the standard representation.
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param alg                   The algorithm:
 *                              #PSA_ALG_ML_DSA (not implemented yet) or
 *                              #PSA_ALG_DETERMINISTIC_ML_DSA.
 * \param[in] message           The message to verify.
 * \param message_length        The length of \p message, in bytes.
 * \param[in] signature         The signature to verify.
 * \param signature_length      The length of \p signature, in bytes.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_NOT_SUPPORTED
 *         The key type or size registered in \p attributes is not supported,
 *         or the algorithm is not supported.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material is invalid.
 * \retval #PSA_ERROR_INVALID_SIGNATURE
 *         The signature is not valid for this message.
 */
psa_status_t tf_psa_crypto_mldsa_verify_message(
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg,
    const uint8_t *message, size_t message_length,
    const uint8_t *signature, size_t signature_length);

/** Set up a pure-ML-DSA signature operation.
 *
 * \param operation             An operation structure. It must not
 *                              be in use.
 * \param[in] attributes        The key attributes.
 * \param[in] key_buffer        The key material. This must be a key pair
 *                              in the standard representation, i.e.
 *                              just the 32-byte seed.
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param alg                   The algorithm:
 *                              #PSA_ALG_ML_DSA (not implemented yet) or
 *                              #PSA_ALG_DETERMINISTIC_ML_DSA.
 *
 * \retval 0
 *         Success.
 * \retval #PSA_ERROR_NOT_SUPPORTED
 *         The key type or size registered in \p attributes is not supported,
 *         or the algorithm is not supported.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material is invalid, or the key type is invalid for the
 *         given algorithm.
 */
psa_status_t tf_psa_crypto_mldsa_sign_setup(
    tf_psa_crypto_mldsa_operation_t *operation,
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg);

/** Set up a pure-ML-DSA verification operation.
 *
 * \param operation             An operation structure. It must not
 *                              be in use.
 * \param[in] attributes        The key attributes.
 * \param[in] key_buffer        The key material. This must be a public key
 *                              in the standard representation.
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param alg                   The algorithm:
 *                              #PSA_ALG_ML_DSA or
 *                              #PSA_ALG_DETERMINISTIC_ML_DSA.
 *
 * \retval 0
 *         Success.
 * \retval #PSA_ERROR_NOT_SUPPORTED
 *         The key type or size registered in \p attributes is not supported,
 *         or the algorithm is not supported.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material is invalid, or the key type is invalid for the
 *         given algorithm.
 */
psa_status_t tf_psa_crypto_mldsa_verify_setup(
    tf_psa_crypto_mldsa_operation_t *operation,
    const psa_key_attributes_t *attributes,
    const uint8_t *key_buffer, size_t key_buffer_size,
    psa_algorithm_t alg);

/** Add a message chunk to a pure-ML-DSA signature or verification operation.
 *
 * \param operation             An operation structure. It must have
 *                              been set up and not finished
 *                              or aborted yet.
 * \param[in] input             The message chunk.
 * \param input_length          The length of \p input, in bytes.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_BAD_STATE
 *         The state of \p operation has been detected as inconsistent
 *         with the request. Note that this function does not guarantee
 *         that an inconsistent state is detected.
 */
psa_status_t tf_psa_crypto_mldsa_update(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *input, size_t input_length);

/** Finish a pure-ML-DSA signature operation.
 *
 * \param operation             An operation structure. It must have
 *                              been set up for signing and not finished
 *                              or aborted yet.
 * \param[in] key_buffer        The key material. This must be the same seed
 *                              passed to tf_psa_crypto_mldsa_sign_setup().
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param[out] signature        On success, the exported key.
 * \param signature_size        The size of \p signature, in bytes.
 * \param[out] signature_length On success, the length of the data written
 *                              to \p signature.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_BAD_STATE
 *         The state of \p operation has been detected as inconsistent
 *         with the request. Note that this function does not guarantee
 *         that an inconsistent state is detected.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material has been detected to be invalid or inconsistent
 *         with the key passed during setup. Note that this function does not
 *         guarantee that an inconsistent key is detected.
 * \retval #PSA_ERROR_BUFFER_TOO_SMALL
 *         \p signature_size is too small.
 */
psa_status_t tf_psa_crypto_mldsa_sign_finish(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *key_buffer, size_t key_buffer_size,
    uint8_t *signature, size_t signature_size, size_t *signature_length);

/** Finish a pure-ML-DSA verification operation.
 *
 * \param operation             An operation structure. It must have
 *                              been set up for verifying and not finished
 *                              or aborted yet.
 * \param[in] key_buffer        The key material. This must be the same
 *                              public key passed to
 *                              tf_psa_crypto_mldsa_verify_setup().
 * \param key_buffer_size       The size of \p key_buffer, in bytes.
 * \param[in] signature         The signature to verify.
 * \param signature_length      The length of \p signature, in bytes.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 * \retval #PSA_ERROR_BAD_STATE
 *         The state of \p operation has been detected as inconsistent
 *         with the request. Note that this function does not guarantee
 *         that an inconsistent state is detected.
 * \retval #PSA_ERROR_INVALID_ARGUMENT
 *         The key material has been detected to be invalid or inconsistent
 *         with the key passed during setup. Note that this function does not
 *         guarantee that an inconsistent key is detected.
 * \retval #PSA_ERROR_INVALID_SIGNATURE
 *         The signature is not valid for this message.
 */
psa_status_t tf_psa_crypto_mldsa_verify_finish(
    tf_psa_crypto_mldsa_operation_t *operation,
    const uint8_t *key_buffer, size_t key_buffer_size,
    const uint8_t *signature, size_t signature_length);

/** Abort a pure-ML-DSA signature or verification operation.
 *
 * \param operation             An operation structure. It must have
 *                              been initialized.
 *
 * \retval #PSA_SUCCESS
 *         Success.
 */
psa_status_t tf_psa_crypto_mldsa_abort(
    tf_psa_crypto_mldsa_operation_t *operation);

#endif /* TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED */

#endif /* "psa_crypto_mldsa.h" */
