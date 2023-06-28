/*
libtap - Write tests in C
Copyright 2012 Jake Gelbman <gelbman@gmail.com>
This file is licensed under the LGPL
*/

#define _DEFAULT_SOURCE 1

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "tap.h"

static int expected_tests = NO_PLAN;
static int failed_tests;
static int current_test;
static char *todo_mesg;

static char *
vstrdupf (const char *fmt, va_list args) {
    char *str;
    int size;
    va_list args2;
    va_copy(args2, args);
    if (!fmt)
        fmt = "";
    size = vsnprintf(NULL, 0, fmt, args2) + 2;
    str = malloc(size);
    if (!str) {
        perror("malloc error");
        exit(1);
    }
    vsprintf(str, fmt, args);
    va_end(args2);
    return str;
}

void
tap_plan (int tests, const char *fmt, ...) {
    expected_tests = tests;
    if (tests == SKIP_ALL) {
        char *why;
        va_list args;
        va_start(args, fmt);
        why = vstrdupf(fmt, args);
        va_end(args);
        printf("1..0 ");
        diag("SKIP %s\n", why);
        exit(0);
    }
    if (tests != NO_PLAN) {
        printf("1..%d\n", tests);
    }
}

int
vok_at_loc (const char *file, int line, int test, const char *fmt,
            va_list args)
{
    char *name = vstrdupf(fmt, args);
    if (!test) {
        printf("not ");
    }
    printf("ok %d", ++current_test);
    if (*name)
        printf(" - %s", name);
    if (todo_mesg) {
        printf(" # TODO");
        if (*todo_mesg)
            printf(" %s", todo_mesg);
    }
    printf("\n");
    if (!test) {
        printf("#   Failed ");
        if (todo_mesg)
            printf("(TODO) ");
        printf("test ");
        if (*name)
            printf("'%s'\n#   ", name);
        printf("at %s line %d.\n", file, line);
        if (!todo_mesg)
            failed_tests++;
    }
    free(name);
    return test;
}

int
ok_at_loc (const char *file, int line, int test, const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vok_at_loc(file, line, test, fmt, args);
    va_end(args);
    return test;
}

static int
mystrcmp (const char *a, const char *b) {
    return a == b ? 0 : !a ? -1 : !b ? 1 : strcmp(a, b);
}

#define eq(a, b) (!mystrcmp(a, b))
#define ne(a, b) (mystrcmp(a, b))

int
is_at_loc (const char *file, int line, const char *got, const char *expected,
           const char *fmt, ...)
{
    int test = eq(got, expected);
    va_list args;
    va_start(args, fmt);
    vok_at_loc(file, line, test, fmt, args);
    va_end(args);
    if (!test) {
        diag("         got: '%s'", got);
        diag("    expected: '%s'", expected);
    }
    return test;
}

int
isnt_at_loc (const char *file, int line, const char *got, const char *expected,
             const char *fmt, ...)
{
    int test = ne(got, expected);
    va_list args;
    va_start(args, fmt);
    vok_at_loc(file, line, test, fmt, args);
    va_end(args);
    if (!test) {
        diag("         got: '%s'", got);
        diag("    expected: anything else");
    }
    return test;
}

int
cmp_ok_at_loc (const char *file, int line, int a, const char *op, int b,
               const char *fmt, ...)
{
    int test = eq(op, "||") ? a || b
             : eq(op, "&&") ? a && b
             : eq(op, "|")  ? a |  b
             : eq(op, "^")  ? a ^  b
             : eq(op, "&")  ? a &  b
             : eq(op, "==") ? a == b
             : eq(op, "!=") ? a != b
             : eq(op, "<")  ? a <  b
             : eq(op, ">")  ? a >  b
             : eq(op, "<=") ? a <= b
             : eq(op, ">=") ? a >= b
             : eq(op, "<<") ? a << b
             : eq(op, ">>") ? a >> b
             : eq(op, "+")  ? a +  b
             : eq(op, "-")  ? a -  b
             : eq(op, "*")  ? a *  b
             : eq(op, "/")  ? a /  b
             : eq(op, "%")  ? a %  b
             : diag("unrecognized operator '%s'", op);
    va_list args;
    va_start(args, fmt);
    vok_at_loc(file, line, test, fmt, args);
    va_end(args);
    if (!test) {
        diag("    %d", a);
        diag("        %s", op);
        diag("    %d", b);
    }
    return test;
}

static int
find_mem_diff (const char *a, const char *b, size_t n, size_t *offset) {
    size_t i;
    if (a == b)
        return 0;
    if (!a || !b)
        return 2;
    for (i = 0; i < n; i++) {
        if (a[i] != b[i]) {
            *offset = i;
            return 1;
        }
    }
    return 0;
}

int
cmp_mem_at_loc (const char *file, int line, const void *got,
                const void *expected, size_t n, const char *fmt, ...)
{
    size_t offset;
    int diff = find_mem_diff(got, expected, n, &offset);
    va_list args;
    va_start(args, fmt);
    vok_at_loc(file, line, !diff, fmt, args);
    va_end(args);
    if (diff == 1) {
        diag("    Difference starts at offset %d", offset);
        diag("         got: 0x%02x", ((unsigned char *)got)[offset]);
        diag("    expected: 0x%02x", ((unsigned char *)expected)[offset]);
    }
    else if (diff == 2) {
        diag("         got: %s", got ? "not NULL" : "NULL");
        diag("    expected: %s", expected ? "not NULL" : "NULL");
    }
    return !diff;
}

int
diag (const char *fmt, ...) {
    va_list args;
    char *mesg, *line;
    int i;
    va_start(args, fmt);
    if (!fmt) {
        va_end(args);
        return 0;
    }
    mesg = vstrdupf(fmt, args);
    line = mesg;
    for (i = 0; *line; i++) {
        char c = mesg[i];
        if (!c || c == '\n') {
            mesg[i] = '\0';
            printf("# %s\n", line);
            if (!c)
                break;
            mesg[i] = c;
            line = mesg + i + 1;
        }
    }
    free(mesg);
    va_end(args);
    return 0;
}

int
exit_status () {
    int retval = 0;
    if (expected_tests == NO_PLAN) {
        printf("1..%d\n", current_test);
    }
    else if (current_test != expected_tests) {
        diag("Looks like you planned %d test%s but ran %d.",
            expected_tests, expected_tests > 1 ? "s" : "", current_test);
        retval = 2;
    }
    if (failed_tests) {
        diag("Looks like you failed %d test%s of %d run.",
            failed_tests, failed_tests > 1 ? "s" : "", current_test);
        retval = 1;
    }
    return retval;
}

int
bail_out (int ignore, const char *fmt, ...) {
    va_list args;
    (void) ignore;
    va_start(args, fmt);
    printf("Bail out!  ");
    vprintf(fmt, args);
    printf("\n");
    va_end(args);
    exit(255);
    return 0;
}

void
tap_skip (int n, const char *fmt, ...) {
    char *why;
    va_list args;
    va_start(args, fmt);
    why = vstrdupf(fmt, args);
    va_end(args);
    while (n --> 0) {
        printf("ok %d ", ++current_test);
        diag("skip %s\n", why);
    }
    free(why);
}

void
tap_todo (int ignore, const char *fmt, ...) {
    va_list args;
    (void) ignore;
    va_start(args, fmt);
    todo_mesg = vstrdupf(fmt, args);
    va_end(args);
}

void
tap_end_todo () {
    free(todo_mesg);
    todo_mesg = NULL;
}

#ifndef _WIN32
#include <sys/mman.h>
#include <sys/param.h>
#include <regex.h>

#ifndef MAP_ANONYMOUS
#ifdef MAP_ANON
#define MAP_ANONYMOUS MAP_ANON
#else
#error "System does not support mapping anonymous pages"
#endif
#endif

/* Create a shared memory int to keep track of whether a piece of code executed
dies. to be used in the dies_ok and lives_ok macros.  */
int
tap_test_died (int status) {
    static int *test_died = NULL;
    int prev;
    if (!test_died) {
        test_died = mmap(0, sizeof (int), PROT_READ | PROT_WRITE,
                         MAP_SHARED | MAP_ANONYMOUS, -1, 0);
        *test_died = 0;
    }
    prev = *test_died;
    *test_died = status;
    return prev;
}

int
like_at_loc (int for_match, const char *file, int line, const char *got,
             const char *expected, const char *fmt, ...)
{
    int test;
    regex_t re;
    va_list args;
    int err = regcomp(&re, expected, REG_EXTENDED);
    if (err) {
        char errbuf[256];
        regerror(err, &re, errbuf, sizeof errbuf);
        fprintf(stderr, "Unable to compile regex '%s': %s at %s line %d\n",
                        expected, errbuf, file, line);
        exit(255);
    }
    err = regexec(&re, got, 0, NULL, 0);
    regfree(&re);
    test = for_match ? !err : err;
    va_start(args, fmt);
    vok_at_loc(file, line, test, fmt, args);
    va_end(args);
    if (!test) {
        if (for_match) {
            diag("                   '%s'", got);
            diag("    doesn't match: '%s'", expected);
        }
        else {
            diag("                   '%s'", got);
            diag("          matches: '%s'", expected);
        }
    }
    return test;
}
#endif
