#include "maxminddb_test_helper.h"

void test_bad_epoch(void) {
    char *db_file = bad_database_path("libmaxminddb-uint64-max-epoch.mmdb");

    /* Verify we can at least open the DB without crashing */
    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, "opened bad-epoch MMDB");

    if (status != MMDB_SUCCESS) {
        diag("MMDB_open failed: %s", MMDB_strerror(status));
        free(db_file);
        return;
    }

    /* Run mmdblookup --verbose via system() and check it doesn't crash.
     * We redirect output to /dev/null; the return code tells us
     * whether the process survived. Try both possible paths since tests
     * may run from either the project root or the t/ directory. */
    char cmd[512];
    const char *binary = "../bin/mmdblookup";
    FILE *test_bin = fopen(binary, "r");
    if (!test_bin) {
        binary = "./bin/mmdblookup";
        test_bin = fopen(binary, "r");
    }
    if (test_bin) {
        fclose(test_bin);
    }

    skip(!test_bin, 1, "mmdblookup binary not found");
    snprintf(cmd,
             sizeof(cmd),
             "%s -f %s -i 1.2.3.4 -v > /dev/null 2>&1",
             binary,
             db_file);
    int ret = system(cmd);
    /* system() returns the exit status; a signal-killed process gives
     * a non-zero status. WIFEXITED checks for normal exit. */
    ok(WIFEXITED(ret) && WEXITSTATUS(ret) == 0,
       "mmdblookup --verbose with UINT64_MAX build_epoch does not crash");
    end_skip;

    MMDB_close(&mmdb);
    free(db_file);
}

int main(void) {
    plan(NO_PLAN);
    test_bad_epoch();
    done_testing();
}
