#include "maxminddb_test_helper.h"

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-metadata-pointers.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    char *repeated_string = "Lots of pointers in metadata";

    is(mmdb->metadata.database_type,
       repeated_string,
       "decoded pointer database_type");

    for (uint16_t i = 0; i < mmdb->metadata.description.count; i++) {
        const char *language =
            mmdb->metadata.description.descriptions[i]->language;
        const char *description =
            mmdb->metadata.description.descriptions[i]->description;
        is(description, repeated_string, "%s description", language);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
