#ifndef _POSIX_C_SOURCE
    #define _POSIX_C_SOURCE 200809L
#endif

#include "maxminddb-compat-util.h"
#include "maxminddb.h"
#include <stdlib.h>
#include <unistd.h>

#define kMinInputLength 2
#define kMaxInputLength (256 * 1024)

extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    int status;
    MMDB_s mmdb;
    char filename[] = "/tmp/libfuzzer.XXXXXX";

    if (size < kMinInputLength || size > kMaxInputLength) {
        return 0;
    }

    int const fd = mkstemp(filename);
    if (fd == -1) {
        abort();
    }
    FILE *const fp = fdopen(fd, "wb");
    if (!fp) {
        close(fd);
        unlink(filename);
        abort();
    }

    size_t const written = fwrite(data, sizeof(uint8_t), size, fp);
    int const close_status = fclose(fp);
    if (written != size || close_status != 0) {
        unlink(filename);
        abort();
    }

    status = MMDB_open(filename, MMDB_MODE_MMAP, &mmdb);
    if (status == MMDB_SUCCESS) {
        int gai_error, mmdb_error;
        MMDB_lookup_result_s result =
            MMDB_lookup_string(&mmdb, "1.1.1.1", &gai_error, &mmdb_error);
        if (gai_error == 0 && mmdb_error == MMDB_SUCCESS &&
            result.found_entry) {
            MMDB_entry_data_list_s *entry_data_list = NULL;
            MMDB_get_entry_data_list(&result.entry, &entry_data_list);
            MMDB_free_entry_data_list(entry_data_list);
        }
        MMDB_close(&mmdb);
    }

    if (unlink(filename) != 0) {
        abort();
    }
    return 0;
}
