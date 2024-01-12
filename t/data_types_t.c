#include "maxminddb_test_helper.h"

void test_all_data_types(MMDB_lookup_result_s *result,
                         const char *ip,
                         const char *UNUSED(filename),
                         const char *mode_desc) {
    {
        char description[500];
        snprintf(
            description, 500, "utf8_string field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(result,
                                         MMDB_DATA_TYPE_UTF8_STRING,
                                         description,
                                         "utf8_string",
                                         NULL);
        char *string = mmdb_strndup(data.utf8_string, data.data_size);
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
        is(string, expect, "got expected utf8_string value");

        free(string);
    }

    {
        char description[500];
        snprintf(description, 500, "double field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_DOUBLE, description, "double", NULL);

        compare_double(data.double_value, 42.123456);
    }

    {
        char description[500];
        snprintf(description, 500, "float field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_FLOAT, description, "float", NULL);

        compare_float(data.float_value, 1.1F);
    }

    {
        char description[500];
        snprintf(description, 500, "bytes field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_BYTES, description, "bytes", NULL);
        uint8_t expect[] = {0x00, 0x00, 0x00, 0x2a};
        ok(memcmp(data.bytes, expect, 4) == 0,
           "bytes field has expected value");
    }

    {
        char description[500];
        snprintf(description, 500, "uint16 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT16, description, "uint16", NULL);
        uint16_t expect = 100;
        ok(data.uint16 == expect, "uint16 field is 100");
    }

    {
        char description[500];
        snprintf(description, 500, "uint32 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT32, description, "uint32", NULL);
        uint32_t expect = 1 << 28;
        cmp_ok(data.uint32, "==", expect, "uint32 field is 2**28");
    }

    {
        char description[500];
        snprintf(description, 500, "int32 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_INT32, description, "int32", NULL);
        int32_t expect = 1 << 28;
        expect *= -1;
        cmp_ok(data.int32, "==", expect, "int32 field is -(2**28)");
    }

    {
        char description[500];
        snprintf(description, 500, "uint64 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT64, description, "uint64", NULL);
        uint64_t expect = 1;
        expect <<= 60;
        cmp_ok(data.uint64, "==", expect, "uint64 field is 2**60");
    }

    {
        char description[500];
        snprintf(description, 500, "uint128 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(
            result, MMDB_DATA_TYPE_UINT128, description, "uint128", NULL);
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
        ok(memcmp(data.uint128, expect, 16) == 0, "uint128 field is 2**120");
#else
        mmdb_uint128_t expect = 1;
        expect <<= 120;
        cmp_ok(data.uint128, "==", expect, "uint128 field is 2**120");
#endif
    }

    {
        char description[500];
        snprintf(description, 500, "boolean field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(
            result, MMDB_DATA_TYPE_BOOLEAN, description, "boolean", NULL);
        cmp_ok(data.boolean, "==", true, "boolean field is true");
    }

    {
        char description[500];
        snprintf(description, 500, "array field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_ARRAY, description, "array", NULL);
        ok(data.data_size == 3, "array field has 3 elements");

        snprintf(description, 500, "array[0] for %s - %s", ip, mode_desc);
        data = data_ok(
            result, MMDB_DATA_TYPE_UINT32, description, "array", "0", NULL);
        ok(data.uint32 == 1, "array[0] is 1");

        snprintf(description, 500, "array[1] for %s - %s", ip, mode_desc);
        data = data_ok(
            result, MMDB_DATA_TYPE_UINT32, description, "array", "1", NULL);
        ok(data.uint32 == 2, "array[1] is 1");

        snprintf(description, 500, "array[2] for %s - %s", ip, mode_desc);
        data = data_ok(
            result, MMDB_DATA_TYPE_UINT32, description, "array", "2", NULL);
        ok(data.uint32 == 3, "array[2] is 1");
    }

    {
        char description[500];
        snprintf(description, 500, "map field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_MAP, description, "map", NULL);
        ok(data.data_size == 1, "map field has 1 element");

        snprintf(description, 500, "map{mapX} for %s - %s", ip, mode_desc);

        data = data_ok(
            result, MMDB_DATA_TYPE_MAP, description, "map", "mapX", NULL);
        ok(data.data_size == 2, "map{mapX} field has 2 elements");

        snprintf(description,
                 500,
                 "map{mapX}{utf8_stringX} for %s - %s",
                 ip,
                 mode_desc);

        data = data_ok(result,
                       MMDB_DATA_TYPE_UTF8_STRING,
                       description,
                       "map",
                       "mapX",
                       "utf8_stringX",
                       NULL);
        char *string = mmdb_strndup(data.utf8_string, data.data_size);
        is(string, "hello", "map{mapX}{utf8_stringX} is 'hello'");
        free(string);

        snprintf(
            description, 500, "map{mapX}{arrayX} for %s - %s", ip, mode_desc);
        data = data_ok(result,
                       MMDB_DATA_TYPE_ARRAY,
                       description,
                       "map",
                       "mapX",
                       "arrayX",
                       NULL);
        ok(data.data_size == 3, "map{mapX}{arrayX} field has 3 elements");

        snprintf(description,
                 500,
                 "map{mapX}{arrayX}[0] for %s - %s",
                 ip,
                 mode_desc);
        data = data_ok(result,
                       MMDB_DATA_TYPE_UINT32,
                       description,
                       "map",
                       "mapX",
                       "arrayX",
                       "0",
                       NULL);
        ok(data.uint32 == 7, "map{mapX}{arrayX}[0] is 7");

        snprintf(description,
                 500,
                 "map{mapX}{arrayX}[1] for %s - %s",
                 ip,
                 mode_desc);
        data = data_ok(result,
                       MMDB_DATA_TYPE_UINT32,
                       description,
                       "map",
                       "mapX",
                       "arrayX",
                       "1",
                       NULL);
        ok(data.uint32 == 8, "map{mapX}{arrayX}[1] is 8");

        snprintf(description,
                 500,
                 "map{mapX}{arrayX}[2] for %s - %s",
                 ip,
                 mode_desc);
        data = data_ok(result,
                       MMDB_DATA_TYPE_UINT32,
                       description,
                       "map",
                       "mapX",
                       "arrayX",
                       "2",
                       NULL);
        ok(data.uint32 == 9, "map{mapX}{arrayX}[2] is 9");
    }
}

void test_all_data_types_as_zero(MMDB_lookup_result_s *result,
                                 const char *ip,
                                 const char *UNUSED(filename),
                                 const char *mode_desc) {
    {
        char description[500];
        snprintf(
            description, 500, "utf8_string field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(result,
                                         MMDB_DATA_TYPE_UTF8_STRING,
                                         description,
                                         "utf8_string",
                                         NULL);
        is(data.utf8_string, "", "got expected utf8_string value (NULL)");
    }

    {
        char description[500];
        snprintf(description, 500, "double field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_DOUBLE, description, "double", NULL);

        compare_double(data.double_value, 0.0);
    }

    {
        char description[500];
        snprintf(description, 500, "float field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_FLOAT, description, "float", NULL);

        compare_float(data.float_value, 0.0F);
    }

    {
        char description[500];
        snprintf(description, 500, "bytes field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_BYTES, description, "bytes", NULL);
        ok(data.data_size == 0, "bytes field data_size is 0");
        /* In C does it makes sense to write something like this?
           uint8_t expect[0] = {};
           ok(memcmp(data.bytes, expect, 0) == 0, "got expected bytes value
           (NULL)"); */
    }

    {
        char description[500];
        snprintf(description, 500, "uint16 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT16, description, "uint16", NULL);
        uint16_t expect = 0;
        ok(data.uint16 == expect, "uint16 field is 0");
    }

    {
        char description[500];
        snprintf(description, 500, "uint32 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT32, description, "uint32", NULL);
        uint32_t expect = 0;
        cmp_ok(data.uint32, "==", expect, "uint32 field is 0");
    }

    {
        char description[500];
        snprintf(description, 500, "int32 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_INT32, description, "int32", NULL);
        int32_t expect = 0;
        expect *= -1;
        cmp_ok(data.int32, "==", expect, "int32 field is 0");
    }

    {
        char description[500];
        snprintf(description, 500, "uint64 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_UINT64, description, "uint64", NULL);
        uint64_t expect = 0;
        cmp_ok(data.uint64, "==", expect, "uint64 field is 0");
    }

    {
        char description[500];
        snprintf(description, 500, "uint128 field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(
            result, MMDB_DATA_TYPE_UINT128, description, "uint128", NULL);
#if MMDB_UINT128_IS_BYTE_ARRAY
        uint8_t expect[16] = {0x00,
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
        ok(memcmp(data.uint128, expect, 16) == 0, "uint128 field is 0");
#else
        mmdb_uint128_t expect = 0;
        cmp_ok(data.uint128, "==", expect, "uint128 field is 0");
#endif
    }

    {
        char description[500];
        snprintf(description, 500, "boolean field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data = data_ok(
            result, MMDB_DATA_TYPE_BOOLEAN, description, "boolean", NULL);
        cmp_ok(data.boolean, "==", false, "boolean field is false");
    }

    {
        char description[500];
        snprintf(description, 500, "array field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_ARRAY, description, "array", NULL);
        ok(data.data_size == 0, "array field has 0 elements");
    }

    {
        char description[500];
        snprintf(description, 500, "map field for %s - %s", ip, mode_desc);

        MMDB_entry_data_s data =
            data_ok(result, MMDB_DATA_TYPE_MAP, description, "map", NULL);
        ok(data.data_size == 0, "map field has 0 elements");
    }
}

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-decoder.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);

    // All of the remaining tests require an open mmdb
    if (NULL == mmdb) {
        diag("could not open %s - skipping remaining tests", path);
        return;
    }

    free(path);

    {
        const char *ip = "not an ip";

        int gai_error, mmdb_error;
        MMDB_lookup_result_s result =
            MMDB_lookup_string(mmdb, ip, &gai_error, &mmdb_error);

        cmp_ok(gai_error,
               "==",
               EAI_NONAME,
               "MMDB_lookup populates getaddrinfo error properly - %s",
               ip);

        ok(!result.found_entry,
           "no result entry struct returned for invalid IP address '%s'",
           ip);
    }

    {
        const char *ip = "e900::";
        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        ok(!result.found_entry,
           "no result entry struct returned for IP address not in the database "
           "- %s - %s - %s",
           ip,
           filename,
           mode_desc);
    }

    {
        const char *ip = "::1.1.1.1";
        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        ok(result.found_entry,
           "got a result entry struct for IP address in the database - %s - %s "
           "- %s",
           ip,
           filename,
           mode_desc);

        cmp_ok(result.entry.offset,
               ">",
               0,
               "result.entry.offset > 0 for address in the database - %s - %s "
               "- %s",
               ip,
               filename,
               mode_desc);

        test_all_data_types(&result, ip, filename, mode_desc);
    }

    {
        const char *ip = "::4.5.6.7";
        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        ok(result.found_entry,
           "got a result entry struct for IP address in the database - %s - %s "
           "- %s",
           ip,
           filename,
           mode_desc);

        cmp_ok(result.entry.offset,
               ">",
               0,
               "result.entry.offset > 0 for address in the database - %s - %s "
               "- %s",
               ip,
               filename,
               mode_desc);

        test_all_data_types(&result, ip, filename, mode_desc);
    }

    {
        const char *ip = "::0.0.0.0";
        MMDB_lookup_result_s result =
            lookup_string_ok(mmdb, ip, filename, mode_desc);

        ok(result.found_entry,
           "got a result entry struct for IP address in the database - %s - %s "
           "- %s",
           ip,
           filename,
           mode_desc);

        test_all_data_types_as_zero(&result, ip, filename, mode_desc);
    }

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
