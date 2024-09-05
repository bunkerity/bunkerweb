/* ecp_alt.h with dummy types for MBEDTLS_ECP_ALT */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef ECP_ALT_H
#define ECP_ALT_H

typedef struct mbedtls_ecp_group {
    const mbedtls_ecp_group_id id;
    const mbedtls_mpi P;
    const mbedtls_mpi A;
    const mbedtls_mpi B;
    const mbedtls_ecp_point G;
    const mbedtls_mpi N;
    const size_t pbits;
    const size_t nbits;
}
mbedtls_ecp_group;

#endif /* ecp_alt.h */
