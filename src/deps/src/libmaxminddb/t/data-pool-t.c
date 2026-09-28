#include "libtap/tap.h"
#include "maxminddb_test_helper.h"
#include <assert.h>
#include <data-pool.h>
#include <inttypes.h>
#include <math.h>

static void test_data_pool_new(void);
static void test_data_pool_destroy(void);
static void test_data_pool_alloc(void);
static void test_data_pool_to_list(void);
static bool create_and_check_list(size_t const, size_t const);
static void check_block_count(MMDB_entry_data_list_s const *const,
                              size_t const);

int main(void) {
    plan(NO_PLAN);
    test_data_pool_new();
    test_data_pool_destroy();
    test_data_pool_alloc();
    test_data_pool_to_list();
    done_testing();
}

static void test_data_pool_new(void) {
    {
        MMDB_data_pool_s *const pool = data_pool_new(0, 512);
        ok(!pool, "size 0 is not valid");
    }

    {
        MMDB_data_pool_s *const pool = data_pool_new(SIZE_MAX - 10, SIZE_MAX);
        ok(!pool, "very large size is not valid");
    }

    {
        MMDB_data_pool_s *const pool = data_pool_new(512, 1024);
        ok(pool != NULL, "size 512 is valid");
        cmp_ok(pool->size, "==", 512, "size is 512");
        cmp_ok(pool->used, "==", 0, "used size is 0");
        cmp_ok(pool->capacity, "==", 512, "capacity is 512");
        cmp_ok(pool->max_size, "==", 1024, "maximum size is 1024");
        data_pool_destroy(pool);
    }

    {
        MMDB_data_pool_s *const pool = data_pool_new(512, 10);
        ok(pool != NULL, "maximum smaller than initial size is valid");
        cmp_ok(pool->size, "==", 10, "initial size is clamped to maximum");
        cmp_ok(pool->capacity, "==", 10, "capacity is clamped to maximum");
        data_pool_destroy(pool);
    }
}

static void test_data_pool_destroy(void) {
    {
        data_pool_destroy(NULL);
    }

    {
        MMDB_data_pool_s *const pool = data_pool_new(512, 512);
        ok(pool != NULL, "created pool");
        data_pool_destroy(pool);
    }
}

static void test_data_pool_alloc(void) {
    {
        MMDB_data_pool_s *const pool = data_pool_new(1, 3);
        ok(pool != NULL, "created pool");
        cmp_ok(pool->used, "==", 0, "used size starts at 0");

        MMDB_entry_data_list_s *const entry1 = data_pool_alloc(pool);
        ok(entry1 != NULL, "allocated first entry");
        // Arbitrary so that we can recognize it.
        entry1->entry_data.offset = (uint32_t)123;

        cmp_ok(pool->size, "==", 1, "size is still 1");
        cmp_ok(pool->used, "==", 1, "used size is 1 after taking one");

        MMDB_entry_data_list_s *const entry2 = data_pool_alloc(pool);
        ok(entry2 != NULL, "got another entry");
        ok(entry1 != entry2, "second entry is different from first entry");

        cmp_ok(pool->size, "==", 2, "size is 2 (new block)");
        cmp_ok(pool->used, "==", 1, "used size is 1 in current block");

        MMDB_entry_data_list_s *const entry3 = data_pool_alloc(pool);
        ok(entry3 != NULL, "got the final allowed entry");
        ok(data_pool_alloc(pool) == NULL,
           "allocation past maximum capacity is rejected");
        cmp_ok(pool->capacity, "==", 3, "capacity does not exceed maximum");

        ok(entry1->entry_data.offset == 123,
           "accessing the original entry's memory is ok");

        data_pool_destroy(pool);
    }

    {
        size_t const initial_size = 10;
        MMDB_data_pool_s *const pool =
            data_pool_new(initial_size, initial_size * 3);
        ok(pool != NULL, "created pool");

        MMDB_entry_data_list_s *entry1 = NULL;
        for (size_t i = 0; i < initial_size; i++) {
            MMDB_entry_data_list_s *const entry = data_pool_alloc(pool);
            ok(entry != NULL, "got an entry");
            // Give each a unique number so we can check it.
            entry->entry_data.offset = (uint32_t)i;
            if (i == 0) {
                entry1 = entry;
            }
        }

        cmp_ok(pool->size, "==", initial_size, "size is the initial size");
        cmp_ok(pool->used, "==", initial_size, "used size is as expected");

        MMDB_entry_data_list_s *const entry = data_pool_alloc(pool);
        ok(entry != NULL, "got an entry");
        entry->entry_data.offset = (uint32_t)initial_size;

        cmp_ok(
            pool->size, "==", initial_size * 2, "size is the initial size*2");
        cmp_ok(pool->used, "==", 1, "used size is as expected");

        MMDB_entry_data_list_s *const list = data_pool_to_list(pool);

        MMDB_entry_data_list_s *element = list;
        for (size_t i = 0; i < initial_size + 1; i++) {
            ok(element->entry_data.offset == (uint32_t)i,
               "found offset %" PRIu32 ", should have %zu",
               element->entry_data.offset,
               i);
            element = element->next;
        }

        ok(entry1->entry_data.offset == (uint32_t)0,
           "accessing entry1's original memory is ok after growing the pool");

        data_pool_destroy(pool);
    }

    {
        size_t const maximum_size = 65536;
        MMDB_data_pool_s *const pool = data_pool_new(64, maximum_size);
        ok(pool != NULL, "created a decoder-sized pool");
        for (size_t i = 0; i < maximum_size; i++) {
            MMDB_entry_data_list_s *const entry = data_pool_alloc(pool);
            assert(entry != NULL);
            (void)entry;
        }
        cmp_ok(pool->capacity,
               "==",
               maximum_size,
               "final block is clamped to the remaining capacity");
        cmp_ok(pool->sizes[pool->index],
               "==",
               64,
               "the clamped final block reserves only 64 entries");
        ok(data_pool_alloc(pool) == NULL,
           "decoder-sized pool refuses a 65,537th entry");
        data_pool_destroy(pool);
    }
}

static void test_data_pool_to_list(void) {
    {
        size_t const initial_size = 16;
        MMDB_data_pool_s *const pool =
            data_pool_new(initial_size, initial_size);
        ok(pool != NULL, "created pool");

        MMDB_entry_data_list_s *const entry1 = data_pool_alloc(pool);
        ok(entry1 != NULL, "got an entry");

        MMDB_entry_data_list_s *const list_one_element =
            data_pool_to_list(pool);
        ok(list_one_element != NULL, "got a list");
        ok(list_one_element == entry1,
           "list's first element is the first we retrieved");
        ok(list_one_element->next == NULL, "list is one element in size");

        MMDB_entry_data_list_s *const entry2 = data_pool_alloc(pool);
        ok(entry2 != NULL, "got another entry");

        MMDB_entry_data_list_s *const list_two_elements =
            data_pool_to_list(pool);
        ok(list_two_elements != NULL, "got a list");
        ok(list_two_elements == entry1,
           "list's first element is the first we retrieved");
        ok(list_two_elements->next != NULL, "list has a second element");

        MMDB_entry_data_list_s *const second_element = list_two_elements->next;
        ok(second_element == entry2,
           "second item in list is second we retrieved");
        ok(second_element->next == NULL, "list ends with the second element");

        data_pool_destroy(pool);
    }

    {
        size_t const initial_size = 1;
        MMDB_data_pool_s *const pool =
            data_pool_new(initial_size, initial_size);
        ok(pool != NULL, "created pool");

        MMDB_entry_data_list_s *const entry1 = data_pool_alloc(pool);
        ok(entry1 != NULL, "got an entry");

        MMDB_entry_data_list_s *const list_one_element =
            data_pool_to_list(pool);
        ok(list_one_element != NULL, "got a list");
        ok(list_one_element == entry1,
           "list's first element is the first we retrieved");
        ok(list_one_element->next == NULL, "list ends with this element");

        data_pool_destroy(pool);
    }

    {
        size_t const initial_size = 2;
        MMDB_data_pool_s *const pool =
            data_pool_new(initial_size, initial_size);
        ok(pool != NULL, "created pool");

        MMDB_entry_data_list_s *const entry1 = data_pool_alloc(pool);
        ok(entry1 != NULL, "got an entry");

        MMDB_entry_data_list_s *const entry2 = data_pool_alloc(pool);
        ok(entry2 != NULL, "got an entry");
        ok(entry1 != entry2, "second entry is different from the first");

        MMDB_entry_data_list_s *const list_element1 = data_pool_to_list(pool);
        ok(list_element1 != NULL, "got a list");
        ok(list_element1 == entry1,
           "list's first element is the first we retrieved");

        MMDB_entry_data_list_s *const list_element2 = list_element1->next;
        ok(list_element2 == entry2,
           "second element is the second we retrieved");
        ok(list_element2->next == NULL, "list ends with this element");

        data_pool_destroy(pool);
    }

    {
        diag("starting test: fill one block save for one spot");
        ok(create_and_check_list(3, 2), "fill one block save for one spot");
    }

    {
        diag("starting test: fill one block");
        ok(create_and_check_list(3, 3), "fill one block");
    }

    {
        diag(
            "starting test: fill one block and use one spot in the next block");
        ok(create_and_check_list(3, 3 + 1),
           "fill one block and use one spot in the next block");
    }

    {
        diag("starting test: fill two blocks save for one spot");
        ok(create_and_check_list(3, 3 + 3 * 2 - 1),
           "fill two blocks save for one spot");
    }

    {
        diag("starting test: fill two blocks");
        ok(create_and_check_list(3, 3 + 3 * 2), "fill two blocks");
    }

    {
        diag("starting test: fill two blocks and use one spot in the next");
        ok(create_and_check_list(3, 3 + 3 * 2 + 1),
           "fill two blocks and use one spot in the next");
    }

    {
        diag("starting test: fill three blocks save for one spot");
        ok(create_and_check_list(3, 3 + 3 * 2 + 3 * 2 * 2 - 1),
           "fill three blocks save for one spot");
    }

    {
        diag("starting test: fill three blocks");
        ok(create_and_check_list(3, 3 + 3 * 2 + 3 * 2 * 2),
           "fill three blocks");
    }

    // It would be nice to have a larger number of these, but it's expensive to
    // run many. We currently hardcode what this will be anyway, so varying
    // this is not very interesting.
    size_t const initial_sizes[] = {1, 2, 32, 64, 128, 256};

    size_t const max_element_count = 4096;

    for (size_t i = 0; i < sizeof(initial_sizes) / sizeof(initial_sizes[0]);
         i++) {
        size_t const initial_size = initial_sizes[i];

        for (size_t element_count = 0; element_count < max_element_count;
             element_count++) {
            assert(create_and_check_list(initial_size, element_count));
        }
    }
}

// Use assert() rather than libtap as libtap is significantly slower and we run
// this frequently.
static bool create_and_check_list(size_t const initial_size,
                                  size_t const element_count) {
    size_t max_size = initial_size;
    if (element_count > initial_size) {
        max_size = element_count;
    }
    MMDB_data_pool_s *const pool = data_pool_new(initial_size, max_size);
    assert(pool != NULL);

    assert(pool->used == 0);

    // Hold on to the pointers as we initially see them so that we can check
    // they are still valid after building the list.
    MMDB_entry_data_list_s **const entry_array =
        calloc(element_count, sizeof(MMDB_entry_data_list_s *));
    assert(entry_array != NULL);

    for (size_t i = 0; i < element_count; i++) {
        MMDB_entry_data_list_s *const entry = data_pool_alloc(pool);
        assert(entry != NULL);

        entry->entry_data.offset = (uint32_t)i;

        entry_array[i] = entry;
    }

    MMDB_entry_data_list_s *const list = data_pool_to_list(pool);

    if (element_count == 0) {
        assert(list == NULL);
        data_pool_destroy(pool);
        free(entry_array);
        return true;
    }

    assert(list != NULL);

    MMDB_entry_data_list_s *element = list;
    for (size_t i = 0; i < element_count; i++) {
        assert(element->entry_data.offset == (uint32_t)i);

        assert(element == entry_array[i]);

        element = element->next;
    }
    assert(element == NULL);

    check_block_count(list, initial_size);

    data_pool_destroy(pool);
    free(entry_array);
    return true;
}

// Use assert() rather than libtap as libtap is significantly slower and we run
// this frequently.
static void check_block_count(MMDB_entry_data_list_s const *const list,
                              size_t const initial_size) {
    size_t got_block_count = 0;
    size_t got_element_count = 0;

    MMDB_entry_data_list_s const *element = list;
    while (element) {
        got_element_count++;

        if (element->pool) {
            got_block_count++;
        }

        element = element->next;
    }

    // Because <number of elements> = <initial size> * 2^(number of blocks)
    double const a = ceil((double)got_element_count / (double)initial_size);
    double const b = log2(a);
    size_t const expected_block_count = ((size_t)b) + 1;

    assert(got_block_count == expected_block_count);
}
