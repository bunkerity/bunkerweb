#include <assert.h>
#include <stdlib.h>
#include <strings.h>

#include "libinjection.h"

/*
 * reproduce core dump due to a stack overflow in libinjection.
 * to run this test, libinjection must be compiled without optimization
 *
 * gcc -O0 -o test_stack_xss src/test_stack_xss.c  src/libinjection*.c &&
 * ./test_stack_xss && echo OK
 *
 */

int main(void) {
    const size_t input_size = 10000000;

    char *input = malloc(input_size);

    assert(input != NULL);

    memset(input, '/', input_size);
    input[input_size - 1] = '\0';

    // should not crash
    libinjection_xss(input, strlen(input));

    return 0;
}
