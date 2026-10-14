#include "maxminddb_test_helper.h"

/*
 * Test the off-by-one fix in MMDB_read_node: node_number >= node_count
 * must return MMDB_INVALID_NODE_NUMBER_ERROR. Previously the check used
 * >, allowing node_number == node_count to read past the tree.
 */
void test_read_node_bounds(void) {
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, "mmap mode");
    free(db_file);

    if (!mmdb) {
        return;
    }

    MMDB_search_node_s node;

    /* node_count - 1 is the last valid node */
    int status = MMDB_read_node(mmdb, mmdb->metadata.node_count - 1, &node);
    cmp_ok(status,
           "==",
           MMDB_SUCCESS,
           "MMDB_read_node succeeds for last valid node");

    /* node_count itself is out of bounds (the off-by-one fix) */
    status = MMDB_read_node(mmdb, mmdb->metadata.node_count, &node);
    cmp_ok(status,
           "==",
           MMDB_INVALID_NODE_NUMBER_ERROR,
           "MMDB_read_node rejects node_number == node_count");

    /* node_count + 1 is also out of bounds */
    status = MMDB_read_node(mmdb, mmdb->metadata.node_count + 1, &node);
    cmp_ok(status,
           "==",
           MMDB_INVALID_NODE_NUMBER_ERROR,
           "MMDB_read_node rejects node_number > node_count");

    MMDB_close(mmdb);
    free(mmdb);
}

// Open a pre-built corruption fixture and assert that all rejection paths
// fire. `lookup_ip` must traverse the corrupted record from node 0 — high
// bit 0 for a corrupted left record, 1 for a corrupted right record.
static void check_corrupt_record(const char *label,
                                 const char *fixture,
                                 const char *lookup_ip) {
    char *db_file = bad_database_path(fixture);
    MMDB_s mmdb;
    int status = MMDB_open(db_file, MMDB_MODE_MMAP, &mmdb);
    cmp_ok(status, "==", MMDB_SUCCESS, "%s: opened crafted bad MMDB", label);
    if (status != MMDB_SUCCESS) {
        free(db_file);
        return;
    }

    MMDB_search_node_s node;
    status = MMDB_read_node(&mmdb, 0, &node);
    cmp_ok(status,
           "==",
           MMDB_CORRUPT_SEARCH_TREE_ERROR,
           "%s: MMDB_read_node rejects record as corrupt",
           label);

    int gai_error = 0;
    int mmdb_error = 0;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(&mmdb, lookup_ip, &gai_error, &mmdb_error);
    cmp_ok(gai_error, "==", 0, "%s: lookup string parse succeeds", label);
    cmp_ok(mmdb_error,
           "==",
           MMDB_CORRUPT_SEARCH_TREE_ERROR,
           "%s: MMDB_lookup_string rejects record",
           label);
    ok(!result.found_entry, "%s: lookup reports no entry", label);

    MMDB_close(&mmdb);
    free(db_file);
}

void test_separator_record_rejected(void) {
    // Records in the half-open range [node_count + 1, node_count + 16) point
    // into the 16-byte separator between the search tree and data section
    // and must be rejected as corrupt.
    check_corrupt_record("left record, first separator byte",
                         "libmaxminddb-separator-record-min-left.mmdb",
                         "1.1.1.1");
    check_corrupt_record("right record, first separator byte",
                         "libmaxminddb-separator-record-min-right.mmdb",
                         "128.0.0.0");
    check_corrupt_record("left record, last separator byte",
                         "libmaxminddb-separator-record-max-left.mmdb",
                         "1.1.1.1");
}

int main(void) {
    plan(NO_PLAN);
    test_read_node_bounds();
    test_separator_record_rejected();
    done_testing();
}
