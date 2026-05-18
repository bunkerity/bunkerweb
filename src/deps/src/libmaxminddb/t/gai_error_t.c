#include "maxminddb_test_helper.h"

void test_mmdb_error_set_on_gai_failure(void) {
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, "mmap mode");
    free(db_file);

    if (!mmdb) {
        return;
    }

    /* Set mmdb_error to a known non-zero value to detect if it gets written */
    int gai_error = 0;
    int mmdb_error = 0xDEAD;

    /* ".." is not a valid IP address - getaddrinfo will fail */
    MMDB_lookup_string(mmdb, "..", &gai_error, &mmdb_error);

    ok(gai_error != 0, "gai_error is non-zero for invalid IP '..'");
    cmp_ok(mmdb_error,
           "==",
           MMDB_SUCCESS,
           "mmdb_error is set to MMDB_SUCCESS when gai_error is non-zero");

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    test_mmdb_error_set_on_gai_failure();
    done_testing();
}
