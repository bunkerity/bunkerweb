/** \file psa_crypto_helpers.c
 *
 * \brief Helper functions to test PSA crypto functionality.
 */

/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include <test/helpers.h>
#include <test/macros.h>
#include <psa_crypto_slot_management.h>
#include <test/psa_crypto_helpers.h>

#if defined(MBEDTLS_CTR_DRBG_C)
#include <mbedtls/ctr_drbg.h>
#endif

#if defined(MBEDTLS_PSA_CRYPTO_C)

#include <psa/crypto.h>

#if defined(MBEDTLS_PSA_CRYPTO_STORAGE_C)

#include <psa_crypto_storage.h>

static mbedtls_svc_key_id_t key_ids_used_in_test[9];
static size_t num_key_ids_used;

int mbedtls_test_uses_key_id(mbedtls_svc_key_id_t key_id)
{
    size_t i;
    if (MBEDTLS_SVC_KEY_ID_GET_KEY_ID(key_id) >
        PSA_MAX_PERSISTENT_KEY_IDENTIFIER) {
        /* Don't touch key id values that designate non-key files. */
        return 1;
    }
    for (i = 0; i < num_key_ids_used; i++) {
        if (mbedtls_svc_key_id_equal(key_id, key_ids_used_in_test[i])) {
            return 1;
        }
    }
    if (num_key_ids_used == ARRAY_LENGTH(key_ids_used_in_test)) {
        return 0;
    }
    key_ids_used_in_test[num_key_ids_used] = key_id;
    ++num_key_ids_used;
    return 1;
}

void mbedtls_test_psa_purge_key_storage(void)
{
    size_t i;
    for (i = 0; i < num_key_ids_used; i++) {
        psa_destroy_persistent_key(key_ids_used_in_test[i]);
    }
    num_key_ids_used = 0;
}

void mbedtls_test_psa_purge_key_cache(void)
{
    size_t i;
    for (i = 0; i < num_key_ids_used; i++) {
        psa_purge_key(key_ids_used_in_test[i]);
    }
}

#endif /* MBEDTLS_PSA_CRYPTO_STORAGE_C */

const char *mbedtls_test_helper_is_psa_leaking(void)
{
    mbedtls_psa_stats_t stats;

    mbedtls_psa_get_stats(&stats);

    /* Some volatile slots may be used for internal purposes. Generally
     * we'll have exactly MBEDTLS_TEST_PSA_INTERNAL_KEYS at this point,
     * but in some cases we might have less, e.g. if a code path calls
     * PSA_DONE more than once, or if there has only been a partial or
     * failed initialization. */
    if (stats.volatile_slots > MBEDTLS_TEST_PSA_INTERNAL_KEYS) {
        return "A volatile slot has not been closed properly.";
    }
    if (stats.persistent_slots != 0) {
        return "A persistent slot has not been closed properly.";
    }
    if (stats.external_slots != 0) {
        return "An external slot has not been closed properly.";
    }
    if (stats.half_filled_slots != 0) {
        return "A half-filled slot has not been cleared properly.";
    }
    if (stats.locked_slots != 0) {
        return "Some slots are still marked as locked.";
    }

    return NULL;
}

#if defined(RECORD_PSA_STATUS_COVERAGE_LOG)
/** Name of the file where return statuses are logged by #RECORD_STATUS. */
#define STATUS_LOG_FILE_NAME "statuses.log"

psa_status_t mbedtls_test_record_status(psa_status_t status,
                                        const char *func,
                                        const char *file, int line,
                                        const char *expr)
{
    /* We open the log file on first use.
     * We never close the log file, so the record_status feature is not
     * compatible with resource leak detectors such as Asan.
     */
    static FILE *log;
    if (log == NULL) {
        log = fopen(STATUS_LOG_FILE_NAME, "a");
    }
    fprintf(log, "%d:%s:%s:%d:%s\n", (int) status, func, file, line, expr);
    return status;
}
#endif /* defined(RECORD_PSA_STATUS_COVERAGE_LOG) */

psa_key_usage_t mbedtls_test_update_key_usage_flags(psa_key_usage_t usage_flags)
{
    psa_key_usage_t updated_usage = usage_flags;

    if (usage_flags & PSA_KEY_USAGE_SIGN_HASH) {
        updated_usage |= PSA_KEY_USAGE_SIGN_MESSAGE;
    }

    if (usage_flags & PSA_KEY_USAGE_VERIFY_HASH) {
        updated_usage |= PSA_KEY_USAGE_VERIFY_MESSAGE;
    }

    return updated_usage;
}

int mbedtls_test_fail_if_psa_leaking(int line_no, const char *filename)
{
    const char *msg = mbedtls_test_helper_is_psa_leaking();
    if (msg == NULL) {
        return 0;
    } else {
        mbedtls_test_fail(msg, line_no, filename);
        return 1;
    }
}

uint64_t mbedtls_test_parse_binary_string(data_t *bin_string)
{
    uint64_t result = 0;
    TEST_LE_U(bin_string->len, 8);
    for (size_t i = 0; i < bin_string->len; i++) {
        result = result << 8 | bin_string->x[i];
    }
exit:
    return result; /* returns 0 if len > 8 */
}

#if defined(MBEDTLS_PSA_INJECT_ENTROPY)

#include <mbedtls/entropy.h>
#include <psa_crypto_its.h>

int mbedtls_test_inject_entropy_seed_read(unsigned char *buf, size_t len)
{
    size_t actual_len = 0;
    psa_status_t status = psa_its_get(PSA_CRYPTO_ITS_RANDOM_SEED_UID,
                                      0, len, buf, &actual_len);
    if (status != 0) {
        return MBEDTLS_ERR_ENTROPY_FILE_IO_ERROR;
    }
    if (actual_len != len) {
        return MBEDTLS_ERR_ENTROPY_SOURCE_FAILED;
    }
    return 0;
}

int mbedtls_test_inject_entropy_seed_write(unsigned char *buf, size_t len)
{
    psa_status_t status = psa_its_set(PSA_CRYPTO_ITS_RANDOM_SEED_UID,
                                      len, buf, 0);
    if (status != 0) {
        return MBEDTLS_ERR_ENTROPY_FILE_IO_ERROR;
    }
    return 0;
}

int mbedtls_test_inject_entropy_restore(void)
{
    unsigned char buf[MBEDTLS_ENTROPY_BLOCK_SIZE];
    for (size_t i = 0; i < sizeof(buf); i++) {
        buf[i] = (unsigned char) i;
    }
    psa_status_t status = mbedtls_psa_inject_entropy(buf, sizeof(buf));
    /* It's ok if the file was just created, or if it already exists. */
    if (status != PSA_SUCCESS && status != PSA_ERROR_NOT_PERMITTED) {
        return status;
    }
    return PSA_SUCCESS;
}

#endif /* MBEDTLS_PSA_INJECT_ENTROPY */

#endif /* MBEDTLS_PSA_CRYPTO_C */
