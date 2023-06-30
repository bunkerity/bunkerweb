#include "maxminddb_test_helper.h"

/* This test exercises a bug found in MMDB_get_value for certain types of
 * nested data structures which contain pointers. See
 * https://github.com/maxmind/libmaxminddb/issues/2 and
 * https://github.com/maxmind/libmaxminddb/issues/3.
 *
 * There is also the potential for a similar bug when looking up a value by
 * path in an array. This is not tested (yet) as we don't have the right test
 * data for it.
 *
 * These tests are somewhat fragile since they depend on a specific data
 * layout in the database. Ideally the test would check that this layout
 * exists before checking to see if the lookups are correct.
 */

void test_one_ip(MMDB_s *mmdb,
                 const char *filename,
                 const char *mode_desc,
                 char *ip,
                 char *country_code) {
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, mode_desc);

    MMDB_entry_data_s entry_data = data_ok(&result,
                                           MMDB_DATA_TYPE_UTF8_STRING,
                                           "country{iso_code}",
                                           "country",
                                           "iso_code",
                                           NULL);

    if (ok(entry_data.has_data, "found data for country{iso_code}")) {
        char *string =
            mmdb_strndup(entry_data.utf8_string, entry_data.data_size);
        if (!string) {
            ok(0, "mmdb_strndup() call failed");
            exit(1);
        }
        if (!ok(strcmp(string, country_code) == 0,
                "iso_code is %s",
                country_code)) {
            diag("  value is %s", string);
        }
        free(string);
    }
}

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "GeoIP2-City-Test.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    /* This exercises a bug where the entire top-level value is a pointer to
     * another part of the data section. */
    test_one_ip(mmdb, filename, mode_desc, "2001:218::", "JP");
    /* This exercises a bug where one subnet's data shares part of the data
     * with another subnet - in this case it is the "country" key (and others)
     * in the top level map. We are testing that the "country" key's value is
     * handled correctly. The value _should_ be a pointer to another map. */
    test_one_ip(mmdb, filename, mode_desc, "81.2.69.160", "GB");

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
