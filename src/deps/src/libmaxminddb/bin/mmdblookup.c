#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include "maxminddb.h"
#include <errno.h>
#include <getopt.h>
#ifndef _WIN32
#include <pthread.h>
#endif
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#ifndef UNICODE
#define UNICODE
#endif
#include <malloc.h>
#else
#include <libgen.h>
#include <unistd.h>
#endif

static void usage(char *program, int exit_code, const char *error);
static const char **get_options(int argc,
                                char **argv,
                                char **mmdb_file,
                                char **ip_address,
                                int *verbose,
                                int *iterations,
                                int *lookup_path_length,
                                int *const thread_count,
                                char **const ip_file);
static MMDB_s open_or_die(const char *fname);
static void dump_meta(MMDB_s *mmdb);
static bool lookup_from_file(MMDB_s *const mmdb,
                             char const *const ip_file,
                             bool const dump);
static int lookup_and_print(MMDB_s *mmdb,
                            const char *ip_address,
                            const char **lookup_path,
                            int lookup_path_length,
                            bool verbose);
static int benchmark(MMDB_s *mmdb, int iterations);
static MMDB_lookup_result_s lookup_or_die(MMDB_s *mmdb, const char *ipstr);
static void random_ipv4(char *ip);

#ifndef _WIN32
// These aren't with the automatically generated prototypes as we'd lose the
// enclosing macros.
static bool start_threaded_benchmark(MMDB_s *const mmdb,
                                     int const thread_count,
                                     int const iterations);
static long double get_time(void);
static void *thread(void *arg);
#endif

#ifdef _WIN32
int wmain(int argc, wchar_t **wargv) {
    // Convert our argument list from UTF-16 to UTF-8.
    char **argv = (char **)calloc(argc, sizeof(char *));
    if (!argv) {
        fprintf(stderr, "calloc(): %s\n", strerror(errno));
        exit(1);
    }
    for (int i = 0; i < argc; i++) {
        int utf8_width;
        char *utf8_string;
        utf8_width =
            WideCharToMultiByte(CP_UTF8, 0, wargv[i], -1, NULL, 0, NULL, NULL);
        if (utf8_width < 1) {
            fprintf(
                stderr, "WideCharToMultiByte() failed: %d\n", GetLastError());
            exit(1);
        }
        utf8_string = calloc(utf8_width, sizeof(char));
        if (!utf8_string) {
            fprintf(stderr, "calloc(): %s\n", strerror(errno));
            exit(1);
        }
        if (WideCharToMultiByte(
                CP_UTF8, 0, wargv[i], -1, utf8_string, utf8_width, NULL, NULL) <
            1) {
            fprintf(
                stderr, "WideCharToMultiByte() failed: %d\n", GetLastError());
            exit(1);
        }
        argv[i] = utf8_string;
    }
#else  // _WIN32
int main(int argc, char **argv) {
#endif // _WIN32
    char *mmdb_file = NULL;
    char *ip_address = NULL;
    int verbose = 0;
    int iterations = 0;
    int lookup_path_length = 0;
    int thread_count = 0;
    char *ip_file = NULL;

    const char **lookup_path = get_options(argc,
                                           argv,
                                           &mmdb_file,
                                           &ip_address,
                                           &verbose,
                                           &iterations,
                                           &lookup_path_length,
                                           &thread_count,
                                           &ip_file);

    MMDB_s mmdb = open_or_die(mmdb_file);

    if (verbose) {
        dump_meta(&mmdb);
    }

    // The benchmarking and lookup from file modes are hidden features mainly
    // intended for development right now. This means there are several flags
    // that exist but are intentionally not mentioned in the usage or man page.

    // The lookup from file mode may be useful to expose publicly in the usage,
    // but we should have it respect the lookup_path functionality if we do so.
    if (ip_file) {
        free((void *)lookup_path);
        if (!lookup_from_file(&mmdb, ip_file, verbose == 1)) {
            MMDB_close(&mmdb);
            return 1;
        }
        MMDB_close(&mmdb);
        return 0;
    }

    if (0 == iterations) {
        exit(lookup_and_print(
            &mmdb, ip_address, lookup_path, lookup_path_length, verbose));
    }

    free((void *)lookup_path);

    srand((unsigned int)time(NULL));

#ifndef _WIN32
    if (thread_count > 0) {
        if (!start_threaded_benchmark(&mmdb, thread_count, iterations)) {
            MMDB_close(&mmdb);
            exit(1);
        }
        MMDB_close(&mmdb);
        exit(0);
    }
#endif

    exit(benchmark(&mmdb, iterations));
}

static void usage(char *program, int exit_code, const char *error) {
    if (NULL != error) {
        fprintf(stderr, "\n  *ERROR: %s\n", error);
    }

    char *usage =
        "\n"
        "  %s --file /path/to/file.mmdb --ip 1.2.3.4 [path to lookup]\n"
        "\n"
        "  This application accepts the following options:\n"
        "\n"
        "      --file (-f)     The path to the MMDB file. Required.\n"
        "\n"
        "      --ip (-i)       The IP address to look up. Required.\n"
        "\n"
        "      --verbose (-v)  Turns on verbose output. Specifically, this "
        "causes this\n"
        "                      application to output the database metadata.\n"
        "\n"
        "      --version       Print the program's version number and exit.\n"
        "\n"
        "      --help (-h -?)  Show usage information.\n"
        "\n"
        "  If an IP's data entry resolves to a map or array, you can provide\n"
        "  a lookup path to only show part of that data.\n"
        "\n"
        "  For example, given a JSON structure like this:\n"
        "\n"
        "    {\n"
        "        \"names\": {\n"
        "             \"en\": \"Germany\",\n"
        "             \"de\": \"Deutschland\"\n"
        "        },\n"
        "        \"cities\": [ \"Berlin\", \"Frankfurt\" ]\n"
        "    }\n"
        "\n"
        "  You could look up just the English name by calling mmdblookup with "
        "a lookup path of:\n"
        "\n"
        "    mmdblookup --file ... --ip ... names en\n"
        "\n"
        "  Or you could look up the second city in the list with:\n"
        "\n"
        "    mmdblookup --file ... --ip ... cities 1\n"
        "\n"
        "  Array numbering begins with zero (0).\n"
        "\n"
        "  If you do not provide a path to lookup, all of the information for "
        "a given IP\n"
        "  will be shown.\n"
        "\n";

    fprintf(stdout, usage, program);
    exit(exit_code);
}

static const char **get_options(int argc,
                                char **argv,
                                char **mmdb_file,
                                char **ip_address,
                                int *verbose,
                                int *iterations,
                                int *lookup_path_length,
                                int *const thread_count,
                                char **const ip_file) {
    static int help = 0;
    static int version = 0;

#ifdef _WIN32
    char *program = alloca(strlen(argv[0]));
    _splitpath(argv[0], NULL, NULL, program, NULL);
    _splitpath(argv[0], NULL, NULL, NULL, program + strlen(program));
#else
    char *program = basename(argv[0]);
#endif

    while (1) {
        static struct option options[] = {
            {"file", required_argument, 0, 'f'},
            {"ip", required_argument, 0, 'i'},
            {"verbose", no_argument, 0, 'v'},
            {"version", no_argument, 0, 'n'},
            {"benchmark", required_argument, 0, 'b'},
#ifndef _WIN32
            {"threads", required_argument, 0, 't'},
#endif
            {"ip-file", required_argument, 0, 'I'},
            {"help", no_argument, 0, 'h'},
            {"?", no_argument, 0, 1},
            {0, 0, 0, 0}};

        int opt_index;
#ifdef _WIN32
        char const *const optstring = "f:i:b:I:vnh?";
#else
        char const *const optstring = "f:i:b:t:I:vnh?";
#endif
        int opt_char = getopt_long(argc, argv, optstring, options, &opt_index);

        if (-1 == opt_char) {
            break;
        }

        if ('f' == opt_char) {
            *mmdb_file = optarg;
        } else if ('i' == opt_char) {
            *ip_address = optarg;
        } else if ('v' == opt_char) {
            *verbose = 1;
        } else if ('n' == opt_char) {
            version = 1;
        } else if ('b' == opt_char) {
            long const i = strtol(optarg, NULL, 10);
            if (i > INT_MAX) {
                usage(program, 1, "iterations exceeds maximum value");
            }
            *iterations = (int)i;
        } else if ('h' == opt_char || '?' == opt_char) {
            help = 1;
        } else if (opt_char == 't') {
            long const i = strtol(optarg, NULL, 10);
            if (i > INT_MAX) {
                usage(program, 1, "thread count exceeds maximum value");
            }
            *thread_count = (int)i;
        } else if (opt_char == 'I') {
            *ip_file = optarg;
        }
    }

    if (help) {
        usage(program, 0, NULL);
    }

    if (version) {
        fprintf(stdout, "\n  %s version %s\n\n", program, PACKAGE_VERSION);
        exit(0);
    }

    if (NULL == *mmdb_file) {
        usage(program, 1, "You must provide a filename with --file");
    }

    if (*ip_address == NULL && *iterations == 0 && !*ip_file) {
        usage(program, 1, "You must provide an IP address with --ip");
    }

    const char **lookup_path =
        calloc((size_t)(argc - optind) + 1, sizeof(const char *));
    if (!lookup_path) {
        fprintf(stderr, "calloc(): %s\n", strerror(errno));
        exit(1);
    }
    int i;
    for (i = 0; i < argc - optind; i++) {
        lookup_path[i] = argv[i + optind];
        (*lookup_path_length)++;
    }
    lookup_path[i] = NULL;

    return lookup_path;
}

static MMDB_s open_or_die(const char *fname) {
    MMDB_s mmdb;
    int status = MMDB_open(fname, MMDB_MODE_MMAP, &mmdb);

    if (MMDB_SUCCESS != status) {
        fprintf(
            stderr, "\n  Can't open %s - %s\n", fname, MMDB_strerror(status));

        if (MMDB_IO_ERROR == status) {
            fprintf(stderr, "    IO error: %s\n", strerror(errno));
        }

        fprintf(stderr, "\n");

        exit(2);
    }

    return mmdb;
}

static void dump_meta(MMDB_s *mmdb) {
    const char *meta_dump = "\n"
                            "  Database metadata\n"
                            "    Node count:    %i\n"
                            "    Record size:   %i bits\n"
                            "    IP version:    IPv%i\n"
                            "    Binary format: %i.%i\n"
                            "    Build epoch:   %llu (%s)\n"
                            "    Type:          %s\n"
                            "    Languages:     ";

    char date[40];
    const time_t epoch = (const time_t)mmdb->metadata.build_epoch;
    strftime(date, 40, "%F %T UTC", gmtime(&epoch));

    fprintf(stdout,
            meta_dump,
            mmdb->metadata.node_count,
            mmdb->metadata.record_size,
            mmdb->metadata.ip_version,
            mmdb->metadata.binary_format_major_version,
            mmdb->metadata.binary_format_minor_version,
            mmdb->metadata.build_epoch,
            date,
            mmdb->metadata.database_type);

    for (size_t i = 0; i < mmdb->metadata.languages.count; i++) {
        fprintf(stdout, "%s", mmdb->metadata.languages.names[i]);
        if (i < mmdb->metadata.languages.count - 1) {
            fprintf(stdout, " ");
        }
    }
    fprintf(stdout, "\n");

    fprintf(stdout, "    Description:\n");
    for (size_t i = 0; i < mmdb->metadata.description.count; i++) {
        fprintf(stdout,
                "      %s:   %s\n",
                mmdb->metadata.description.descriptions[i]->language,
                mmdb->metadata.description.descriptions[i]->description);
    }
    fprintf(stdout, "\n");
}

// The input file should have one IP per line.
//
// We look up each IP.
//
// If dump is true, we dump the data for each IP to stderr. This is useful for
// comparison in that you can dump out the data for the IPs before and after
// making changes. It goes to stderr rather than stdout so that the report does
// not get included in what you will compare (since it will almost always be
// different).
//
// In addition to being useful for comparisons, this function provides a way to
// have a more deterministic set of lookups for benchmarking.
static bool lookup_from_file(MMDB_s *const mmdb,
                             char const *const ip_file,
                             bool const dump) {
    FILE *const fh = fopen(ip_file, "r");
    if (!fh) {
        fprintf(stderr, "fopen(): %s: %s\n", ip_file, strerror(errno));
        return false;
    }

    clock_t const clock_start = clock();
    char buf[1024] = {0};
    // I'd normally use uint64_t, but support for it is optional in C99.
    unsigned long long i = 0;
    while (1) {
        if (fgets(buf, sizeof(buf), fh) == NULL) {
            if (!feof(fh)) {
                fprintf(stderr, "fgets(): %s\n", strerror(errno));
                fclose(fh);
                return false;
            }
            if (fclose(fh) != 0) {
                fprintf(stderr, "fclose(): %s\n", strerror(errno));
                return false;
            }
            break;
        }

        char *ptr = buf;
        while (*ptr != '\0') {
            if (*ptr == '\n') {
                *ptr = '\0';
                break;
            }
            ptr++;
        }
        if (strlen(buf) == 0) {
            continue;
        }

        i++;

        MMDB_lookup_result_s result = lookup_or_die(mmdb, buf);
        if (!result.found_entry) {
            continue;
        }

        MMDB_entry_data_list_s *entry_data_list = NULL;
        int const status =
            MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        if (status != MMDB_SUCCESS) {
            fprintf(stderr,
                    "MMDB_get_entry_data_list(): %s\n",
                    MMDB_strerror(status));
            fclose(fh);
            MMDB_free_entry_data_list(entry_data_list);
            return false;
        }

        if (!entry_data_list) {
            fprintf(stderr, "entry_data_list is NULL\n");
            fclose(fh);
            return false;
        }

        if (dump) {
            fprintf(stdout, "%s:\n", buf);
            int const status2 =
                MMDB_dump_entry_data_list(stderr, entry_data_list, 0);
            if (status2 != MMDB_SUCCESS) {
                fprintf(stderr,
                        "MMDB_dump_entry_data_list(): %s\n",
                        MMDB_strerror(status2));
                fclose(fh);
                MMDB_free_entry_data_list(entry_data_list);
                return false;
            }
        }

        MMDB_free_entry_data_list(entry_data_list);
    }

    clock_t const clock_diff = clock() - clock_start;
    double const seconds = (double)clock_diff / CLOCKS_PER_SEC;

    fprintf(
        stdout,
        "Looked up %llu addresses in %.2f seconds. %.2Lf lookups per second.\n",
        i,
        seconds,
        (long double)i / seconds);

    return true;
}

static int lookup_and_print(MMDB_s *mmdb,
                            const char *ip_address,
                            const char **lookup_path,
                            int lookup_path_length,
                            bool verbose) {

    MMDB_lookup_result_s result = lookup_or_die(mmdb, ip_address);
    MMDB_entry_data_list_s *entry_data_list = NULL;

    int exit_code = 0;

    if (verbose) {
        fprintf(stdout, "\n  Record prefix length: %d\n", result.netmask);
    }

    if (result.found_entry) {
        int status;
        if (lookup_path_length) {
            MMDB_entry_data_s entry_data;
            status = MMDB_aget_value(&result.entry, &entry_data, lookup_path);
            if (MMDB_SUCCESS == status) {
                if (entry_data.offset) {
                    MMDB_entry_s entry = {.mmdb = mmdb,
                                          .offset = entry_data.offset};
                    status = MMDB_get_entry_data_list(&entry, &entry_data_list);
                } else {
                    fprintf(stdout,
                            "\n  No data was found at the lookup path you "
                            "provided\n\n");
                }
            }
        } else {
            status = MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        }

        if (MMDB_SUCCESS != status) {
            fprintf(stderr,
                    "Got an error looking up the entry data - %s\n",
                    MMDB_strerror(status));
            exit_code = 5;
            goto end;
        }

        if (NULL != entry_data_list) {
            fprintf(stdout, "\n");
            MMDB_dump_entry_data_list(stdout, entry_data_list, 2);
            fprintf(stdout, "\n");
        }
    } else {
        fprintf(stderr,
                "\n  Could not find an entry for this IP address (%s)\n\n",
                ip_address);
        exit_code = 6;
    }

end:
    MMDB_free_entry_data_list(entry_data_list);
    MMDB_close(mmdb);
    free((void *)lookup_path);

    return exit_code;
}

static int benchmark(MMDB_s *mmdb, int iterations) {
    char ip_address[16];
    int exit_code = 0;

    clock_t time = clock();

    for (int i = 0; i < iterations; i++) {
        random_ipv4(ip_address);

        MMDB_lookup_result_s result = lookup_or_die(mmdb, ip_address);
        MMDB_entry_data_list_s *entry_data_list = NULL;

        if (result.found_entry) {

            int status =
                MMDB_get_entry_data_list(&result.entry, &entry_data_list);

            if (MMDB_SUCCESS != status) {
                fprintf(stderr,
                        "Got an error looking up the entry data - %s\n",
                        MMDB_strerror(status));
                exit_code = 5;
                MMDB_free_entry_data_list(entry_data_list);
                goto end;
            }
        }

        MMDB_free_entry_data_list(entry_data_list);
    }

    time = clock() - time;
    double seconds = ((double)time / CLOCKS_PER_SEC);
    fprintf(stdout,
            "\n  Looked up %i addresses in %.2f seconds. %.2f lookups per "
            "second.\n\n",
            iterations,
            seconds,
            iterations / seconds);

end:
    MMDB_close(mmdb);

    return exit_code;
}

static MMDB_lookup_result_s lookup_or_die(MMDB_s *mmdb, const char *ipstr) {
    int gai_error, mmdb_error;
    MMDB_lookup_result_s result =
        MMDB_lookup_string(mmdb, ipstr, &gai_error, &mmdb_error);

    if (0 != gai_error) {
#ifdef _WIN32
        char const *const strerr = gai_strerrorA(gai_error);
#else
        char const *const strerr = gai_strerror(gai_error);
#endif
        fprintf(stderr,
                "\n  Error from call to getaddrinfo for %s - %s\n\n",
                ipstr,
                strerr);
        exit(3);
    }

    if (MMDB_SUCCESS != mmdb_error) {
        fprintf(stderr,
                "\n  Got an error from the maxminddb library: %s\n\n",
                MMDB_strerror(mmdb_error));
        exit(4);
    }

    return result;
}

static void random_ipv4(char *ip) {
    // rand() is perfectly fine for this use case
    // coverity[dont_call]
    int ip_int = rand();
    uint8_t *bytes = (uint8_t *)&ip_int;

    snprintf(ip,
             16,
             "%u.%u.%u.%u",
             *bytes,
             *(bytes + 1),
             *(bytes + 2),
             *(bytes + 3));
}

#ifndef _WIN32
struct thread_info {
    pthread_t id;
    int num;
    MMDB_s *mmdb;
    int iterations;
};

static bool start_threaded_benchmark(MMDB_s *const mmdb,
                                     int const thread_count,
                                     int const iterations) {
    struct thread_info *const tinfo =
        calloc((size_t)thread_count, sizeof(struct thread_info));
    if (!tinfo) {
        fprintf(stderr, "calloc(): %s\n", strerror(errno));
        return false;
    }

    // Using clock() isn't appropriate for multiple threads. It's CPU time, not
    // wall time.
    long double const start_time = get_time();
    if (start_time == -1) {
        free(tinfo);
        return false;
    }

    for (int i = 0; i < thread_count; i++) {
        tinfo[i].num = i;
        tinfo[i].mmdb = mmdb;
        tinfo[i].iterations = iterations;

        if (pthread_create(&tinfo[i].id, NULL, &thread, &tinfo[i]) != 0) {
            fprintf(stderr, "pthread_create() failed\n");
            free(tinfo);
            return false;
        }
    }

    for (int i = 0; i < thread_count; i++) {
        if (pthread_join(tinfo[i].id, NULL) != 0) {
            fprintf(stderr, "pthread_join() failed\n");
            free(tinfo);
            return false;
        }
    }

    free(tinfo);

    long double const end_time = get_time();
    if (end_time == -1) {
        return false;
    }

    long double const elapsed = end_time - start_time;
    unsigned long long const total_ips =
        (unsigned long long)(iterations * thread_count);
    long double rate = total_ips;
    if (elapsed != 0) {
        rate = total_ips / elapsed;
    }

    fprintf(stdout,
            "Looked up %llu addresses using %d threads in %.2Lf seconds. %.2Lf "
            "lookups per second.\n",
            total_ips,
            thread_count,
            elapsed,
            rate);

    return true;
}

static long double get_time(void) {
    // clock_gettime() is not present on OSX until 10.12.
#ifdef HAVE_CLOCK_GETTIME
    struct timespec tp = {
        .tv_sec = 0,
        .tv_nsec = 0,
    };
    clockid_t clk_id = CLOCK_REALTIME;
#ifdef _POSIX_MONOTONIC_CLOCK
    clk_id = CLOCK_MONOTONIC;
#endif
    if (clock_gettime(clk_id, &tp) != 0) {
        fprintf(stderr, "clock_gettime(): %s\n", strerror(errno));
        return -1;
    }
    return (long double)tp.tv_sec + ((float)tp.tv_nsec / 1e9);
#else
    time_t t = time(NULL);
    if (t == (time_t)-1) {
        fprintf(stderr, "time(): %s\n", strerror(errno));
        return -1;
    }
    return (long double)t;
#endif
}

static void *thread(void *arg) {
    const struct thread_info *const tinfo = arg;
    if (!tinfo) {
        fprintf(stderr, "thread(): %s\n", strerror(EINVAL));
        return NULL;
    }

    char ip_address[16] = {0};

    for (int i = 0; i < tinfo->iterations; i++) {
        memset(ip_address, 0, 16);
        random_ipv4(ip_address);

        MMDB_lookup_result_s result = lookup_or_die(tinfo->mmdb, ip_address);
        if (!result.found_entry) {
            continue;
        }

        MMDB_entry_data_list_s *entry_data_list = NULL;
        int const status =
            MMDB_get_entry_data_list(&result.entry, &entry_data_list);
        if (status != MMDB_SUCCESS) {
            fprintf(stderr,
                    "MMDB_get_entry_data_list(): %s\n",
                    MMDB_strerror(status));
            MMDB_free_entry_data_list(entry_data_list);
            return NULL;
        }

        if (!entry_data_list) {
            fprintf(stderr, "entry_data_list is NULL\n");
            return NULL;
        }

        MMDB_free_entry_data_list(entry_data_list);
    }

    return NULL;
}
#endif
