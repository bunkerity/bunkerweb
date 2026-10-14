#include "maxminddb_test_helper.h"

static void test_record_rejected(const char *fixture,
                                 const char *address,
                                 const char *desc) {
    char *path = test_database_path(fixture);
    MMDB_s *mmdb = open_ok(path, MMDB_MODE_MMAP, desc);
    free(path);
    if (!mmdb) {
        return;
    }

    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, address, fixture, desc);
    ok(result.found_entry, "%s: entry found", desc);
    if (result.found_entry) {
        MMDB_entry_data_list_s *entry_data_list = NULL;
        int const status =
            MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        cmp_ok(status,
               "==",
               MMDB_DECODER_LIMIT_ERROR,
               "%s: full decode returns MMDB_DECODER_LIMIT_ERROR",
               desc);
        ok(entry_data_list == NULL,
           "%s: error leaves the output list set to NULL",
           desc);
        MMDB_free_entry_data_list(entry_data_list);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

static void test_record_allowed(const char *fixture,
                                const char *address,
                                size_t expected_values,
                                uint64_t expected_payload,
                                const char *desc) {
    char *path = test_database_path(fixture);
    MMDB_s *mmdb = open_ok(path, MMDB_MODE_MMAP, desc);
    free(path);
    if (!mmdb) {
        return;
    }

    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, address, fixture, desc);
    ok(result.found_entry, "%s: entry found", desc);
    if (result.found_entry) {
        MMDB_entry_data_list_s *entry_data_list = NULL;
        int const status =
            MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        cmp_ok(status, "==", MMDB_SUCCESS, "%s: full decode succeeds", desc);
        ok(entry_data_list != NULL, "%s: full decode returns a list", desc);

        size_t values = 0;
        uint64_t payload = 0;
        for (MMDB_entry_data_list_s *node = entry_data_list; node;
             node = node->next) {
            values++;
            if (node->entry_data.type == MMDB_DATA_TYPE_UTF8_STRING ||
                node->entry_data.type == MMDB_DATA_TYPE_BYTES) {
                payload += node->entry_data.data_size;
            }
        }
        cmp_ok(values,
               "==",
               expected_values,
               "%s: decoded the expected number of values",
               desc);
        cmp_ok(payload,
               "==",
               expected_payload,
               "%s: decoded the expected payload bytes",
               desc);
        MMDB_free_entry_data_list(entry_data_list);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

static void test_per_call_state(void) {
    const char *fixture = "MaxMind-DB-test-payload-amplification-dos.mmdb";
    char *path = test_database_path(fixture);
    MMDB_s *mmdb = open_ok(path, MMDB_MODE_MMAP, "per-call state");
    free(path);
    if (!mmdb) {
        return;
    }

    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, "1.1.1.1", fixture, "per-call state");
    ok(result.found_entry, "per-call state: entry found");
    if (result.found_entry) {
        for (int i = 1; i <= 2; i++) {
            MMDB_entry_data_list_s *list = NULL;
            int const status = MMDB_get_entry_data_list(&result.entry, &list);
            cmp_ok(status,
                   "==",
                   MMDB_DECODER_LIMIT_ERROR,
                   "per-call: attack decode %d is rejected",
                   i);
            ok(list == NULL,
               "per-call: attack decode %d leaves a NULL list",
               i);
            MMDB_free_entry_data_list(list);
        }

        MMDB_entry_data_list_s *metadata = NULL;
        int const status =
            MMDB_get_metadata_as_entry_data_list(mmdb, &metadata);
        cmp_ok(status,
               "==",
               MMDB_SUCCESS,
               "per-call: metadata decode on the same reader succeeds");
        ok(metadata != NULL,
           "per-call: metadata decode on the same reader returns a list");
        MMDB_free_entry_data_list(metadata);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

static void test_targeted_lookup_bypasses_full_decode_limit(void) {
    const char *fixture = "MaxMind-DB-test-decoder-payload-limit-over.mmdb";
    const char *desc = "targeted oversized lookup";
    char *path = test_database_path(fixture);
    MMDB_s *mmdb = open_ok(path, MMDB_MODE_MMAP, desc);
    free(path);
    if (!mmdb) {
        return;
    }

    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, "1.1.1.1", fixture, desc);
    ok(result.found_entry, "%s: entry found", desc);
    if (result.found_entry) {
        MMDB_entry_data_s entry_data;
        int const status =
            MMDB_get_value(&result.entry, &entry_data, "0", NULL);
        cmp_ok(status,
               "==",
               MMDB_SUCCESS,
               "targeted lookup succeeds without expanding the structure");
        if (status == MMDB_SUCCESS) {
            ok(entry_data.has_data, "targeted lookup returns data");
            cmp_ok(entry_data.type,
                   "==",
                   MMDB_DATA_TYPE_BYTES,
                   "targeted lookup returns the bytes value");
            cmp_ok(entry_data.data_size,
                   "==",
                   65535,
                   "targeted lookup returns the complete bytes value");
        }
    }

    MMDB_close(mmdb);
    free(mmdb);
}

static void test_metadata_limit_error(void) {
    char *db_file =
        test_database_path("MaxMind-DB-test-metadata-payload-limit.mmdb");
    MMDB_s mmdb;
    int const status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status,
           "==",
           MMDB_INVALID_METADATA_ERROR,
           "metadata decoder limit is reported as invalid metadata by open");
    if (status == MMDB_SUCCESS) {
        MMDB_close(&mmdb);
    }
    free(db_file);
}

int main(void) {
    plan(NO_PLAN);

    is(MMDB_strerror(MMDB_DECODER_LIMIT_ERROR),
       "The decoded data structure exceeds the configured resource limits",
       "decoder limit status has a distinct error message");

    test_record_rejected("MaxMind-DB-test-pointer-decoder-dos.mmdb",
                         "1.1.1.1",
                         "IPv4 value-count fan-out");
    test_record_rejected("MaxMind-DB-test-pointer-decoder-dos-ipv6.mmdb",
                         "2001:db8::1",
                         "IPv6 value-count fan-out");
    test_record_rejected("MaxMind-DB-test-payload-amplification-dos.mmdb",
                         "1.1.1.1",
                         "bytes payload amplification");
    test_record_rejected(
        "MaxMind-DB-test-payload-amplification-dos-worst-case.mmdb",
        "1.1.1.1",
        "worst-case bytes payload amplification");
    test_record_rejected(
        "MaxMind-DB-test-payload-amplification-dos-string.mmdb",
        "1.1.1.1",
        "string payload amplification");

    test_record_allowed("MaxMind-DB-test-decoder-value-limit.mmdb",
                        "1.1.1.1",
                        65536,
                        0,
                        "exact value-count limit");
    test_record_allowed(
        "MaxMind-DB-test-decoder-value-limit-pointer-heavy.mmdb",
        "1.1.1.1",
        65535,
        0,
        "pointer-heavy record under the value-count limit");
    test_record_rejected("MaxMind-DB-test-decoder-value-limit-over.mmdb",
                         "1.1.1.1",
                         "one over the value-count limit");
    test_record_allowed("MaxMind-DB-test-decoder-payload-limit.mmdb",
                        "1.1.1.1",
                        34,
                        2097152,
                        "exact payload-byte limit");
    test_record_rejected("MaxMind-DB-test-decoder-payload-limit-over.mmdb",
                         "1.1.1.1",
                         "one over the payload-byte limit");

    test_record_allowed("GeoIP2-City-Test.mmdb",
                        "81.2.69.142",
                        120,
                        679,
                        "normal production-style record");
    test_per_call_state();
    test_targeted_lookup_bypasses_full_decode_limit();
    test_metadata_limit_error();

    done_testing();
}
