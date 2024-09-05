/** \file psa_crypto_stubs.c
 *
 * \brief Stub functions when MBEDTLS_PSA_CRYPTO_CLIENT is enabled but
 *        MBEDTLS_PSA_CRYPTO_C is disabled.
 */

/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include <psa/crypto.h>

#if defined(MBEDTLS_PSA_CRYPTO_CLIENT) && !defined(MBEDTLS_PSA_CRYPTO_C)

psa_status_t psa_generate_random(uint8_t *output,
                                 size_t output_size)
{
    (void) output;
    (void) output_size;

    return PSA_ERROR_COMMUNICATION_FAILURE;
}

psa_status_t psa_export_key(mbedtls_svc_key_id_t key,
                            uint8_t *data,
                            size_t data_size,
                            size_t *data_length)
{
    (void) key;
    (void) data;
    (void) data_size;
    (void) data_length;
    return PSA_ERROR_COMMUNICATION_FAILURE;
}

psa_status_t psa_export_public_key(mbedtls_svc_key_id_t key,
                                   uint8_t *data,
                                   size_t data_size,
                                   size_t *data_length)
{
    (void) key;
    (void) data;
    (void) data_size;
    (void) data_length;
    return PSA_ERROR_COMMUNICATION_FAILURE;
}

psa_status_t psa_get_key_attributes(mbedtls_svc_key_id_t key,
                                    psa_key_attributes_t *attributes)
{
    (void) key;
    (void) attributes;
    return PSA_ERROR_COMMUNICATION_FAILURE;
}

psa_status_t psa_hash_abort(psa_hash_operation_t *operation)
{
    (void) operation;
    return PSA_ERROR_COMMUNICATION_FAILURE;
}

psa_status_t psa_import_key(const psa_key_attributes_t *attributes,
                            const uint8_t *data,
                            size_t data_length,
                            mbedtls_svc_key_id_t *key)
{
    (void) attributes;
    (void) data;
    (void) data_length;
    (void) key;
    return PSA_ERROR_COMMUNICATION_FAILURE;
}

#endif /* MBEDTLS_PSA_CRYPTO_CLIENT && !MBEDTLS_PSA_CRYPTO_C */
