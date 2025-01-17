#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <glob.h>
#include "libinjection.h"
#include "libinjection_sqli.h"
#include "libinjection_html5.h"
#include "libinjection_xss.h"

static char g_test[8096];
static char g_input[8096];
static char g_expected[8096];

size_t modp_rtrim(char* str, size_t len);
size_t print_string(char* buf, size_t len, stoken_t* t);
size_t print_var(char* buf, size_t len, stoken_t* t);
size_t print_token(char* buf, size_t len, stoken_t *t);
int read_file(const char* fname, int flags, int testtype);
const char* h5_type_to_string(enum html5_type x);
size_t print_html5_token(char* buf, size_t len, h5_state_t* hs);

size_t modp_rtrim(char* str, size_t len)
{
    while (len) {
        char c = str[len -1];
        if (c == ' ' || c == '\n' || c == '\t' || c == '\r') {
            str[len -1] = '\0';
            len -= 1;
        } else {
            break;
        }
    }
    return len;
}

size_t print_string(char* buf, size_t len, stoken_t* t)
{
    int slen = 0;

    /* print opening quote */
    if (t->str_open != '\0') {
        slen = sprintf(buf + len, "%c", t->str_open);
        assert(slen >= 0);
        len += (size_t) slen;
    }

    /* print content */
    slen = sprintf(buf + len, "%s", t->val);
    assert(slen >= 0);
    len += (size_t) slen;

    /* print closing quote */
    if (t->str_close != '\0') {
        slen = sprintf(buf + len, "%c", t->str_close);
        assert(slen >= 0);
        len += (size_t) slen;
    }

    return len;
}

size_t print_var(char* buf, size_t len, stoken_t* t)
{
    int slen;
    if (t->count >= 1) {
        slen = sprintf(buf + len, "%c", '@');
        assert(slen >= 0);
        len += (size_t) slen;
    }
    if (t->count == 2) {
        slen = sprintf(buf + len, "%c", '@');
        assert(slen >= 0);
        len += (size_t) slen;
    }
    return print_string(buf, len, t);
}

const char* h5_type_to_string(enum html5_type x)
{
    switch (x) {
    case DATA_TEXT: return "DATA_TEXT";
    case TAG_NAME_OPEN: return "TAG_NAME_OPEN";
    case TAG_NAME_CLOSE: return "TAG_NAME_CLOSE";
    case TAG_NAME_SELFCLOSE: return "TAG_NAME_SELFCLOSE";
    case TAG_DATA: return "TAG_DATA";
    case TAG_CLOSE: return "TAG_CLOSE";
    case ATTR_NAME: return "ATTR_NAME";
    case ATTR_VALUE: return "ATTR_VALUE";
    case TAG_COMMENT: return "TAG_COMMENT";
    case DOCTYPE: return "DOCTYPE";
    default:
        assert(0);
    }
    return "";
}

size_t print_html5_token(char* buf, size_t len, h5_state_t* hs)
{
    int slen;
    char* tmp = (char*) malloc(hs->token_len + 1);
    memcpy(tmp, hs->token_start, hs->token_len);
    /* TODO.. encode to be printable */
    tmp[hs->token_len] = '\0';

    slen = sprintf(buf + len, "%s,%d,%s\n",
                   h5_type_to_string(hs->token_type),
                   (int) hs->token_len,
                   tmp);
    len += (size_t) slen;
    free(tmp);
    return len;
}

size_t print_token(char* buf, size_t len, stoken_t *t)
{
    int slen;

    slen = sprintf(buf + len, "%c ", t->type);
    assert(slen >= 0);
    len += (size_t) slen;
    switch (t->type) {
    case 's':
        len = print_string(buf, len, t);
        break;
    case 'v':
        len = print_var(buf, len, t);
        break;
    default:
        slen = sprintf(buf + len, "%s", t->val);
        assert(slen >= 0);
        len += (size_t) slen;
    }
    slen = sprintf(buf + len, "%c", '\n');
    assert(slen >= 0);
    len += (size_t) slen;
    return len;
}

int read_file(const char* fname, int flags, int testtype)
{
    int count = 0;
    FILE *fp = NULL;
    char linebuf[8192];
    char g_actual[8192];
    char* bufptr = NULL;
    size_t slen;
    char* copy;
    sfilter sf;
    int ok = 1;
    int num_tokens;
    int issqli;
    int i;

    g_test[0] = '\0';
    g_input[0] = '\0';
    g_expected[0] = '\0';

    fp = fopen(fname, "r");
    while(fgets(linebuf, sizeof(linebuf), fp) != NULL) {
        if (count == 0 && strcmp(linebuf, "--TEST--\n") == 0) {
            bufptr = g_test;
            count = 1;
        } else if (count == 1 && strcmp(linebuf, "--INPUT--\n") == 0) {
            bufptr = g_input;
            count = 2;
        } else if (count == 2 && strcmp(linebuf, "--EXPECTED--\n") == 0) {
            bufptr = g_expected;
            count = 3;
        } else {
            assert(bufptr != NULL);
            strcat(bufptr, linebuf);
        }
    }
    fclose(fp);
    if (count != 3) {
        return 1;
    }

    g_expected[modp_rtrim(g_expected, strlen(g_expected))] = '\0';
    g_input[modp_rtrim(g_input, strlen(g_input))] = '\0';


    slen = strlen(g_input);
    copy = (char* ) malloc(slen);
    memcpy(copy, g_input, slen);

    g_actual[0] = '\0';
    if (testtype == 0) {
        /*
         * print SQLi tokenization only
         */
        libinjection_sqli_init(&sf, copy, slen, flags);
        libinjection_sqli_callback(&sf, NULL, NULL);
        slen =0;
        while (libinjection_sqli_tokenize(&sf) == 1) {
            slen = print_token(g_actual, slen, sf.current);
        }
    } else if (testtype == 1) {
        /*
         * testing tokenization + folding
         */
        libinjection_sqli_init(&sf, copy, slen, flags);
        libinjection_sqli_callback(&sf, NULL, NULL);
        slen =0;
        num_tokens = libinjection_sqli_fold(&sf);
        for (i = 0; i < num_tokens; ++i) {
            slen = print_token(g_actual, slen, libinjection_sqli_get_token(&sf, i));
        }
    } else if (testtype == 2) {
        /**
         * test SQLi detection
         */
        char buf[100];
        issqli = libinjection_sqli(copy, slen, buf);
        if (issqli) {
            sprintf(g_actual, "%s", buf);
        }
    } else if (testtype == 3) {
        /*
         * test HTML 5 tokenization only
         */

        h5_state_t hs;
        libinjection_h5_init(&hs, copy, slen, DATA_STATE);
        slen = 0;
        while (libinjection_h5_next(&hs)) {
            slen = print_html5_token(g_actual, slen, &hs);
        }
    } else if (testtype == 4) {
        /*
         * test XSS detection
         */
        sprintf(g_actual, "%d", libinjection_xss(copy, slen));
    } else {
        fprintf(stderr, "Got strange testtype value of %d\n", testtype);
        assert(0);
    }

    g_actual[modp_rtrim(g_actual, strlen(g_actual))] = '\0';

    if (strcmp(g_expected, g_actual) != 0) {
        printf("INPUT: \n%s\n==\n", g_input);
        printf("EXPECTED: \n%s\n==\n", g_expected);
        printf("GOT: \n%s\n==\n", g_actual);
        ok = 0;
    }

    free(copy);
    return ok;
}

int main(int argc, char** argv)
{
    int offset = 1;
    int i;
    int ok;
    int count = 0;
    int count_fail = 0;
    int flags = 0;
    int testtype = 0;
    int quiet = 0;

    const char* fname;
    while (argc > offset) {
        if (strcmp(argv[offset], "-q") == 0 || strcmp(argv[offset], "--quiet") == 0) {
            quiet = 1;
            offset += 1;
        } else {
            break;
        }
    }

    printf("%s\n", libinjection_version());

    for (i = offset; i < argc; ++i) {
        fname = argv[i];
        count += 1;
        if (strstr(fname, "test-tokens-")) {
            flags = FLAG_QUOTE_NONE | FLAG_SQL_ANSI;
            testtype = 0;
        } else if (strstr(fname, "test-folding-")) {
            flags = FLAG_QUOTE_NONE | FLAG_SQL_ANSI;
            testtype = 1;
        } else if (strstr(fname, "test-sqli-")) {
            flags = FLAG_NONE;
            testtype = 2;
        } else if (strstr(fname, "test-html5-")) {
            flags = FLAG_NONE;
            testtype = 3;
        } else if (strstr(fname, "test-xss-")) {
            flags = FLAG_NONE;
            testtype = 4;
        } else {
            fprintf(stderr, "Unknown test type: %s, failing\n", fname);
            count_fail += 1;
            continue;
        }

        ok = read_file(fname, flags, testtype);
        if (ok) {
            if (! quiet) {
                fprintf(stderr, "%s: ok\n", fname);
            }
        } else {
            count_fail += 1;
            if (! quiet) {
                fprintf(stderr, "%s: fail\n", fname);
            }
        }
    }
    return count > 0 && count_fail > 0;
}
