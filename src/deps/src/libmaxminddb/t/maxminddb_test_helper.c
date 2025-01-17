#include "maxminddb_test_helper.h"

#if HAVE_CONFIG_H
#include <config.h>
#endif

#include <assert.h>
#include <stdarg.h>
#include <sys/types.h>

#include "maxminddb.h"

#ifdef _WIN32
#include <io.h>
#else
#include <libgen.h>
#include <unistd.h>
#endif

void for_all_record_sizes(const char *filename_fmt,
                          void (*tests)(int record_size,
                                        const char *filename,
                                        const char *description)) {
    int sizes[] = {24, 28, 32};
    for (int i = 0; i < 3; i++) {
        int size = sizes[i];

        char filename[500];
#if defined(__clang__)
// This warning seems ok to ignore here in the tests.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wformat-nonliteral"
#endif
        snprintf(filename, 500, filename_fmt, size);
#if defined(__clang__)
#pragma clang diagnostic pop
#endif

        char description[14];
        snprintf(description, 14, "%i bit record", size);

        tests(size, filename, description);
    }
}

void for_all_modes(void (*tests)(int mode, const char *description)) {
    tests(MMDB_MODE_MMAP, "mmap mode");
}

char *test_database_path(const char *filename) {
    char *test_db_dir;
#ifdef _WIN32
    test_db_dir = "../t/maxmind-db/test-data";
#else
    char cwd[500];
    char *UNUSED(tmp) = getcwd(cwd, 500);

    if (strcmp(basename(cwd), "t") == 0) {
        test_db_dir = "./maxmind-db/test-data";
    } else {
        test_db_dir = "./t/maxmind-db/test-data";
    }
#endif

    char *path = malloc(500);
    assert(NULL != path);

    snprintf(path, 500, "%s/%s", test_db_dir, filename);

    return path;
}

char *dup_entry_string_or_bail(MMDB_entry_data_s entry_data) {
    char *string = mmdb_strndup(entry_data.utf8_string, entry_data.data_size);
    if (NULL == string) {
        BAIL_OUT("mmdb_strndup failed");
    }

    return string;
}

MMDB_s *open_ok(const char *db_file, int mode, const char *mode_desc) {
#ifdef _WIN32
    int access_rv = _access(db_file, 04);
#else
    int access_rv = access(db_file, R_OK);
#endif
    if (access_rv != 0) {
        BAIL_OUT("could not read the specified file - %s\nIf you are in a git "
                 "checkout try running 'git submodule update --init'",
                 db_file);
    }

    MMDB_s *mmdb = (MMDB_s *)calloc(1, sizeof(MMDB_s));

    if (NULL == mmdb) {
        BAIL_OUT("could not allocate memory for our MMDB_s struct");
    }

    int status = MMDB_open(db_file, (uint32_t)mode, mmdb);

    int is_ok = ok(MMDB_SUCCESS == status,
                   "open %s status is success - %s",
                   db_file,
                   mode_desc);

    if (!is_ok) {
        diag("open status code = %d (%s)", status, MMDB_strerror(status));
        free(mmdb);
        return NULL;
    }

    is_ok = ok(mmdb->file_size > 0,
               "mmdb struct has been set for %s - %s",
               db_file,
               mode_desc);

    if (!is_ok) {
        free(mmdb);
        return NULL;
    }

    return mmdb;
}

MMDB_lookup_result_s lookup_string_ok(MMDB_s *mmdb,
                                      const char *ip,
                                      const char *file,
                                      const char *mode_desc) {
    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(mmdb, ip, &gai_error, &mmdb_error);

    test_lookup_errors(
        gai_error, mmdb_error, "MMDB_lookup_string", ip, file, mode_desc);

    return result;
}

MMDB_lookup_result_s lookup_sockaddr_ok(MMDB_s *mmdb,
                                        const char *ip,
                                        const char *file,
                                        const char *mode_desc) {
    int ai_flags = AI_NUMERICHOST;
    struct addrinfo hints = {.ai_socktype = SOCK_STREAM};
    struct addrinfo *addresses = NULL;

    if (ip[0] == ':') {
        hints.ai_flags = ai_flags;
#if defined AI_V4MAPPED && !defined __FreeBSD__
        hints.ai_flags |= AI_V4MAPPED;
#endif
        hints.ai_family = AF_INET6;
    } else {
        hints.ai_flags = ai_flags;
        hints.ai_family = AF_INET;
    }

    int gai_error = getaddrinfo(ip, NULL, &hints, &addresses);

    int mmdb_error = 0;
    MMDB_lookup_result_s result = {.found_entry = false};
    if (gai_error == 0) {
        result = MMDB_lookup_sockaddr(mmdb, addresses->ai_addr, &mmdb_error);
    }
    if (NULL != addresses) {
        freeaddrinfo(addresses);
    }

    test_lookup_errors(
        gai_error, mmdb_error, "MMDB_lookup_sockaddr", ip, file, mode_desc);

    return result;
}

void test_lookup_errors(int gai_error,
                        int mmdb_error,
                        const char *function,
                        const char *ip,
                        const char *file,
                        const char *mode_desc) {

    int is_ok = ok(0 == gai_error,
                   "no getaddrinfo error in call to %s for %s - %s - %s",
                   function,
                   ip,
                   file,
                   mode_desc);

    if (!is_ok) {
        diag("error from call to getaddrinfo for %s - %s",
             ip,
             gai_strerror(gai_error));
    }

    is_ok = ok(0 == mmdb_error,
               "no MMDB error in call to %s for %s - %s - %s",
               function,
               ip,
               file,
               mode_desc);

    if (!is_ok) {
        diag("MMDB error - %s", MMDB_strerror(mmdb_error));
    }
}

MMDB_entry_data_s data_ok(MMDB_lookup_result_s *result,
                          uint32_t expect_type,
                          const char *description,
                          ...) {
    va_list keys;
    va_start(keys, description);

    MMDB_entry_data_s data;
    int status = MMDB_vget_value(&result->entry, &data, keys);

    va_end(keys);

    if (cmp_ok(status,
               "==",
               MMDB_SUCCESS,
               "no error from call to MMDB_vget_value - %s",
               description)) {

        if (!cmp_ok((int)data.type,
                    "==",
                    (int)expect_type,
                    "got the expected data type - %s",
                    description)) {

            diag("  data type value is %i but expected %i",
                 data.type,
                 expect_type);
        }
    } else {
        diag("  error from MMDB_vget_value - %s", MMDB_strerror(status));
    }

    return data;
}

void compare_double(double got, double expect) {
    double diff = fabs(got - expect);
    int is_ok = ok(diff < 0.01, "double value was approximately %2.6f", expect);
    if (!is_ok) {
        diag(
            "  got %2.6f but expected %2.6f (diff = %2.6f)", got, expect, diff);
    }
}

void compare_float(float got, float expect) {
    float diff = fabsf(got - expect);
    int is_ok = ok(diff < 0.01, "float value was approximately %2.1f", expect);
    if (!is_ok) {
        diag(
            "  got %2.4f but expected %2.1f (diff = %2.1f)", got, expect, diff);
    }
}
