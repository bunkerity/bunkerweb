#include "maxminddb_test_helper.h"

void test_one_ip(MMDB_s *mmdb,
                 const char *ip,
                 const char *filename,
                 const char *mode_desc) {
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, mode_desc);

    ok(result.found_entry,
       "got a result for an IPv4 address included in a larger-than-IPv4 subnet "
       "- %s - %s",
       ip,
       mode_desc);

    data_ok(&result, MMDB_DATA_TYPE_UTF8_STRING, "string value for IP", NULL);
}

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-no-ipv4-search-tree.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    test_one_ip(mmdb, "1.1.1.1", filename, mode_desc);
    test_one_ip(mmdb, "255.255.255.255", filename, mode_desc);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
