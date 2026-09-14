#include "maxminddb_test_helper.h"

static void test_trailing_metadata_marker(void) {
    char *db_file = bad_database_path("libmaxminddb-metadata-marker-only.mmdb");
    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status,
           "==",
           MMDB_INVALID_METADATA_ERROR,
           "MMDB_open rejects a file containing only the metadata marker");

    if (status == MMDB_SUCCESS) {
        MMDB_close(&mmdb);
    }

    free(db_file);
}

int main(void) {
    plan(NO_PLAN);
    test_trailing_metadata_marker();
    done_testing();
}
