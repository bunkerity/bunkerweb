/**
 * Copyright 2012, 2013 Nick Galbreath
 * nickg@client9.com
 * BSD License -- see COPYING.txt for details
 *
 * This is for testing against files in ../data/ *.txt
 * Reads from stdin or a list of files, and emits if a line
 * is a SQLi attack or not, and does basic statistics
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libinjection.h"
#include "libinjection_sqli.h"

void print_string(stoken_t *t);
void print_var(stoken_t *t);
void print_token(stoken_t *t);
void usage(void);

void print_string(stoken_t *t) {
    /* print opening quote */
    if (t->str_open != '\0') {
        printf("%c", t->str_open);
    }

    /* print content */
    printf("%s", t->val);

    /* print closing quote */
    if (t->str_close != '\0') {
        printf("%c", t->str_close);
    }
}

void print_var(stoken_t *t) {
    if (t->count >= 1) {
        printf("%c", '@');
    }
    if (t->count == 2) {
        printf("%c", '@');
    }
    print_string(t);
}

void print_token(stoken_t *t) {
    printf("%c ", t->type);
    switch (t->type) {
    case 's':
        print_string(t);
        break;
    case 'v':
        print_var(t);
        break;
    default:
        printf("%s", t->val);
    }
    printf("%s", "\n");
}

void usage(void) {
    printf("\n");
    printf("libinjection sqli tester\n");
    printf("\n");
    printf(" -ca  parse as ANSI SQL\n");
    printf(" -cm  parse as MySQL SQL\n");
    printf(" -q0  parse as is\n");
    printf(" -q1  parse in single-quote mode\n");
    printf(" -q2  parse in doiuble-quote mode\n");
    printf("\n");
    printf(" -f --fold  fold results\n");
    printf("\n");
    printf(" -d --detect  detect SQLI.  empty reply = not detected\n");
    printf("\n");
}

int main(int argc, const char *argv[]) {
    size_t slen;
    char *copy;

    int flags = 0;
    int fold = 0;
    int detect = 0;

    int i;
    int count;
    int offset = 1;
    int issqli;

    sfilter sf;

    if (argc < 2) {
        usage();
        return 1;
    }
    while (1) {
        if (strcmp(argv[offset], "-h") == 0 ||
            strcmp(argv[offset], "-?") == 0 ||
            strcmp(argv[offset], "--help") == 0) {
            usage();
            return 1;
        }
        if (strcmp(argv[offset], "-m") == 0) {
            flags |= FLAG_SQL_MYSQL;
            offset += 1;
        } else if (strcmp(argv[offset], "-f") == 0 ||
                   strcmp(argv[offset], "--fold") == 0) {
            fold = 1;
            offset += 1;
        } else if (strcmp(argv[offset], "-d") == 0 ||
                   strcmp(argv[offset], "--detect") == 0) {
            detect = 1;
            offset += 1;
        } else if (strcmp(argv[offset], "-ca") == 0) {
            flags |= FLAG_SQL_ANSI;
            offset += 1;
        } else if (strcmp(argv[offset], "-cm") == 0) {
            flags |= FLAG_SQL_MYSQL;
            offset += 1;
        } else if (strcmp(argv[offset], "-q0") == 0) {
            flags |= FLAG_QUOTE_NONE;
            offset += 1;
        } else if (strcmp(argv[offset], "-q1") == 0) {
            flags |= FLAG_QUOTE_SINGLE;
            offset += 1;
        } else if (strcmp(argv[offset], "-q2") == 0) {
            flags |= FLAG_QUOTE_DOUBLE;
            offset += 1;
        } else {
            break;
        }
    }

    /* ATTENTION: argv is a C-string, null terminated.  We copy this
     * to it's own location, WITHOUT null byte.  This way, valgrind
     * can see if we run past the buffer.
     */

    slen = strlen(argv[offset]);
    copy = (char *)malloc(slen);
    memcpy(copy, argv[offset], slen);
    libinjection_sqli_init(&sf, copy, slen, flags);

    if (detect == 1) {
        issqli = libinjection_is_sqli(&sf);
        if (issqli) {
            printf("%s\n", sf.fingerprint);
        }
    } else if (fold == 1) {
        count = libinjection_sqli_fold(&sf);
        for (i = 0; i < count; ++i) {
            print_token(&(sf.tokenvec[i]));
        }
    } else {
        while (libinjection_sqli_tokenize(&sf)) {
            print_token(sf.current);
        }
    }

    free(copy);

    return 0;
}
