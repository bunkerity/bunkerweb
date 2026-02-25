#include "maxminddb_test_helper.h"
#include <limits.h>

void test_negative_indent(void) {
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, "mmap mode");
    free(db_file);

    if (!mmdb) {
        return;
    }

    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(mmdb, "1.1.1.1", &gai_error, &mmdb_error);
    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "lookup succeeded");

    if (result.found_entry) {
        MMDB_entry_data_list_s *entry_data_list = NULL;
        int status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        cmp_ok(status, "==", MMDB_SUCCESS, "get_entry_data_list succeeded");

        if (MMDB_SUCCESS == status && entry_data_list) {
            FILE *devnull = fopen("/dev/null", "w");
            if (!devnull) {
                BAIL_OUT("could not open /dev/null");
            }

            /* Negative indent should not crash — it should be clamped to 0 */
            status = MMDB_dump_entry_data_list(devnull, entry_data_list, -1);
            cmp_ok(status,
                   "==",
                   MMDB_SUCCESS,
                   "MMDB_dump_entry_data_list with indent=-1 returns success");

            status = MMDB_dump_entry_data_list(devnull, entry_data_list, -100);
            cmp_ok(
                status,
                "==",
                MMDB_SUCCESS,
                "MMDB_dump_entry_data_list with indent=-100 returns success");

            status =
                MMDB_dump_entry_data_list(devnull, entry_data_list, INT_MIN);
            cmp_ok(status,
                   "==",
                   MMDB_SUCCESS,
                   "MMDB_dump_entry_data_list with indent=INT_MIN returns "
                   "success");

            fclose(devnull);
        }
        MMDB_free_entry_data_list(entry_data_list);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    test_negative_indent();
    done_testing();
}
