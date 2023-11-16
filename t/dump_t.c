#define _XOPEN_SOURCE 700

#include "maxminddb_test_helper.h"

#ifdef HAVE_OPEN_MEMSTREAM
void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-decoder.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const char *ip = "1.1.1.1";
    MMDB_lookup_result_s result =
        lookup_string_ok(mmdb, ip, filename, mode_desc);

    MMDB_entry_data_list_s *entry_data_list;
    int status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);

    ok(MMDB_SUCCESS == status, "MMDB_get_entry_data_list is successful");

    char *dump_output;
    size_t dump_size;
    FILE *stream = open_memstream(&dump_output, &dump_size);
    status = MMDB_dump_entry_data_list(stream, entry_data_list, 0);
    fclose(stream);
    MMDB_free_entry_data_list(entry_data_list);

    ok(MMDB_SUCCESS == status,
       "MMDB_dump_entry_data_list is successful - %s",
       mode_desc);

    cmp_ok(dump_size, ">", 0, "MMDB_dump produced output - %s", mode_desc);

    char *expect[] = {"{",
                      "  \"array\": ",
                      "    [",
                      "      1 <uint32>",
                      "      2 <uint32>",
                      "      3 <uint32>",
                      "    ]",
                      "  \"boolean\": ",
                      "    true <boolean>",
                      "  \"bytes\": ",
                      "    0000002A <bytes>",
                      "  \"double\": ",
                      "    42.123456 <double>",
                      "  \"float\": ",
                      "    1.100000 <float>",
                      "  \"int32\": ",
                      "    -268435456 <int32>",
                      "  \"map\": ",
                      "    {",
                      "      \"mapX\": ",
                      "        {",
                      "          \"arrayX\": ",
                      "            [",
                      "              7 <uint32>",
                      "              8 <uint32>",
                      "              9 <uint32>",
                      "            ]",
                      "          \"utf8_stringX\": ",
                      "            \"hello\" <utf8_string>",
                      "        }",
                      "    }",
                      "  \"uint128\": ",
                      "    0x01000000000000000000000000000000 <uint128>",
                      "  \"uint16\": ",
                      "    100 <uint16>",
                      "  \"uint32\": ",
                      "    268435456 <uint32>",
                      "  \"uint64\": ",
                      "    1152921504606846976 <uint64>",
                      "  \"utf8_string\": ",
                      "    \"unicode! ☯ - ♫\" <utf8_string>",
                      "}"};

    for (int i = 0; i < 42; i++) {
        ok((strstr(dump_output, expect[i]) != NULL),
           "dump output contains expected line (%s) - %s",
           expect[i],
           mode_desc);
    }

    free(dump_output);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
#else
int main(void) {
    plan(SKIP_ALL, "This test requires the open_memstream() function");
}
#endif
