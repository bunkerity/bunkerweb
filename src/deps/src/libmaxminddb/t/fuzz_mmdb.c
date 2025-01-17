#include "maxminddb-compat-util.h"
#include "maxminddb.h"
#include <unistd.h>

#define kMinInputLength 2
#define kMaxInputLength 4048

extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    int status;
    FILE *fp;
    MMDB_s mmdb;
    char filename[256];

    if (size < kMinInputLength || size > kMaxInputLength)
        return 0;

    sprintf(filename, "/tmp/libfuzzer.%d", getpid());

    fp = fopen(filename, "wb");
    if (!fp)
        return 0;

    fwrite(data, size, sizeof(uint8_t), fp);
    fclose(fp);

    status = MMDB_open(filename, MMDB_MODE_MMAP, &mmdb);
    if (status == MMDB_SUCCESS)
        MMDB_close(&mmdb);

    unlink(filename);
    return 0;
}
