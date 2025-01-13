#include "maxminddb_test_helper.h"

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-broken-pointers-24.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    {
        const char *ip = "1.1.1.16";
        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        MMDB_entry_data_s entry_data;
        int status = MMDB_get_value(&result.entry, &entry_data, NULL);

        cmp_ok(status,
               "==",
               MMDB_INVALID_DATA_ERROR,
               "MMDB_get_value returns MMDB_INVALID_DATA_ERROR for bad pointer "
               "in data section");

        MMDB_entry_data_list_s *entry_data_list;
        status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);

        cmp_ok(status,
               "==",
               MMDB_INVALID_DATA_ERROR,
               "MMDB_get_entry_data_list returns MMDB_INVALID_DATA_ERROR for "
               "bad pointer in data section");

        // This is not necessary as on error we should not need to free
        // anything. However test that it is safe to do so. See change in
        // 1.12.2.
        MMDB_free_entry_data_list(entry_data_list);
    }

    {
        const char *ip = "1.1.1.32";

        int gai_error, mmdb_error;
        MMDB_lookup_string(mmdb, ip, &gai_error, &mmdb_error);

        cmp_ok(mmdb_error,
               "==",
               MMDB_CORRUPT_SEARCH_TREE_ERROR,
               "MMDB_lookup_string sets mmdb_error to "
               "MMDB_CORRUPT_SEARCH_TREE_ERROR when a search tree record "
               "points outside the data section");
    }

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
