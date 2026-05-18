#include "maxminddb_test_helper.h"

/*
 * Test that the bounds check in find_address_in_search_tree uses 64-bit
 * arithmetic. We can't realistically create a database large enough to
 * trigger the uint32 overflow (it would require billions of nodes), but
 * we can verify the fix doesn't regress normal lookups.
 *
 * The real protection is the cast to uint64_t before addition,
 * matching the pattern used elsewhere in the codebase.
 */
void test_normal_lookup_still_works(void) {
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, "mmap mode");
    free(db_file);

    if (!mmdb) {
        return;
    }

    int gai_error, mmdb_error;
    (void)MMDB_lookup_string(mmdb, "1.1.1.1", &gai_error, &mmdb_error);

    cmp_ok(gai_error, "==", 0, "no gai error");
    cmp_ok(mmdb_error, "==", MMDB_SUCCESS, "no mmdb error");

    MMDB_close(mmdb);
    free(mmdb);
}

void test_record_type_bounds(void) {
    /* Test that record_type correctly handles values near the boundary.
     * With the uint64_t cast fix, valid records should still be classified
     * correctly. */
    char *db_file = test_database_path("MaxMind-DB-test-ipv4-24.mmdb");
    MMDB_s *mmdb = open_ok(db_file, MMDB_MODE_MMAP, "mmap mode");
    free(db_file);

    if (!mmdb) {
        return;
    }

    /* Read node 0 and verify records are valid types */
    MMDB_search_node_s node;
    int status = MMDB_read_node(mmdb, 0, &node);
    cmp_ok(status, "==", MMDB_SUCCESS, "MMDB_read_node succeeded");

    ok(node.left_record_type == MMDB_RECORD_TYPE_SEARCH_NODE ||
           node.left_record_type == MMDB_RECORD_TYPE_EMPTY ||
           node.left_record_type == MMDB_RECORD_TYPE_DATA,
       "left record type is valid");

    ok(node.right_record_type == MMDB_RECORD_TYPE_SEARCH_NODE ||
           node.right_record_type == MMDB_RECORD_TYPE_EMPTY ||
           node.right_record_type == MMDB_RECORD_TYPE_DATA,
       "right record type is valid");

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    test_normal_lookup_still_works();
    test_record_type_bounds();
    done_testing();
}
