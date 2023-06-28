#include "maxminddb_test_helper.h"

MMDB_entry_data_list_s *
test_array_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *array = entry_data_list = entry_data_list->next;
    cmp_ok(array->entry_data.type,
           "==",
           MMDB_DATA_TYPE_ARRAY,
           "'array' key's value is an array");
    cmp_ok(array->entry_data.data_size,
           "==",
           3,
           "'array' key's value has 3 elements");

    MMDB_entry_data_list_s *idx0 = entry_data_list = entry_data_list->next;
    cmp_ok(idx0->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "first array entry is a UINT32");
    cmp_ok(idx0->entry_data.uint32, "==", 1, "first array entry value is 1");

    MMDB_entry_data_list_s *idx1 = entry_data_list = entry_data_list->next;
    cmp_ok(idx1->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "second array entry is a UINT32");
    cmp_ok(idx1->entry_data.uint32, "==", 2, "second array entry value is 2");

    MMDB_entry_data_list_s *idx2 = entry_data_list = entry_data_list->next;
    cmp_ok(idx2->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "third array entry is a UINT32");
    cmp_ok(idx2->entry_data.uint32, "==", 3, "third array entry value is 3");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_boolean_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_BOOLEAN,
           "'boolean' key's value is a boolean");
    ok(value->entry_data.boolean, "'boolean' key's value is true");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_bytes_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_BYTES,
           "'bytes' key's value is bytes");
    uint8_t *bytes = malloc(value->entry_data.data_size);
    if (NULL == bytes) {
        BAIL_OUT("malloc failed");
    }
    memcpy(bytes, value->entry_data.bytes, value->entry_data.data_size);
    uint8_t expect[] = {0x00, 0x00, 0x00, 0x2a};

    ok(memcmp(bytes, expect, 4) == 0, "got expected value for bytes key");

    free((void *)bytes);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_double_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_DOUBLE,
           "'double' key's value is a double");

    compare_double(value->entry_data.double_value, 42.123456);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_float_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_FLOAT,
           "'float' key's value is a float");

    compare_float(value->entry_data.float_value, 1.1F);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_int32_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_INT32,
           "'int32' key's value is an int32");

    int32_t expect = 1 << 28;
    expect *= -1;
    cmp_ok(value->entry_data.int32,
           "==",
           expect,
           "got expected value for int32 key");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_arrayX_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *arrayX = entry_data_list = entry_data_list->next;
    cmp_ok(arrayX->entry_data.type,
           "==",
           MMDB_DATA_TYPE_ARRAY,
           "'map{mapX}{arrayX}' key's value is an array");
    cmp_ok(arrayX->entry_data.data_size,
           "==",
           3,
           "'map{mapX}{arrayX}' key's value has 3 elements");

    MMDB_entry_data_list_s *idx0 = entry_data_list = entry_data_list->next;
    cmp_ok(idx0->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "first array entry is a UINT32");
    cmp_ok(idx0->entry_data.uint32, "==", 7, "first array entry value is 7");

    MMDB_entry_data_list_s *idx1 = entry_data_list = entry_data_list->next;
    cmp_ok(idx1->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "second array entry is a UINT32");
    cmp_ok(idx1->entry_data.uint32, "==", 8, "second array entry value is 8");

    MMDB_entry_data_list_s *idx2 = entry_data_list = entry_data_list->next;
    cmp_ok(idx2->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "third array entry is a UINT32");
    cmp_ok(idx2->entry_data.uint32, "==", 9, "third array entry value is 9");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_mapX_key_value_pair(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *mapX_key = entry_data_list = entry_data_list->next;
    cmp_ok(mapX_key->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "found a map key in 'map{mapX}'");
    char *mapX_key_name = dup_entry_string_or_bail(mapX_key->entry_data);

    if (strcmp(mapX_key_name, "utf8_stringX") == 0) {
        MMDB_entry_data_list_s *mapX_value = entry_data_list =
            entry_data_list->next;
        cmp_ok(mapX_value->entry_data.type,
               "==",
               MMDB_DATA_TYPE_UTF8_STRING,
               "'map{mapX}{utf8_stringX}' type is utf8_string");
        char *utf8_stringX_value =
            dup_entry_string_or_bail(mapX_value->entry_data);
        ok(strcmp(utf8_stringX_value, "hello") == 0,
           "map{mapX}{utf8_stringX} value is 'hello'");
        free(utf8_stringX_value);
    } else if (strcmp(mapX_key_name, "arrayX") == 0) {
        entry_data_list = test_arrayX_value(entry_data_list);
    } else {
        ok(0, "unknown key found in map{mapX} - %s", mapX_key_name);
    }

    free(mapX_key_name);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_map_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *map = entry_data_list = entry_data_list->next;
    cmp_ok(map->entry_data.type,
           "==",
           MMDB_DATA_TYPE_MAP,
           "'map' key's value is a map");
    cmp_ok(map->entry_data.data_size,
           "==",
           1,
           "'map' key's value has 1 key/value pair");

    MMDB_entry_data_list_s *map_key_1 = entry_data_list = entry_data_list->next;
    cmp_ok(map_key_1->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "found a map key in 'map'");
    char *map_key_1_name = dup_entry_string_or_bail(map_key_1->entry_data);
    ok(strcmp(map_key_1_name, "mapX") == 0, "key name is mapX");
    free(map_key_1_name);

    MMDB_entry_data_list_s *mapX = entry_data_list = entry_data_list->next;
    cmp_ok(mapX->entry_data.type,
           "==",
           MMDB_DATA_TYPE_MAP,
           "'map{mapX}' key's value is a map");
    cmp_ok(mapX->entry_data.data_size,
           "==",
           2,
           "'map' key's value has 2 key/value pairs");

    entry_data_list = test_mapX_key_value_pair(entry_data_list);
    entry_data_list = test_mapX_key_value_pair(entry_data_list);

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_uint128_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT128,
           "'uint128' key's value is an uint128");

#if MMDB_UINT128_IS_BYTE_ARRAY
    uint8_t expect[16] = {0x01,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00,
                          0x00};
    ok(memcmp(value->entry_data.uint128, expect, 16) == 0,
       "uint128 field is 2**120");
#else
    mmdb_uint128_t expect = 1;
    expect <<= 120;
    cmp_ok(value->entry_data.uint128, "==", expect, "uint128 field is 2**120");
#endif

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_uint16_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT16,
           "'uint16' key's value is an uint16");
    uint16_t expect = 100;
    ok(value->entry_data.uint16 == expect, "uint16 field is 100");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_uint32_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT32,
           "'uint32' key's value is an uint32");
    uint32_t expect = 1 << 28;
    cmp_ok(value->entry_data.uint32, "==", expect, "uint32 field is 100");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_uint64_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UINT64,
           "'uint64' key's value is an uint64");
    uint64_t expect = 1;
    expect <<= 60;
    cmp_ok(value->entry_data.uint64, "==", expect, "uint64 field is 2**60");

    return entry_data_list;
}

MMDB_entry_data_list_s *
test_utf8_string_value(MMDB_entry_data_list_s *entry_data_list) {
    MMDB_entry_data_list_s *value = entry_data_list = entry_data_list->next;

    cmp_ok(value->entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "'utf8_string' key's value is a string");
    char *utf8_string = dup_entry_string_or_bail(value->entry_data);
    // This is hex for "unicode! ☯ - ♫" as bytes
    char expect[19] = {0x75,
                       0x6e,
                       0x69,
                       0x63,
                       0x6f,
                       0x64,
                       0x65,
                       0x21,
                       0x20,
                       (char)0xe2,
                       (char)0x98,
                       (char)0xaf,
                       0x20,
                       0x2d,
                       0x20,
                       (char)0xe2,
                       (char)0x99,
                       (char)0xab,
                       0x00};

    is(utf8_string, expect, "got expected value for utf8_string key");

    free(utf8_string);

    return entry_data_list;
}

void run_tests(int mode, const char *description) {
    const char *filename = "MaxMind-DB-test-decoder.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, description);
    free(path);

    char *ip = "1.1.1.1";
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, description);

    MMDB_entry_data_list_s *entry_data_list, *first;
    int status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);

    if (MMDB_SUCCESS != status) {
        BAIL_OUT("MMDB_get_entry_data_list failed with %s",
                 MMDB_strerror(status));
    } else {
        cmp_ok(
            status, "==", MMDB_SUCCESS, "MMDB_get_entry_data_list succeeded");
    }

    first = entry_data_list;

    cmp_ok(entry_data_list->entry_data.type,
           "==",
           MMDB_DATA_TYPE_MAP,
           "first entry in entry data list is a map");
    cmp_ok(entry_data_list->entry_data.data_size,
           "==",
           12,
           "first map in entry data list has 12 k/v pairs");

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
        if (strcmp(key_name, "array") == 0) {
            entry_data_list = test_array_value(entry_data_list);
        } else if (strcmp(key_name, "boolean") == 0) {
            entry_data_list = test_boolean_value(entry_data_list);
        } else if (strcmp(key_name, "bytes") == 0) {
            entry_data_list = test_bytes_value(entry_data_list);
        } else if (strcmp(key_name, "double") == 0) {
            entry_data_list = test_double_value(entry_data_list);
        } else if (strcmp(key_name, "float") == 0) {
            entry_data_list = test_float_value(entry_data_list);
        } else if (strcmp(key_name, "int32") == 0) {
            entry_data_list = test_int32_value(entry_data_list);
        } else if (strcmp(key_name, "map") == 0) {
            entry_data_list = test_map_value(entry_data_list);
        } else if (strcmp(key_name, "uint128") == 0) {
            entry_data_list = test_uint128_value(entry_data_list);
        } else if (strcmp(key_name, "uint16") == 0) {
            entry_data_list = test_uint16_value(entry_data_list);
        } else if (strcmp(key_name, "uint32") == 0) {
            entry_data_list = test_uint32_value(entry_data_list);
        } else if (strcmp(key_name, "uint64") == 0) {
            entry_data_list = test_uint64_value(entry_data_list);
        } else if (strcmp(key_name, "utf8_string") == 0) {
            entry_data_list = test_utf8_string_value(entry_data_list);
        } else {
            ok(0, "unknown key found in map - %s", key_name);
        }

        free(key_name);
    }

    MMDB_free_entry_data_list(first);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
