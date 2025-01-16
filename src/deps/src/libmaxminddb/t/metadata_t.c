#include "maxminddb_test_helper.h"

void test_metadata(MMDB_s *mmdb, const char *mode_desc) {
    cmp_ok(mmdb->metadata.node_count,
           "==",
           163,
           "node_count is 163 - %s",
           mode_desc);
    cmp_ok(mmdb->metadata.record_size,
           "==",
           24,
           "record_size is 24 - %s",
           mode_desc);
    cmp_ok(
        mmdb->metadata.ip_version, "==", 4, "ip_version is 4 - %s", mode_desc);
    is(mmdb->metadata.database_type,
       "Test",
       "database_type is Test - %s",
       mode_desc);
    // 2013-07-01T00:00:00Z
    uint64_t expect_epoch = 1372636800;
    int is_ok = cmp_ok(mmdb->metadata.build_epoch,
                       ">=",
                       expect_epoch,
                       "build_epoch > %lli",
                       expect_epoch);
    if (!is_ok) {
        diag("  epoch is %lli", mmdb->metadata.build_epoch);
    }

    cmp_ok(mmdb->metadata.binary_format_major_version,
           "==",
           2,
           "binary_format_major_version is 2 - %s",
           mode_desc);
    cmp_ok(mmdb->metadata.binary_format_minor_version,
           "==",
           0,
           "binary_format_minor_version is 0 - %s",
           mode_desc);

    cmp_ok(mmdb->metadata.languages.count,
           "==",
           2,
           "found 2 languages - %s",
           mode_desc);
    is(mmdb->metadata.languages.names[0],
       "en",
       "first language is en - %s",
       mode_desc);
    is(mmdb->metadata.languages.names[1],
       "zh",
       "second language is zh - %s",
       mode_desc);

    cmp_ok(mmdb->metadata.description.count,
           "==",
           2,
           "found 2 descriptions - %s",
           mode_desc);
    for (uint16_t i = 0; i < mmdb->metadata.description.count; i++) {
        const char *language =
            mmdb->metadata.description.descriptions[i]->language;
        const char *description =
            mmdb->metadata.description.descriptions[i]->description;
        if (strncmp(language, "en", 2) == 0) {
            ok(1, "found en description");
            is(description, "Test Database", "en description");
        } else if (strncmp(language, "zh", 2) == 0) {
            ok(1, "found zh description");
            is(description, "Test Database Chinese", "zh description");
        } else {
            ok(0,
               "found unknown description in unexpected language - %s",
               language);
        }
    }

    cmp_ok(mmdb->full_record_byte_size,
           "==",
           6,
           "full_record_byte_size is 6 - %s",
           mode_desc);
}

MMDB_entry_data_list_s *
test_languages_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *languages = entry_data_list = entry_data_list->next;

    cmp_ok(languages->entry_data.type,
           "==",
           MMDB_DATA_TYPE_ARRAY,
           "'languages' key's value is an array");
    cmp_ok(languages->entry_data.data_size,
           "==",
           2,
           "'languages' key's value has 2 elements");

    MMDB_entry_data_list_s *idx0 = entry_data_list = entry_data_list->next;
    cmp_ok(idx0->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "first array entry is a UTF8_STRING");
    char *lang0 = dup_entry_string_or_bail(idx0->entry_data);
    is(lang0, "en", "first language is en");
    free(lang0);

    MMDB_entry_data_list_s *idx1 = entry_data_list = entry_data_list->next;
    cmp_ok(idx1->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "second array entry is a UTF8_STRING");
    char *lang1 = dup_entry_string_or_bail(idx1->entry_data);
    is(lang1, "zh", "second language is zh");
    free(lang1);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_description_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *description = entry_data_list =
        entry_data_list->next;
    cmp_ok(description->entry_data.type,
           "==",
           MMDB_DATA_TYPE_MAP,
           "'description' key's value is a map");
    cmp_ok(description->entry_data.data_size,
           "==",
           2,
           "'description' key's value has 2 key/value pairs");

    for (int i = 0; i < 2; i++) {
        MMDB_entry_data_list_s *key = entry_data_list = entry_data_list->next;
        cmp_ok(key->entry_data.type,
               "==",
               MMDB_DATA_TYPE_UTF8_STRING,
               "found a map key in 'map'");
        char *key_name = dup_entry_string_or_bail(key->entry_data);

        MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;
        cmp_ok(value->entry_data.type,
               "==",
               MMDB_DATA_TYPE_UTF8_STRING,
               "map value is a UTF8_STRING");
        char *description = dup_entry_string_or_bail(value->entry_data);

        if (strcmp(key_name, "en") == 0) {
            is(description,
               "Test Database",
               "en description == 'Test Database'");
        } else if (strcmp(key_name, "zh") == 0) {
            is(description,
               "Test Database Chinese",
               "zh description == 'Test Database Chinese'");
        } else {
            ok(0, "unknown key found in description map - %s", key_name);
        }

        free(key_name);
        free(description);
    }

    return entry_data_list;
}

void test_metadata_as_data_entry_list(MMDB_s *mmdb, const char *mode_desc) {
    MMDB_entry_data_list_s *entry_data_list, *first;
    int status = MMDB_get_metadata_as_entry_data_list(mmdb, &entry_data_list);

    first = entry_data_list;

    cmp_ok(status,
           "==",
           MMDB_SUCCESS,
           "get metadata as data_entry_list - %s",
           mode_desc);

    cmp_ok(first->entry_data.data_size,
           "==",
           9,
           "metadata map has 9 key/value pairs");

    while (1) {
        MMDB_entry_data_list_s *key = entry_data_list = entry_data_list->next;

        if (!key) {
            break;
        }

        cmp_ok(key->entry_data.type,
               "==",
               MMDB_DATA_TYPE_UTF8_STRING,
               "found a map key");

        char *key_name = dup_entry_string_or_bail(key->entry_data);
        if (strcmp(key_name, "node_count") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            cmp_ok(value->entry_data.uint32, "==", 163, "node_count == 163");
        } else if (strcmp(key_name, "record_size") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            cmp_ok(value->entry_data.uint16, "==", 24, "record_size == 24");
        } else if (strcmp(key_name, "ip_version") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            cmp_ok(value->entry_data.uint16, "==", 4, "ip_version == 4");
        } else if (strcmp(key_name, "binary_format_major_version") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            cmp_ok(value->entry_data.uint16,
                   "==",
                   2,
                   "binary_format_major_version == 2");
        } else if (strcmp(key_name, "binary_format_minor_version") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            cmp_ok(value->entry_data.uint16,
                   "==",
                   0,
                   "binary_format_minor_version == 0");
        } else if (strcmp(key_name, "build_epoch") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            ok(value->entry_data.uint64 > 1373571901,
               "build_epoch > 1373571901");
        } else if (strcmp(key_name, "database_type") == 0) {
            MMDB_entry_data_list_s *value = entry_data_list =
                entry_data_list->next;
            char *type = dup_entry_string_or_bail(value->entry_data);
            is(type, "Test", "type == Test");
            free(type);
        } else if (strcmp(key_name, "languages") == 0) {
            entry_data_list = test_languages_value(entry_data_list);
        } else if (strcmp(key_name, "description") == 0) {
            entry_data_list = test_description_value(entry_data_list);
        } else {
            ok(0, "unknown key found in metadata map - %s", key_name);
        }

        free(key_name);
    }

    MMDB_free_entry_data_list(first);
}

void run_tests(int mode, const char *mode_desc) {
    const char *file = "MaxMind-DB-test-ipv4-24.mmdb";
    char *path = test_database_path(file);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);

    // All of the remaining tests require an open mmdb
    if (NULL == mmdb) {
        diag("could not open %s - skipping remaining tests", path);
        return;
    }
    free(path);

    test_metadata(mmdb, mode_desc);
    test_metadata_as_data_entry_list(mmdb, mode_desc);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
