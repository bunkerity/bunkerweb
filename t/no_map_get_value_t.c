#include "maxminddb_test_helper.h"

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-string-value-entries.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const char *ip = "1.1.1.1";
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, mode_desc);

    MMDB_entry_data_s entry_data;
    int status = MMDB_get_value(&result.entry, &entry_data, NULL);

    cmp_ok(status,
           "==",
           MMDB_SUCCESS,
           "status for MMDB_get_value() is MMDB_SUCCESS");
    ok(entry_data.has_data, "found a value when varargs list is just NULL");
    cmp_ok(entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "returned entry type is utf8_string");

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
