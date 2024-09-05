#include <stdint.h>
#include "mbedtls/x509_crt.h"
#include "common.h"

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)
{
#ifdef MBEDTLS_X509_CRT_PARSE_C
    int ret;
    mbedtls_x509_crt crt;
    unsigned char buf[4096];

    mbedtls_x509_crt_init(&crt);
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = psa_crypto_init();
    if (status != PSA_SUCCESS) {
        goto exit;
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    ret = mbedtls_x509_crt_parse(&crt, Data, Size);
#if !defined(MBEDTLS_X509_REMOVE_INFO)
    if (ret == 0) {
        ret = mbedtls_x509_crt_info((char *) buf, sizeof(buf) - 1, " ", &crt);
    }
#else
    ((void) ret);
    ((void) buf);
#endif /* !MBEDTLS_X509_REMOVE_INFO */

#if defined(MBEDTLS_USE_PSA_CRYPTO)
exit:
    mbedtls_psa_crypto_free();
#endif /* MBEDTLS_USE_PSA_CRYPTO */
    mbedtls_x509_crt_free(&crt);
#else
    (void) Data;
    (void) Size;
#endif

    return 0;
}
