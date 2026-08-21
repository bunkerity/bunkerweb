/**
 * \file crypto_struct_pqcp.h
 *
 * \brief Context structure declarations of the PSA driver that wraps around
 *        mldsa-native.
 */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef TF_PSA_CRYPTO_PRIVATE_CRYPTO_STRUCT_PQCP_H
#define TF_PSA_CRYPTO_PRIVATE_CRYPTO_STRUCT_PQCP_H

#include "mbedtls/private_access.h"

#include <psa/crypto_driver_common.h>

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)

#if defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE)
/* This is a copy of the type mld_shake128ctx
 * in drivers/mldsa-native/mldsa/src/fips202/fips202.h,
 * which is not an installed header. */
typedef struct {
    uint64_t s[25];
    unsigned int pos;
} tf_psa_crypto_mldsa_shake256_struct_t;
typedef union {
    unsigned char bytes[sizeof(tf_psa_crypto_mldsa_shake256_struct_t)];
    tf_psa_crypto_mldsa_shake256_struct_t structure;
} tf_psa_crypto_mldsa_shake256_t;
#else
typedef struct psa_xof_operation_s tf_psa_crypto_mldsa_shake256_t;
#endif

typedef struct {
    /* Depending on the library version and compilation options, some fields
     * may be unused or repurposed. See psa_crypto_mldsa.c for actual usage
     * details. */
    uint8_t parameter_set;      /* 44, 65 or 87 */
    uint8_t hedged;             /* 0=deterministic, 1=hedged */
    uint8_t context_set;        /* boolean: has set_context been called? */
    uint8_t reserved;           /* uses space anyway, reserver for future use */
    size_t key_length;          /* size of key in bytes */
    uint8_t *key;               /* heap pointer, owned by the driver */
    tf_psa_crypto_mldsa_shake256_t shake;
} tf_psa_crypto_mldsa_operation_t;

#endif /* TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED */

#endif /* TF_PSA_CRYPTO_PRIVATE_CRYPTO_STRUCT_PQCP_H */
