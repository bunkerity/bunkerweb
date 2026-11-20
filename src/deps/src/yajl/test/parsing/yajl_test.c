/*
 * Copyright (c) 2007-2014, Lloyd Hilaiel <me@lloyd.io>
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#include <yajl/yajl_parse.h>
#include <yajl/yajl_gen.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <assert.h>

/* memory debugging routines */
typedef struct
{
    unsigned int numFrees;
    unsigned int numMallocs;
    /* XXX: we really need a hash table here with per-allocation
     *      information */
} yajlTestMemoryContext;

/* cast void * into context */
#define TEST_CTX(vptr) ((yajlTestMemoryContext *) (vptr))

static void yajlTestFree(void * ctx, void * ptr)
{
    assert(ptr != NULL);
    TEST_CTX(ctx)->numFrees++;
    free(ptr);
}

static void * yajlTestMalloc(void * ctx, size_t sz)
{
    assert(sz != 0);
    TEST_CTX(ctx)->numMallocs++;
    return malloc(sz);
}

static void * yajlTestRealloc(void * ctx, void * ptr, size_t sz)
{
    if (ptr == NULL) {
        assert(sz != 0);
        TEST_CTX(ctx)->numMallocs++;
    } else if (sz == 0) {
        TEST_CTX(ctx)->numFrees++;
    }

    return realloc(ptr, sz);
}


/* begin parsing callback routines */
#define BUF_SIZE 2048

static int test_yajl_null(void *ctx)
{
    printf("null\n");
    return 1;
}

static int test_yajl_boolean(void * ctx, int boolVal)
{
    printf("bool: %s\n", boolVal ? "true" : "false");
    return 1;
}

static int test_yajl_integer(void *ctx, long long integerVal)
{
    printf("integer: %lld\n", integerVal);
    return 1;
}

static int test_yajl_double(void *ctx, double doubleVal)
{
    printf("double: %g\n", doubleVal);
    return 1;
}

static int test_yajl_string(void *ctx, const unsigned char * stringVal,
                            size_t stringLen)
{
    printf("string: '");
    fwrite(stringVal, 1, stringLen, stdout);
    printf("'\n");
    return 1;
}

static int test_yajl_map_key(void *ctx, const unsigned char * stringVal,
                             size_t stringLen)
{
    char * str = (char *) malloc(stringLen + 1);
    str[stringLen] = 0;
    memcpy(str, stringVal, stringLen);
    printf("key: '%s'\n", str);
    free(str);
    return 1;
}

static int test_yajl_start_map(void *ctx)
{
    printf("map open '{'\n");
    return 1;
}


static int test_yajl_end_map(void *ctx)
{
    printf("map close '}'\n");
    return 1;
}

static int test_yajl_start_array(void *ctx)
{
    printf("array open '['\n");
    return 1;
}

static int test_yajl_end_array(void *ctx)
{
    printf("array close ']'\n");
    return 1;
}

static yajl_callbacks callbacks = {
    test_yajl_null,
    test_yajl_boolean,
    test_yajl_integer,
    test_yajl_double,
    NULL,
    test_yajl_string,
    test_yajl_start_map,
    test_yajl_map_key,
    test_yajl_end_map,
    test_yajl_start_array,
    test_yajl_end_array
};

static void usage(const char * progname)
{
    fprintf(stderr,
            "usage:  %s [options]\n"
            "Parse input from stdin as JSON and ouput parsing details "
                                                          "to stdout\n"
            "   -b  set the read buffer size\n"
            "   -c  allow comments\n"
            "   -g  allow *g*arbage after valid JSON text\n"
            "   -m  allows the parser to consume multiple JSON values\n"
            "       from a single string separated by whitespace\n"
            "   -p  partial JSON documents should not cause errors\n",
            progname);
    exit(1);
}

int
main(int argc, char ** argv)
{
    yajl_handle hand;
    const char * fileName = NULL;
    static unsigned char * fileData = NULL;
    FILE *file;
    size_t bufSize = BUF_SIZE;
    yajl_status stat;
    size_t rd;
    int i, j;

    /* memory allocation debugging: allocate a structure which collects
     * statistics */
    yajlTestMemoryContext memCtx = { 0,0 };

    /* memory allocation debugging: allocate a structure which holds
     * allocation routines */
    yajl_alloc_funcs allocFuncs = {
        yajlTestMalloc,
        yajlTestRealloc,
        yajlTestFree,
        (void *) NULL
    };

    allocFuncs.ctx = (void *) &memCtx;

    /* allocate the parser */
    hand = yajl_alloc(&callbacks, &allocFuncs, NULL);

    /* check arguments.  We expect exactly one! */
    for (i=1;i<argc;i++) {
        if (!strcmp("-c", argv[i])) {
            yajl_config(hand, yajl_allow_comments, 1);
        } else if (!strcmp("-b", argv[i])) {
            if (++i >= argc) usage(argv[0]);

            /* validate integer */
            for (j=0;j<(int)strlen(argv[i]);j++) {
                if (argv[i][j] <= '9' && argv[i][j] >= '0') continue;
                fprintf(stderr, "-b requires an integer argument.  '%s' "
                        "is invalid\n", argv[i]);
                usage(argv[0]);
            }

            bufSize = atoi(argv[i]);
            if (!bufSize) {
                fprintf(stderr, "%zu is an invalid buffer size\n",
                        bufSize);
            }
        } else if (!strcmp("-g", argv[i])) {
            yajl_config(hand, yajl_allow_trailing_garbage, 1);
        } else if (!strcmp("-m", argv[i])) {
            yajl_config(hand, yajl_allow_multiple_values, 1);
        } else if (!strcmp("-p", argv[i])) {
            yajl_config(hand, yajl_allow_partial_values, 1);
        } else {
            fileName = argv[i];
            break;
        }
    }

    fileData = (unsigned char *) malloc(bufSize);

    if (fileData == NULL) {
        fprintf(stderr,
                "failed to allocate read buffer of %zu bytes, exiting.",
                bufSize);
        yajl_free(hand);
        exit(2);
    }

    if (fileName)
    {
        file = fopen(fileName, "r");
    }
    else
    {
        file = stdin;
    }
    for (;;) {
        rd = fread((void *) fileData, 1, bufSize, file);

        if (rd == 0) {
            if (!feof(stdin)) {
                fprintf(stderr, "error reading from '%s'\n", fileName);
            }
            break;
        }
        /* read file data, now pass to parser */
        stat = yajl_parse(hand, fileData, rd);

        if (stat != yajl_status_ok) break;
    }

    stat = yajl_complete_parse(hand);
    if (stat != yajl_status_ok)
    {
        unsigned char * str = yajl_get_error(hand, 0, fileData, rd);
        fflush(stdout);
        fprintf(stderr, "%s", (char *) str);
        yajl_free_error(hand, str);
    }

    yajl_free(hand);
    free(fileData);

    if (fileName)
    {
        fclose(file);
    }
    /* finally, print out some memory statistics */

/* (lth) only print leaks here, as allocations and frees may vary depending
 *       on read buffer size, causing false failures.
 *
 *  printf("allocations:\t%u\n", memCtx.numMallocs);
 *  printf("frees:\t\t%u\n", memCtx.numFrees);
*/
    fflush(stderr);
    fflush(stdout);
    printf("memory leaks:\t%u\n", memCtx.numMallocs - memCtx.numFrees);

    return 0;
}
