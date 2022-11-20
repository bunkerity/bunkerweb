#include "maxminddb_test_helper.h"

static void test_big_lookup(void);

/* These globals are gross but it's the easiest way to mix calling
 * for_all_modes() and for_all_record_sizes() */
static int Current_Mode;
static const char *Current_Mode_Description;

void test_one_result(MMDB_s *mmdb,
                     MMDB_lookup_result_s result,
                     const char *ip,
                     const char *expect,
                     const char *function,
                     const char *filename,
                     const char *mode_desc) {
    int is_ok = ok(result.found_entry,
                   "got a result for an IP in the database - %s - %s - %s - %s",
                   function,
                   ip,
                   filename,
                   mode_desc);

    if (!is_ok) {
        return;
    }

    MMDB_entry_data_s data =
        data_ok(&result, MMDB_DATA_TYPE_UTF8_STRING, "result{ip}", "ip", NULL);

    char *string = mmdb_strndup(data.utf8_string, data.data_size);

    char *real_expect;
    if (mmdb->metadata.ip_version == 4 || strncmp(expect, "::", 2) == 0) {
        real_expect = mmdb_strndup(expect, strlen(expect));
    } else {
        // When looking up IPv4 addresses in a mixed DB the result will be
        // something like "::1.2.3.4", not just "1.2.3.4".
        size_t maxlen = strlen(expect) + 3;
        real_expect = malloc(maxlen);
        if (!real_expect) {
            BAIL_OUT("could not allocate memory");
        }
        snprintf(real_expect, maxlen, "::%s", expect);
    }

    is(string,
       real_expect,
       "found expected result for ip key - %s - %s - %s - %s",
       function,
       ip,
       filename,
       mode_desc);

    free(real_expect);
    free(string);
}

void test_one_ip(MMDB_s *mmdb,
                 const char *ip,
                 const char *expect,
                 const char *filename,
                 const char *mode_desc) {
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, mode_desc);

    test_one_result(
        mmdb, result, ip, expect, "MMDB_lookup_string", filename, mode_desc);

    result = lookup_sockaddr_ok(mmdb, ip, filename, mode_desc);
    test_one_result(
        mmdb, result, ip, expect, "MMDB_lookup_addrinfo", filename, mode_desc);
}

void run_ipX_tests(const char *filename,
                   const char **missing_ips,
                   int missing_ips_length,
                   const char *pairs[][2],
                   int pairs_rows) {
    char *path = test_database_path(filename);
    int mode = Current_Mode;
    const char *mode_desc = Current_Mode_Description;

    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    char desc_suffix[500];
    snprintf(desc_suffix, 500, "%s - %s", filename, mode_desc);

    for (int i = 0; i < missing_ips_length; i++) {
        const char *ip = missing_ips[i];

        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        ok(!result.found_entry,
           "no result entry struct returned for IP address not in the database "
           "(string lookup) - %s - %s - %s",
           ip,
           filename,
           mode_desc);

        result = lookup_sockaddr_ok(mmdb, ip, filename, mode_desc);

        ok(!result.found_entry,
           "no result entry struct returned for IP address not in the database "
           "(ipv4 lookup) - %s - %s - %s",
           ip,
           filename,
           mode_desc);
    }

    for (int i = 0; i < pairs_rows; i += 1) {
        const char *ip_to_lookup = pairs[i][0];
        const char *expect = pairs[i][1];

        test_one_ip(mmdb, ip_to_lookup, expect, filename, mode_desc);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

void run_ipv4_tests(int UNUSED(record_size),
                    const char *filename,
                    const char *UNUSED(ignored)) {
    const char *pairs[9][2] = {
        {"1.1.1.1", "1.1.1.1"},
        {"1.1.1.2", "1.1.1.2"},
        {"1.1.1.3", "1.1.1.2"},
        {"1.1.1.7", "1.1.1.4"},
        {"1.1.1.9", "1.1.1.8"},
        {"1.1.1.15", "1.1.1.8"},
        {"1.1.1.17", "1.1.1.16"},
        {"1.1.1.31", "1.1.1.16"},
        {"1.1.1.32", "1.1.1.32"},
    };

    const char *missing[1] = {"2.3.4.5"};
    run_ipX_tests(filename, missing, 1, pairs, 9);
}

void run_ipv6_tests(int UNUSED(record_size),
                    const char *filename,
                    const char *UNUSED(ignored)) {
    const char *pairs[9][2] = {
        {"::1:ffff:ffff", "::1:ffff:ffff"},
        {"::2:0:0", "::2:0:0"},
        {"::2:0:1a", "::2:0:0"},
        {"::2:0:40", "::2:0:40"},
        {"::2:0:4f", "::2:0:40"},
        {"::2:0:50", "::2:0:50"},
        {"::2:0:52", "::2:0:50"},
        {"::2:0:58", "::2:0:58"},
        {"::2:0:59", "::2:0:58"},
    };

    const char *missing[2] = {"2.3.4.5", "::abcd"};
    run_ipX_tests(filename, missing, 2, pairs, 9);
}

void all_record_sizes(int mode, const char *description) {
    const char *ipv4_filename_fmts[] = {"MaxMind-DB-test-ipv4-%i.mmdb",
                                        "MaxMind-DB-test-mixed-%i.mmdb"};

    Current_Mode = mode;
    Current_Mode_Description = description;

    for (int i = 0; i < 2; i++) {
        for_all_record_sizes(ipv4_filename_fmts[i], &run_ipv4_tests);
    }

    const char *ipv6_filename_fmts[] = {"MaxMind-DB-test-ipv6-%i.mmdb",
                                        "MaxMind-DB-test-mixed-%i.mmdb"};

    for (int i = 0; i < 2; i++) {
        for_all_record_sizes(ipv6_filename_fmts[i], &run_ipv6_tests);
    }
}

static void test_big_lookup(void) {
    const char *const db_filename = "GeoIP2-Precision-Enterprise-Test.mmdb";
    char *db_path = test_database_path(db_filename);
    ok(db_path != NULL, "got database path");

    MMDB_s *const mmdb = open_ok(db_path, MMDB_MODE_MMAP, "mmap mode");
    ok(mmdb != NULL, "opened MMDB");
    free(db_path);

    int gai_err = 0, mmdb_err = 0;
    const char *const ip_address = "81.2.69.160";
    MMDB_lookup_result_s result =
        MMDB_lookup_string(mmdb, ip_address, &gai_err, &mmdb_err);
    ok(gai_err == 0, "no getaddrinfo error");
    ok(mmdb_err == MMDB_SUCCESS, "no error from maxminddb library");
    ok(result.found_entry, "found IP");

    MMDB_entry_data_list_s *entry_data_list = NULL;
    ok(MMDB_get_entry_data_list(&result.entry, &entry_data_list) ==
           MMDB_SUCCESS,
       "successfully looked up entry data list");
    ok(entry_data_list != NULL, "got an entry_data_list");

    MMDB_free_entry_data_list(entry_data_list);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&all_record_sizes);
    test_big_lookup();
    done_testing();
}
