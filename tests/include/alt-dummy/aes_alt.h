/* aes_alt.h with dummy types for MBEDTLS_AES_ALT */
/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#ifndef AES_ALT_H
#define AES_ALT_H

typedef struct mbedtls_aes_context {
    int dummy;
}
mbedtls_aes_context;

#if defined(MBEDTLS_CIPHER_MODE_XTS)

typedef struct mbedtls_aes_xts_context {
    int dummy;
} mbedtls_aes_xts_context;
#endif


#endif /* aes_alt.h */
