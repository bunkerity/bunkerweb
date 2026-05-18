#include "maxminddb_test_helper.h"

void test_deep_nesting_rejected(void) {
    char *db_file = bad_database_path("libmaxminddb-deep-nesting.mmdb");

    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, "opened deeply nested MMDB");

    if (status != MMDB_SUCCESS) {
        diag("MMDB_open failed: %s", MMDB_strerror(status));
        free(db_file);
        return;
    }

    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(&mmdb, "1.2.3.4", &gai_error, &mmdb_error);

    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "lookup succeeded");
    ok(result.found_entry, "entry found");

    if (result.found_entry) {
        /* Looking up non-existent key "z" forces skip_map_or_array to
         * recurse through all 600 nesting levels. With the depth limit,
         * this should return MMDB_INVALID_DATA_ERROR instead of crashing. */
        MMDB_entry_data_s entry_data;
        const char *lookup_path[] = {"z", NULL};
        status = MMDB_aget_value(&result.entry, &entry_data, lookup_path);
        cmp_ok(status,
               "==",
               MMDB_INVALID_DATA_ERROR,
               "MMDB_aget_value returns MMDB_INVALID_DATA_ERROR for "
               "deeply nested data exceeding max depth");
    }

    MMDB_close(&mmdb);
    free(db_file);
}

void test_valid_nesting_allowed(void) {
    char *db_file = test_database_path("MaxMind-DB-test-nested.mmdb");

    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, "opened moderately nested MMDB");

    if (status != MMDB_SUCCESS) {
        diag("MMDB_open failed: %s", MMDB_strerror(status));
        free(db_file);
        return;
    }

    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(&mmdb, "1.1.1.1", &gai_error, &mmdb_error);

    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "lookup succeeded");
    ok(result.found_entry, "entry found");

    if (result.found_entry) {
        MMDB_entry_data_list_s *entry_data_list = NULL;
        status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        cmp_ok(status,
               "==",
               MMDB_SUCCESS,
               "MMDB_get_entry_data_list succeeds for "
               "valid nesting depth");
        MMDB_free_entry_data_list(entry_data_list);
    }

    MMDB_close(&mmdb);
    free(db_file);
}

void test_deep_array_nesting_rejected(void) {
    char *db_file = bad_database_path("libmaxminddb-deep-array-nesting.mmdb");

    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, "opened deeply nested array MMDB");

    if (status != MMDB_SUCCESS) {
        diag("MMDB_open failed: %s", MMDB_strerror(status));
        free(db_file);
        return;
    }

    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(&mmdb, "1.2.3.4", &gai_error, &mmdb_error);

    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "lookup succeeded");
    ok(result.found_entry, "entry found");

    if (result.found_entry) {
        MMDB_entry_data_list_s *entry_data_list = NULL;
        status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        cmp_ok(status,
               "==",
               MMDB_INVALID_DATA_ERROR,
               "MMDB_get_entry_data_list returns MMDB_INVALID_DATA_ERROR "
               "for deeply nested arrays exceeding max depth");
        MMDB_free_entry_data_list(entry_data_list);
    }

    MMDB_close(&mmdb);
    free(db_file);
}

int main(void) {
    plan(NO_PLAN);
    test_deep_nesting_rejected();
    test_deep_array_nesting_rejected();
    test_valid_nesting_allowed();
    done_testing();
}
