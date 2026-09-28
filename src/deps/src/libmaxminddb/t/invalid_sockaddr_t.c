#include "maxminddb_test_helper.h"

static void test_invalid_sockaddr_family(const char *filename,
                                         sa_family_t family,
                                         const char *open_msg,
                                         const char *family_msg) {
    char *db_file = test_database_path(filename);
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, open_msg);
    free(db_file);

    if (!mmdb) {
        return;
    }

    struct sockaddr addr = {.sa_family = family};
    int mmdb_error = MMDB_SUCCESS;
    MMDB_lookup_result_s result =
        MMDB_lookup_sockaddr(mmdb, &addr, &mmdb_error);

    ok(!result.found_entry, "%s: no entry returned", family_msg);
    cmp_ok(result.netmask, "==", 0, "%s: netmask left at zero", family_msg);
    cmp_ok(mmdb_error,
           "==",
           MMDB_INVALID_NETWORK_ADDRESS_ERROR,
           "%s: MMDB_lookup_sockaddr rejects unsupported family",
           family_msg);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    test_invalid_sockaddr_family("MaxMind-DB-test-ipv4-24.mmdb",
                                 AF_UNIX,
                                 "opened IPv4 test database (AF_UNIX)",
                                 "AF_UNIX against IPv4 db");
    test_invalid_sockaddr_family("MaxMind-DB-test-ipv4-24.mmdb",
                                 AF_UNSPEC,
                                 "opened IPv4 test database (AF_UNSPEC)",
                                 "AF_UNSPEC against IPv4 db");
    test_invalid_sockaddr_family("MaxMind-DB-test-ipv6-24.mmdb",
                                 AF_UNIX,
                                 "opened IPv6 test database (AF_UNIX)",
                                 "AF_UNIX against IPv6 db");
    test_invalid_sockaddr_family("MaxMind-DB-test-ipv6-24.mmdb",
                                 AF_UNSPEC,
                                 "opened IPv6 test database (AF_UNSPEC)",
                                 "AF_UNSPEC against IPv6 db");
    done_testing();
}
