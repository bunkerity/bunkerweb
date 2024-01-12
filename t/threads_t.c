#include "maxminddb_test_helper.h"
#include <pthread.h>

typedef struct thread_arg {
    int thread_id;
    MMDB_s *mmdb;
    const char *ip_to_lookup;
} thread_arg_s;

typedef struct test_result {
    const char *ip_looked_up;
    int lookup_string_gai_error;
    int lookup_string_mmdb_error;
    int found_entry;
    int get_value_status;
    int data_type_ok;
    char *data_value;
} test_result_s;

void test_one_ip(MMDB_s *mmdb, const char *ip, test_result_s *test_result) {

    test_result->ip_looked_up = ip;

    int gai_error = 0;
    int mmdb_error = 0;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(mmdb, ip, &gai_error, &mmdb_error);

    test_result->lookup_string_gai_error = gai_error;
    if (gai_error) {
        return;
    }

    test_result->lookup_string_mmdb_error = mmdb_error;
    if (mmdb_error) {
        return;
    }

    test_result->found_entry = result.found_entry;
    if (!result.found_entry) {
        return;
    }

    MMDB_entry_data_s data;
    int status = MMDB_get_value(&result.entry, &data, "ip", NULL);

    test_result->get_value_status = status;
    if (status) {
        return;
    }

    test_result->data_type_ok = data.type == MMDB_DATA_TYPE_UTF8_STRING;
    if (!test_result->data_type_ok) {
        return;
    }

    test_result->data_value = mmdb_strndup(data.utf8_string, data.data_size);

    return;
}

void *run_one_thread(void *arg) {
    thread_arg_s *thread_arg = (thread_arg_s *)arg;

    MMDB_s *mmdb = thread_arg->mmdb;
    const char *ip = thread_arg->ip_to_lookup;

    test_result_s *result = malloc(sizeof(test_result_s));
    if (!result) {
        BAIL_OUT("could not allocate memory");
    }
    test_one_ip(mmdb, ip, result);

    pthread_exit((void *)result);
}

void process_result(test_result_s *result,
                    const char *expect,
                    const char *mode_desc) {
    int is_ok;
    is_ok = ok(!result->lookup_string_gai_error,
               "no getaddrinfo error for %s - %s",
               result->ip_looked_up,
               mode_desc);
    if (!is_ok) {
        return;
    }

    is_ok = ok(!result->lookup_string_mmdb_error,
               "no mmdb error for %s - %s",
               result->ip_looked_up,
               mode_desc);
    if (!is_ok) {
        return;
    }

    is_ok = ok(result->found_entry,
               "got a result for %s in the database - %s",
               result->ip_looked_up,
               mode_desc);
    if (!is_ok) {
        return;
    }

    is_ok = ok(!result->get_value_status,
               "no error from MMDB_get_value for %s - %s",
               result->ip_looked_up,
               mode_desc);
    if (!is_ok) {
        return;
    }

    is_ok = ok(result->data_type_ok,
               "MMDB_get_value found a utf8_string at 'ip' key for %s - %s",
               result->ip_looked_up,
               mode_desc);
    if (!is_ok) {
        return;
    }

    is(result->data_value,
       expect,
       "found expected result for 'ip' key for %s - %s",
       result->ip_looked_up,
       mode_desc);
}

void run_ipX_tests(MMDB_s *mmdb,
                   const char *pairs[][2],
                   int pairs_rows,
                   const char *mode_desc) {
    pthread_t *threads = malloc((unsigned long)pairs_rows * sizeof(pthread_t));
    struct thread_arg *thread_args =
        malloc((unsigned long)pairs_rows * sizeof(struct thread_arg));

    for (int i = 0; i < pairs_rows; i += 1) {
        thread_args[i].thread_id = i;
        thread_args[i].mmdb = mmdb;
        thread_args[i].ip_to_lookup = pairs[i][0];

        int error =
            pthread_create(&threads[i], NULL, run_one_thread, &thread_args[i]);
        if (error) {
            BAIL_OUT("pthread_create failed");
        }
    }

    for (int i = 0; i < pairs_rows; i += 1) {
        void *thread_return;
        int error = pthread_join(threads[i], &thread_return);
        if (error) {
            BAIL_OUT("pthread_join failed");
        }

        test_result_s *test_result = (test_result_s *)thread_return;
        if (NULL != test_result) {
            process_result(test_result, pairs[i][1], mode_desc);
            if (test_result->data_type_ok) {
                free(test_result->data_value);
            }
            free(test_result);
        }
    }

    free(threads);
    free(thread_args);
}

void run_tests(int mode, const char *mode_desc) {
    const char *filename = "MaxMind-DB-test-mixed-32.mmdb";
    char *path = test_database_path(filename);
    MMDB_s *mmdb = open_ok(path, mode, mode_desc);
    free(path);

    const char *pairs[18][2] = {
        {"1.1.1.1", "::1.1.1.1"},
        {"1.1.1.2", "::1.1.1.2"},
        {"1.1.1.3", "::1.1.1.2"},
        {"1.1.1.7", "::1.1.1.4"},
        {"1.1.1.9", "::1.1.1.8"},
        {"1.1.1.15", "::1.1.1.8"},
        {"1.1.1.17", "::1.1.1.16"},
        {"1.1.1.31", "::1.1.1.16"},
        {"1.1.1.32", "::1.1.1.32"},
        {"::1:ffff:ffff", "::1:ffff:ffff"},
        {"::2:0:0", "::2:0:0"},
        {"::2:0:1a", "::2:0:0"},
        {"::2:0:40", "::2:0:40"},
        {"::2:0:4f", "::2:0:40"},
        {"::2:0:50", "::2:0:50"},
        {"::2:0:52", "::2:0:50"},
        {"::2:0:58", "::2:0:58"},
        {"::2:0:59", "::2:0:58"},
    };

    run_ipX_tests(mmdb, pairs, 18, mode_desc);

    MMDB_close(mmdb);
    free(mmdb);
}

int main(void) {
    plan(NO_PLAN);
    for_all_modes(&run_tests);
    done_testing();
    pthread_exit(NULL);
}
