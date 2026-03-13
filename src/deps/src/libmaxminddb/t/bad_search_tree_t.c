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

int main(void) {
    plan(NO_PLAN);
    test_read_node_bounds();
    done_testing();
}
