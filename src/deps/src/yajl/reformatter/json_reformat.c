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

/* non-zero when we're reformatting a stream */
static int s_streamReformat = 0;

#define GEN_AND_RETURN(func)                                          \
  {                                                                   \
    yajl_gen_status __stat = func;                                    \
    if (__stat == yajl_gen_generation_complete && s_streamReformat) { \
      yajl_gen_reset(g, "\n");                                        \
      __stat = func;                                                  \
    }                                                                 \
    return __stat == yajl_gen_status_ok; }

static int reformat_null(void * ctx)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_null(g));
}

static int reformat_boolean(void * ctx, int boolean)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_bool(g, boolean));
}

static int reformat_number(void * ctx, const char * s, size_t l)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_number(g, s, l));
}

static int reformat_string(void * ctx, const unsigned char * stringVal,
                           size_t stringLen)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_string(g, stringVal, stringLen));
}

static int reformat_map_key(void * ctx, const unsigned char * stringVal,
                            size_t stringLen)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_string(g, stringVal, stringLen));
}

static int reformat_start_map(void * ctx)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_map_open(g));
}


static int reformat_end_map(void * ctx)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_map_close(g));
}

static int reformat_start_array(void * ctx)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_array_open(g));
}

static int reformat_end_array(void * ctx)
{
    yajl_gen g = (yajl_gen) ctx;
    GEN_AND_RETURN(yajl_gen_array_close(g));
}

static yajl_callbacks callbacks = {
    reformat_null,
    reformat_boolean,
    NULL,
    NULL,
    reformat_number,
    reformat_string,
    reformat_start_map,
    reformat_map_key,
    reformat_end_map,
    reformat_start_array,
    reformat_end_array
};

static void
usage(const char * progname)
{
    fprintf(stderr, "%s: reformat json from stdin\n"
            "usage:  json_reformat [options]\n"
            "    -e escape any forward slashes (for embedding in HTML)\n"
            "    -m minimize json rather than beautify (default)\n"
            "    -s reformat a stream of multiple json entites\n"
            "    -u allow invalid UTF8 inside strings during parsing\n",
            progname);
    exit(1);
}

int
main(int argc, char ** argv)
{
    yajl_handle hand;
    static unsigned char fileData[65536];
    /* generator config */
    yajl_gen g;
    yajl_status stat;
    size_t rd;
    int retval = 0;
    int a = 1;

    g = yajl_gen_alloc(NULL);
    yajl_gen_config(g, yajl_gen_beautify, 1);
    yajl_gen_config(g, yajl_gen_validate_utf8, 1);

    /* ok.  open file.  let's read and parse */
    hand = yajl_alloc(&callbacks, NULL, (void *) g);
    /* and let's allow comments by default */
    yajl_config(hand, yajl_allow_comments, 1);

    /* check arguments.*/
    while ((a < argc) && (argv[a][0] == '-') && (strlen(argv[a]) > 1)) {
        unsigned int i;
        for ( i=1; i < strlen(argv[a]); i++) {
            switch (argv[a][i]) {
                case 'm':
                    yajl_gen_config(g, yajl_gen_beautify, 0);
                    break;
                case 's':
                    yajl_config(hand, yajl_allow_multiple_values, 1);
                    s_streamReformat = 1;
                    break;
                case 'u':
                    yajl_config(hand, yajl_dont_validate_strings, 1);
                    break;
                case 'e':
                    yajl_gen_config(g, yajl_gen_escape_solidus, 1);
                    break;
                default:
                    fprintf(stderr, "unrecognized option: '%c'\n\n",
                            argv[a][i]);
                    usage(argv[0]);
            }
        }
        ++a;
    }
    if (a < argc) {
        usage(argv[0]);
    }


    for (;;) {
        rd = fread((void *) fileData, 1, sizeof(fileData) - 1, stdin);

        if (rd == 0) {
            if (!feof(stdin)) {
                fprintf(stderr, "error on file read.\n");
                retval = 1;
            }
            break;
        }
        fileData[rd] = 0;

        stat = yajl_parse(hand, fileData, rd);

        if (stat != yajl_status_ok) break;

        {
            const unsigned char * buf;
            size_t len;
            yajl_gen_get_buf(g, &buf, &len);
            fwrite(buf, 1, len, stdout);
            yajl_gen_clear(g);
        }
    }

    stat = yajl_complete_parse(hand);

    if (stat != yajl_status_ok) {
        unsigned char * str = yajl_get_error(hand, 1, fileData, rd);
        fprintf(stderr, "%s", (const char *) str);
        yajl_free_error(hand, str);
        retval = 1;
    }

    yajl_gen_free(g);
    yajl_free(hand);

    return retval;
}
