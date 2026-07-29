/** \brief Simple integration of mldsa-native from PQCP
 *
 * Define the functions declared in wrap_mldsa_native.c.
 */
/*  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include <tf-psa-crypto/build_info.h>

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED)

//#include "pqcp-config.h"
#include "wrap_mldsa_native.h"

/* The mldsa-native code comes with SHAKE (FIPS 202) implementation,
 * which it uses by default. We turn the default around and have
 * mldsa-native use our own SHAKE (via the PSA driver wrapper layer)
 * unless told otherwise.
 *
 * Mldsa-native includes a "FIPS-202-X4" interface that performs
 * four SHAKE operations which are pipelined on CPUs with enough registers.
 * When pipelined, it has a significant performance advantage.
 * On the other hand, it's an additional cost in code size if
 * PSA SHA3 or SHAKE is enabled. (The FIPS 202 interface from
 * mldsa-native does not provide SHA3, and we have not (yet?)
 * implemented a way to use it as a PSA driver.)
 */
#if !defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE)
#  define MLD_CONFIG_FIPS202_CUSTOM_HEADER "fips202_psa.h"
/* We only provide a "normal" SHAKE interface, not x4. */
#  define MLD_CONFIG_SERIAL_FIPS202_ONLY
#endif /* !defined(TF_PSA_CRYPTO_PQCP_OWN_SHAKE) */

/* Get dependency analysis to rebuild this file if fips202_psa.h changes.
 * It's included by mldsa_native.c through MLD_CONFIG_FIPS202_CUSTOM_HEADER
 * when we configure mldsa-native to use our SHAKE. */
#if 0
#include "fips202_psa.h"
#endif

/* If we include multiple levels, tell the first level to include the
 * shared stuff.
 * After including the first level, we'll tell the other levels not to
 * include the shared stuff.
 */
#define MLD_CONFIG_MULTILEVEL_WITH_SHARED
#define MLD_CONFIG_MONOBUILD_KEEP_SHARED_HEADERS

/* Include the definitions of mldsa-native functions, one parameter set
 * (44, 65 or 87) at a time. The function names have the prefix
 * MLD_CONFIG_NAMESPACE_PREFIX defined in pqcp-config.h, followed by
 * the parameter set (except for functions shared between levels), e.g.
 * tf_psa_crypto_pqcp_mldsa87_keypair_internal().
 * */

#if defined(TF_PSA_CRYPTO_PQCP_MLDSA_87_ENABLED)
#  define MLD_CONFIG_PARAMETER_SET 87
#  include "mldsa_native.c"
#  undef MLD_CONFIG_PARAMETER_SET
/* Don't include the shared code in subsequent inclusions of mldsa_native.c */
#  undef MLD_CONFIG_MULTILEVEL_WITH_SHARED
#  define MLD_CONFIG_MULTILEVEL_NO_SHARED
#endif

#endif /* TF_PSA_CRYPTO_PQCP_MLDSA_ENABLED */
