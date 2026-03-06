#include "maxminddb_test_helper.h"

static void test_db_opens_and_lookup_succeeds(const char *filename,
                                              const char *open_msg) {
    char *db_file = bad_database_path(filename);

    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, open_msg);

    if (status != MMDB_SUCCESS) {
        diag("MMDB_open failed: %s", MMDB_strerror(status));
        free(db_file);
        return;
    }

    int gai_error, mmdb_error;
    MMDB_lookup_string(&mmdb, "1.2.3.4", &gai_error, &mmdb_error);
    cmp_ok(gai_error, "==", 0, "getaddrinfo succeeded");
    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "lookup succeeded");

    MMDB_close(&mmdb);
    free(db_file);
}

void test_empty_map_last_in_metadata(void) {
    test_db_opens_and_lookup_succeeds(
        "libmaxminddb-empty-map-last-in-metadata.mmdb",
        "opened MMDB with empty map at end of metadata");
}

void test_empty_array_last_in_metadata(void) {
    test_db_opens_and_lookup_succeeds(
        "libmaxminddb-empty-array-last-in-metadata.mmdb",
        "opened MMDB with empty array at end of metadata");
}

int main(void) {
    plan(NO_PLAN);
    test_empty_map_last_in_metadata();
    test_empty_array_last_in_metadata();
    done_testing();
}
