#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "common.h"

/* This file doesn't use any Mbed TLS function, but grab mbedtls_config.h anyway
 * in case it contains platform-specific #defines related to malloc or
 * stdio functions. */
#include "mbedtls/build_info.h"

int main(int argc, char **argv)
{
    FILE *fp;
    uint8_t *Data;
    size_t Size;
    const char *argv0 = argv[0] == NULL ? "PROGRAM_NAME" : argv[0];

    if (argc != 2) {
        fprintf(stderr, "Usage: %s REPRODUCER_FILE\n", argv0);
        return 1;
    }
    //opens the file, get its size, and reads it into a buffer
    fp = fopen(argv[1], "rb");
    if (fp == NULL) {
        fprintf(stderr, "%s: Error in fopen\n", argv0);
        perror(argv[1]);
        return 2;
    }
    if (fseek(fp, 0L, SEEK_END) != 0) {
        fprintf(stderr, "%s: Error in fseek(SEEK_END)\n", argv0);
        perror(argv[1]);
        fclose(fp);
        return 2;
    }
    Size = ftell(fp);
    if (Size == (size_t) -1) {
        fprintf(stderr, "%s: Error in ftell\n", argv0);
        perror(argv[1]);
        fclose(fp);
        return 2;
    }
    if (fseek(fp, 0L, SEEK_SET) != 0) {
        fprintf(stderr, "%s: Error in fseek(0)\n", argv0);
        perror(argv[1]);
        fclose(fp);
        return 2;
    }
    Data = malloc(Size);
    if (Data == NULL) {
        fprintf(stderr, "%s: Could not allocate memory\n", argv0);
        perror(argv[1]);
        fclose(fp);
        return 2;
    }
    if (fread(Data, Size, 1, fp) != 1) {
        fprintf(stderr, "%s: Error in fread\n", argv0);
        perror(argv[1]);
        free(Data);
        fclose(fp);
        return 2;
    }

    //launch fuzzer
    LLVMFuzzerTestOneInput(Data, Size);
    free(Data);
    fclose(fp);
    return 0;
}
