/** \brief mldsa-native's fips202.h interface on top of PSA driver dispatch.
 */
/*  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef TF_PSA_CRYTO_SRC_FIPS202_MBEDTLS_H
#define TF_PSA_CRYTO_SRC_FIPS202_MBEDTLS_H

#include <tf-psa-crypto/build_info.h>
#include <psa_crypto_driver_wrappers.h>

#include <stdint.h>

#if !defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE)

/* Make sure that SHAKE operation setup won't fail at runtime because
 * the algorithm is disabled. */
#if !defined(PSA_WANT_ALG_SHAKE128)
#error "PSA SHAKE128 required for MLDSA, but not enabled"
#endif
#if !defined(PSA_WANT_ALG_SHAKE256)
#error "PSA SHAKE256 required for MLDSA, but not enabled"
#endif

/* All the SHAKE callbacks return void, so there's no channel for
 * reporting a runtime failure.
 *
 * Our built-in SHAKE cannot fail (unless the requested SHAKE variant is
 * disabled at compile time, but that is detected at compile time above).
 * So we just ignore the return code from SHAKE calls.
 *
 * However, a third-party SHAKE driver could in principle fail.
 *
 * https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/744
 */

/* At the time of writing, mldsa-native expects this header to define
 * these constants, even though they aren't implementation-specific. */
#define SHAKE128_RATE 168
#define SHAKE256_RATE 136

typedef psa_xof_operation_t mld_shake128ctx;

static inline void mld_shake128_init(mld_shake128ctx *state)
{
    memset(state, 0, sizeof(*state));
    (void) psa_driver_wrapper_xof_setup(state, PSA_ALG_SHAKE128);
}

static inline void mld_shake128_absorb(mld_shake128ctx *state,
                                       const uint8_t *in, size_t inlen)
{
    (void) psa_driver_wrapper_xof_update(state, in, inlen);
}

static inline void mld_shake128_finalize(mld_shake128ctx *state)
{
    (void) state;
}

static inline void mld_shake128_squeeze(uint8_t *out, size_t outlen,
                                        mld_shake128ctx *state)
{
    (void) psa_driver_wrapper_xof_output(state, out, outlen);
}

static inline void mld_shake128_release(mld_shake128ctx *state)
{
    (void) psa_driver_wrapper_xof_abort(state);
}

typedef psa_xof_operation_t mld_shake256ctx;

static inline void mld_shake256_init(mld_shake256ctx *state)
{
    memset(state, 0, sizeof(*state));
    (void) psa_driver_wrapper_xof_setup(state, PSA_ALG_SHAKE256);
}

static inline void mld_shake256_absorb(mld_shake256ctx *state,
                                       const uint8_t *in, size_t inlen)
{
    (void) psa_driver_wrapper_xof_update(state, in, inlen);
}

static inline void mld_shake256_finalize(mld_shake256ctx *state)
{
    (void) state;
}

static inline void mld_shake256_squeeze(uint8_t *out, size_t outlen,
                                        mld_shake256ctx *state)
{
    (void) psa_driver_wrapper_xof_output(state, out, outlen);
}

static inline void mld_shake256_release(mld_shake256ctx *state)
{
    (void) psa_driver_wrapper_xof_abort(state);
}

/* mldsa-native also wants a one-shot SHAKE256 */
static inline void mld_shake256(uint8_t *out, size_t outlen,
                                const uint8_t *in, size_t inlen)
{
    mld_shake256ctx state;
    mld_shake256_init(&state);
    mld_shake256_absorb(&state, in, inlen);
    mld_shake256_finalize(&state);
    mld_shake256_squeeze(out, outlen, &state);
    mld_shake256_release(&state);
}

#endif /* !defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE) */

#endif /* TF_PSA_CRYTO_SRC_FIPS202_MBEDTLS_H */
