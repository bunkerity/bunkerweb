#include "maxminddb_test_helper.h"

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-ipv4-28.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const char *ip = "::abcd";
    int gai_error, mmdb_error;
    MMDB_lookup_string(mmdb, ip, &gai_error, &mmdb_error);

    cmp_ok(mmdb_error,
           "==",
           MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR,
           "MMDB_lookup_string sets mmdb_error to "
           "MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR when we try to look up an "
           "IPv6 address in an IPv4-only database");

    struct addrinfo hints = {.ai_family = AF_INET6, .ai_flags = AI_NUMERICHOST};

    struct addrinfo *addresses;
    gai_error = getaddrinfo(
        "2001:db8:85a3:0:0:8a2e:370:7334", NULL, &hints, &addresses);
    if (gai_error) {
        BAIL_OUT("getaddrinfo failed: %s", gai_strerror(gai_error));
    }

    mmdb_error = 0;
    MMDB_lookup_sockaddr(mmdb, addresses->ai_addr, &mmdb_error);

    cmp_ok(mmdb_error,
           "==",
           MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR,
           "MMDB_lookup_sockaddr sets mmdb_error to "
           "MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR when we try to look up an "
           "IPv6 address in an IPv4-only database");

    freeaddrinfo(addresses);
    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
