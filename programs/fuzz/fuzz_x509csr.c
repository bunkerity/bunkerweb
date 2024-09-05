#include <stdint.h>
#include "mbedtls/x509_csr.h"
#include "common.h"

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)
{
#ifdef MBEDTLS_X509_CSR_PARSE_C
    int ret;
    mbedtls_x509_csr csr;
    unsigned char buf[4096];

    mbedtls_x509_csr_init(&csr);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    ret = mbedtls_x509_csr_parse(&csr, Data, Size);
#if !defined(MBEDTLS_X509_REMOVE_INFO)
    if (ret == 0) {
        ret = mbedtls_x509_csr_info((char *) buf, sizeof(buf) - 1, " ", &csr);
    }
#else
    ((void) ret);
    ((void) buf);
#endif /* !MBEDTLS_X509_REMOVE_INFO */

#if defined(MBEDTLS_USE_PSA_CRYPTO)
exit:
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    mbedtls_x509_csr_free(&csr);
#else
    (void) Data;
    (void) Size;
#endif

    return 0;
}
