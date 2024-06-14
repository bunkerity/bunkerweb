#include "maxminddb_test_helper.h"

void test_entry_data(MMDB_s *mmdb,
                     MMDB_entry_s *entry,
                     uint32_t node_number,
                     char *node_record) {
    MMDB_entry_data_s entry_data;
    int status = MMDB_get_value(entry, &entry_data, "ip", NULL);
    cmp_ok(status, "==", MMDB_SUCCESS, "successful data lookup for node");
    cmp_ok(entry_data.type,
           "==",
           MMDB_DATA_TYPE_UTF8_STRING,
           "returned entry type is UTF8_STRING for %s record of node %i",
           node_record,
           node_number);
}

void run_read_node_tests(MMDB_s *mmdb,
                         const uint32_t tests[][5],
                         int test_count,
                         uint8_t record_size) {
    for (int i = 0; i < test_count; i++) {
        uint32_t node_number = tests[i][0];
        MMDB_search_node_s node;
        int status = MMDB_read_node(mmdb, node_number, &node);
        if (MMDB_SUCCESS == status) {
            cmp_ok(node.left_record,
                   "==",
                   tests[i][1],
                   "left record for node %i is %i - %i bit DB",
                   node_number,
                   tests[i][1],
                   record_size);
            cmp_ok(node.left_record_type,
                   "==",
                   tests[i][2],
                   "left record type for node %i is %i",
                   node_number,
                   tests[i][2]);
            if (node.left_record_type == MMDB_RECORD_TYPE_DATA) {
                test_entry_data(
                    mmdb, &node.left_record_entry, node_number, "left");
            }

            cmp_ok(node.right_record,
                   "==",
                   tests[i][3],
                   "right record for node %i is %i - %i bit DB",
                   node_number,
                   tests[i][3],
                   record_size);
            cmp_ok(node.right_record_type,
                   "==",
                   tests[i][4],
                   "right record type for node %i is %i",
                   node_number,
                   tests[i][4]);

            if (node.right_record_type == MMDB_RECORD_TYPE_DATA) {
                test_entry_data(
                    mmdb, &node.right_record_entry, node_number, "right");
            }
        } else {
            diag("call to MMDB_read_node for node %i failed - %i bit DB",
                 node_number,
                 record_size);
        }
    }
}

void run_24_bit_record_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-mixed-24.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const uint32_t tests[7][5] = {{
                                      0,
                                      1,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      435,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      80,
                                      81,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      323,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      96,
                                      97,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      148,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      103,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      104,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      127,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      514,
                                      MMDB_RECORD_TYPE_DATA,
                                  },
                                  {
                                      132,
                                      527,
                                      MMDB_RECORD_TYPE_DATA,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                  },
                                  {
                                      241,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      242,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  }};
    run_read_node_tests(mmdb, tests, 7, 24);

    MMDB_close(mmdb);
    free(mmdb);
}

void run_28_bit_record_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-mixed-28.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const uint32_t tests[7][5] = {{
                                      0,
                                      1,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      435,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      80,
                                      81,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      323,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      96,
                                      97,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      148,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      103,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      104,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      127,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      514,
                                      MMDB_RECORD_TYPE_DATA,
                                  },
                                  {
                                      132,
                                      527,
                                      MMDB_RECORD_TYPE_DATA,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                  },
                                  {
                                      241,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      242,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  }};
    run_read_node_tests(mmdb, tests, 7, 28);

    MMDB_close(mmdb);
    free(mmdb);
}

void run_32_bit_record_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-mixed-32.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const uint32_t tests[7][5] = {{
                                      0,
                                      1,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      435,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      80,
                                      81,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      323,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      96,
                                      97,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                      148,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      103,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      104,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  },
                                  {
                                      127,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      514,
                                      MMDB_RECORD_TYPE_DATA,
                                  },
                                  {
                                      132,
                                      527,
                                      MMDB_RECORD_TYPE_DATA,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                  },
                                  {
                                      241,
                                      444,
                                      MMDB_RECORD_TYPE_EMPTY,
                                      242,
                                      MMDB_RECORD_TYPE_SEARCH_NODE,
                                  }};

    run_read_node_tests(mmdb, tests, 7, 32);

    MMDB_close(mmdb);
    free(mmdb);
}

void run_tests(int mode, const char *mode_desc) {
    run_24_bit_record_tests(mode, mode_desc);
    run_28_bit_record_tests(mode, mode_desc);
    run_32_bit_record_tests(mode, mode_desc);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
}
