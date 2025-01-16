// The spec says this should be set prior to including any headers, but since
// this is test code, it should be fine to set it here. Setting it here avoids
// setting it in every test program.
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#if HAVE_CONFIG_H
#include <config.h>
#endif
#include "libtap/tap.h"
#include "maxminddb-compat-util.h"
#include "maxminddb.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>

#define R_OK 4

#else
#include <netdb.h>
#endif

#if defined _MSC_VER && _MSC_VER < 1900
/* _snprintf has security issues, but I don't think it is worth
   worrying about for the unit tests. */
#define snprintf _snprintf
#endif

#ifndef MMDB_TEST_HELPER_C
#define MMDB_TEST_HELPER_C (1)

#ifdef __GNUC__
#define UNUSED(x) UNUSED_##x __attribute__((__unused__))
#else
#define UNUSED
#endif

#define MAX_DESCRIPTION_LENGTH 500

extern void for_all_record_sizes(const char *filename_fmt,
                                 void (*tests)(int record_size,
                                               const char *filename,
                                               const char *description));
extern void for_all_modes(void (*tests)(int mode, const char *description));
extern char *test_database_path(const char *filename);
extern char *dup_entry_string_or_bail(MMDB_entry_data_s entry_data);
extern MMDB_s *open_ok(const char *db_file, int mode, const char *mode_desc);
extern MMDB_lookup_result_s lookup_string_ok(MMDB_s *mmdb,
                                             const char *ip,
                                             const char *file,
                                             const char *mode_desc);
extern MMDB_lookup_result_s lookup_sockaddr_ok(MMDB_s *mmdb,
                                               const char *ip,
                                               const char *file,
                                               const char *mode_desc);
extern void test_lookup_errors(int gai_error,
                               int mmdb_error,
                               const char *function,
                               const char *ip,
                               const char *file,
                               const char *mode_desc);
extern MMDB_entry_data_s data_ok(MMDB_lookup_result_s *result,
                                 uint32_t expect_type,
                                 const char *description,
                                 ...);
extern void compare_double(double got, double expect);
extern void compare_float(float got, float expect);

#endif
