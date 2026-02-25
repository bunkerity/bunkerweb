#include "maxminddb_test_helper.h"

void test_double_close(void) {
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");

    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    free(db_file);
    cmp_ok(status, "==", MMDB_SUCCESS, "MMDB_open succeeded");

    if (status != MMDB_SUCCESS) {
        return;
    }

    /* First close should work normally */
    MMDB_close(&mmdb);

    ok(mmdb.file_content == NULL, "file_content is NULL after first close");
    ok(mmdb.data_section == NULL, "data_section is NULL after close");
    ok(mmdb.metadata_section == NULL, "metadata_section is NULL after close");
    cmp_ok(mmdb.metadata.languages.count,
           "==",
           0,
           "languages.count is 0 after close");
    cmp_ok(mmdb.metadata.description.count,
           "==",
           0,
           "description.count is 0 after close");
    cmp_ok(mmdb.file_size, "==", 0, "file_size is 0 after close");
    cmp_ok(
        mmdb.data_section_size, "==", 0, "data_section_size is 0 after close");
    cmp_ok(mmdb.metadata_section_size,
           "==",
           0,
           "metadata_section_size is 0 after close");

    /* Second close should be a safe no-op (file_content was NULLed) */
    MMDB_close(&mmdb);

    ok(1, "calling MMDB_close twice does not crash");
}

int main(void) {
    plan(NO_PLAN);
    test_double_close();
    done_testing();
}
