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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "documents.h"

/* a platform specific defn' of a function to get a high res time in a
 * portable format */
#ifndef WIN32
#include <sys/time.h>
static double mygettime(void) {
    struct timeval now;
    gettimeofday(&now, NULL);
    return now.tv_sec + (now.tv_usec / 1000000.0);
}
#else
#define _WIN32 1
#include <windows.h>
static double mygettime(void) {
    long long tval;
	FILETIME ft;
	GetSystemTimeAsFileTime(&ft);
	tval = ft.dwHighDateTime;
	tval <<=32;
	tval |= ft.dwLowDateTime;
	return tval / 10000000.00;
}
#endif

#define PARSE_TIME_SECS 3

static int
run(int validate_utf8)
{
    long long times = 0; 
    double starttime;

    starttime = mygettime();

    /* allocate a parser */
    for (;;) {
		int i;
        {
            double now = mygettime();
            if (now - starttime >= PARSE_TIME_SECS) break;
        }

        for (i = 0; i < 100; i++) {
            yajl_handle hand = yajl_alloc(NULL, NULL, NULL);
            yajl_status stat;        
            const char ** d;

            yajl_config(hand, yajl_dont_validate_strings, validate_utf8 ? 0 : 1);

            for (d = get_doc(times % num_docs()); *d; d++) {
                stat = yajl_parse(hand, (unsigned char *) *d, strlen(*d));
                if (stat != yajl_status_ok) break;
            }
            
            stat = yajl_complete_parse(hand);

            if (stat != yajl_status_ok) {
                unsigned char * str =
                    yajl_get_error(hand, 1,
                                   (unsigned char *) *d,
                                   (*d ? strlen(*d) : 0));
                fprintf(stderr, "%s", (const char *) str);
                yajl_free_error(hand, str);
                return 1;
            }
            yajl_free(hand);
            times++;
        }
    }

    /* parsed doc 'times' times */
    {
        double throughput;
        double now;
        const char * all_units[] = { "B/s", "KB/s", "MB/s", (char *) 0 };
        const char ** units = all_units;
        int i, avg_doc_size = 0;

        now = mygettime();

        for (i = 0; i < num_docs(); i++) avg_doc_size += doc_size(i);
        avg_doc_size /= num_docs();

        throughput = (times * avg_doc_size) / (now - starttime);
        
        while (*(units + 1) && throughput > 1024) {
            throughput /= 1024;
            units++;
        }
        
        printf("Parsing speed: %g %s\n", throughput, *units);
    }

    return 0;
}

int
main(void)
{
    int rv = 0;

    printf("-- speed tests determine parsing throughput given %d different sample documents --\n",
           num_docs());

    printf("With UTF8 validation:\n");
    rv = run(1);
    if (rv != 0) return rv;
    printf("Without UTF8 validation:\n");
    rv = run(0);
    return rv;
}

