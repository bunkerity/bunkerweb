#include <stdint.h>
#include "mbedtls/x509_crl.h"
#include "common.h"

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)
{
#ifdef MBEDTLS_X509_CRL_PARSE_C
    int ret;
    mbedtls_x509_crl crl;
    unsigned char buf[4096];

    mbedtls_x509_crl_init(&crl);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    ret = mbedtls_x509_crl_parse(&crl, Data, Size);
#if !defined(MBEDTLS_X509_REMOVE_INFO)
    if (ret == 0) {
        ret = mbedtls_x509_crl_info((char *) buf, sizeof(buf) - 1, " ", &crl);
    }
#else
    ((void) ret);
    ((void) buf);
#endif /* !MBEDTLS_X509_REMOVE_INFO */

#if defined(MBEDTLS_USE_PSA_CRYPTO)
exit:
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    mbedtls_x509_crl_free(&crl);
#else
    (void) Data;
    (void) Size;
#endif

    return 0;
}
