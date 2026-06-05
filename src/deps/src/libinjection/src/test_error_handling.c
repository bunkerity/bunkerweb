/**
 * Copyright 2025 LibInjection Project
 * BSD License -- see COPYING.txt for details
 *
 * Test cases for error handling with injection_result_t enum
 *
 * This test verifies that the parser properly returns LIBINJECTION_RESULT_ERROR
 * instead of calling abort() when encountering invalid states.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libinjection.h"
#include "libinjection_error.h"
#include "libinjection_html5.h"
#include "libinjection_sqli.h"
#include "libinjection_xss.h"

/* Test counter */
static int tests_run = 0;
static int tests_passed = 0;

#define TEST_START(name)                                                       \
    do {                                                                       \
        tests_run++;                                                           \
        printf("Test %d: %s ... ", tests_run, name);

#define TEST_END(condition)                                                    \
    if (condition) {                                                           \
        tests_passed++;                                                        \
        printf("PASS\n");                                                      \
    } else {                                                                   \
        printf("FAIL\n");                                                      \
    }                                                                          \
    }                                                                          \
    while (0)

/**
 * Test that normal inputs still return LIBINJECTION_RESULT_FALSE or
 * LIBINJECTION_RESULT_TRUE
 */
static void test_normal_inputs(void) {
    injection_result_t result;
    char fingerprint[8];
    const char *benign;
    const char *sqli;
    const char *xss;
    const char *html;

    TEST_START("Normal benign input returns LIBINJECTION_RESULT_FALSE");
    benign = "hello world 123";
    result = libinjection_sqli(benign, strlen(benign), fingerprint);
    TEST_END(result == LIBINJECTION_RESULT_FALSE);

    TEST_START("Normal SQLi input returns LIBINJECTION_RESULT_TRUE");
    sqli = "1' OR '1'='1";
    result = libinjection_sqli(sqli, strlen(sqli), fingerprint);
    TEST_END(result == LIBINJECTION_RESULT_TRUE);

    TEST_START("Normal XSS input returns LIBINJECTION_RESULT_TRUE");
    xss = "<script>alert('xss')</script>";
    result = libinjection_xss(xss, strlen(xss));
    TEST_END(result == LIBINJECTION_RESULT_TRUE);

    TEST_START("Benign HTML returns LIBINJECTION_RESULT_FALSE");
    html = "<p>Hello World</p>";
    result = libinjection_xss(html, strlen(html));
    TEST_END(result == LIBINJECTION_RESULT_FALSE);
}

/**
 * Test that the library handles edge cases gracefully
 */
static void test_edge_cases(void) {
    injection_result_t result;
    char fingerprint[8];
    char *long_input;
    const char *nulls;

    TEST_START("Empty string does not cause error");
    result = libinjection_sqli("", 0, fingerprint);
    TEST_END(result != LIBINJECTION_RESULT_ERROR);

    long_input = malloc(100000);
    if (long_input != NULL) {
        TEST_START("Very long input does not cause error");
        memset(long_input, 'A', 99999);
        long_input[99999] = '\0';
        result = libinjection_sqli(long_input, strlen(long_input), fingerprint);
        free(long_input);
        TEST_END(result != LIBINJECTION_RESULT_ERROR);
    }

    TEST_START("NULL-like patterns are handled");
    nulls = "\0\0\0\0";
    result = libinjection_sqli(nulls, 4, fingerprint);
    TEST_END(result != LIBINJECTION_RESULT_ERROR);
}

/**
 * Test HTML5 parser state handling
 */
static void test_html5_state_handling(void) {
    h5_state_t hs;
    injection_result_t result;
    const char *html;
    const char *malformed;
    char *nested;

    TEST_START("HTML5 parser initialized properly");
    html = "<div>test</div>";
    libinjection_h5_init(&hs, html, strlen(html), DATA_STATE);
    result = libinjection_h5_next(&hs);
    TEST_END(result != LIBINJECTION_RESULT_ERROR);

    TEST_START("HTML5 parser handles malformed tags");
    malformed = "<div<div>";
    libinjection_h5_init(&hs, malformed, strlen(malformed), DATA_STATE);
    while ((result = libinjection_h5_next(&hs)) == LIBINJECTION_RESULT_TRUE) {
        /* keep going */
    }
    /* Should finish without error or with controlled error */
    TEST_END(result == LIBINJECTION_RESULT_FALSE ||
             result == LIBINJECTION_RESULT_ERROR);

    nested = malloc(10000);
    if (nested != NULL) {
        size_t pos = 0;
        int i;

        TEST_START("HTML5 parser handles deeply nested tags");
        for (i = 0; i < 1000; i++) {
            nested[pos++] = '<';
            nested[pos++] = 'd';
            nested[pos++] = 'i';
            nested[pos++] = 'v';
            nested[pos++] = '>';
        }
        nested[pos] = '\0';
        libinjection_h5_init(&hs, nested, pos, DATA_STATE);
        while ((result = libinjection_h5_next(&hs)) ==
               LIBINJECTION_RESULT_TRUE) {
            /* Should handle without crashing */
        }
        free(nested);
        TEST_END(result == LIBINJECTION_RESULT_FALSE ||
                 result == LIBINJECTION_RESULT_ERROR);
    }
}

/**
 * Test that library no longer calls abort() on error
 * This is more of a smoke test - if the process crashes, test fails
 */
static void test_no_abort_on_error(void) {
    injection_result_t result;
    char fingerprint[8];
    const char *patterns[] = {
        "'''''''''''", "\\\\\\\\\\\\\\\\", "////////", "{{{{{{{{", "}}}}}}}}",
        "[[[[[[[[",    "]]]]]]]]",         "<<<<<<<<", ">>>>>>>>", NULL};
    int all_survived;
    int i;

    TEST_START("Library does not abort on unusual patterns");
    all_survived = 1;
    for (i = 0; patterns[i] != NULL; i++) {
        result =
            libinjection_sqli(patterns[i], strlen(patterns[i]), fingerprint);
        /* Just need to survive - any result is acceptable as long as no abort
         */
        if (result != LIBINJECTION_RESULT_FALSE &&
            result != LIBINJECTION_RESULT_TRUE &&
            result != LIBINJECTION_RESULT_ERROR) {
            all_survived = 0;
            break;
        }
    }
    TEST_END(all_survived);
}

/**
 * Test return value backward compatibility
 */
static void test_backward_compatibility(void) {
    injection_result_t result;
    const char *xss;
    const char *benign;

    /* Cast to int to satisfy cppcheck - we're testing the actual numeric values
     * for backward compatibility, not just enum identity */
    TEST_START("LIBINJECTION_RESULT_FALSE is 0 for backward compatibility");
    TEST_END((int)LIBINJECTION_RESULT_FALSE == 0);

    TEST_START("LIBINJECTION_RESULT_TRUE is 1 for backward compatibility");
    TEST_END((int)LIBINJECTION_RESULT_TRUE == 1);

    TEST_START("LIBINJECTION_RESULT_ERROR is -1");
    TEST_END((int)LIBINJECTION_RESULT_ERROR == -1);

    TEST_START("Simple if(result) check still works for detection");
    xss = "<script>alert(1)</script>";
    result = libinjection_xss(xss, strlen(xss));
    /* Traditional code: if (result) { ... } should still work for positive
     * detection */
    TEST_END(result); /* Should be truthy (LIBINJECTION_RESULT_TRUE = 1) */

    TEST_START("Simple !result check still works for benign");
    benign = "hello world";
    result = libinjection_xss(benign, strlen(benign));
    /* Traditional code: if (!result) { ... } should still work for benign */
    TEST_END(!result); /* Should be falsy (LIBINJECTION_RESULT_FALSE = 0) */
}

int main(void) {
    printf("=== LibInjection Error Handling Test Suite ===\n\n");

    test_normal_inputs();
    test_edge_cases();
    test_html5_state_handling();
    test_no_abort_on_error();
    test_backward_compatibility();

    printf("\n=== Test Summary ===\n");
    printf("Tests run:    %d\n", tests_run);
    printf("Tests passed: %d\n", tests_passed);
    printf("Tests failed: %d\n", tests_run - tests_passed);

    if (tests_run == tests_passed) {
        printf("\nAll tests PASSED!\n");
        return 0;
    } else {
        printf("\nSome tests FAILED!\n");
        return 1;
    }
}
