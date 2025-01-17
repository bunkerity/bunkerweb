/*
 * A not very good test for performance.  This is mostly useful in
 * testing performance -regressions-
 *
 */
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "libinjection.h"
int testIsSQL(void);

int testIsSQL(void) {
    const char *const s[] = {
        "<script>alert(1);</script>",
        "><script>alert(1);</script>"
        "x ><script>alert(1);</script>",
        "' ><script>alert(1);</script>",
        "\"><script>alert(1);</script>",
        "red;</style><script>alert(1);</script>",
        "red;}</style><script>alert(1);</script>",
        "red;\"/><script>alert(1);</script>",
        "');}</style><script>alert(1);</script>",
        "onerror=alert(1)>",
        "x onerror=alert(1);>",
        "x' onerror=alert(1);>",
        "x\" onerror=alert(1);>",
        "<a href=\"javascript:alert(1)\">",
        "<a href='javascript:alert(1)'>",
        "<a href=javascript:alert(1)>",
        "<a href  =   javascript:alert(1); >",
        "<a href=\"  javascript:alert(1);\" >",
        "<a href=\"JAVASCRIPT:alert(1);\" >",
        "123 LIKE -1234.5678E+2;",
        "APPLE 19.123 'FOO' \"BAR\"",
        "/* BAR */ UNION ALL SELECT (2,3,4)",
        "1 || COS(+0X04) --FOOBAR",
        "dog apple @cat banana bar",
        "dog apple cat \"banana \'bar",
        "102 TABLE CLOTH",
        "(1001-'1') union select 1,2,3,4 from credit_cards",
        NULL};
    const int imax = 1000000;
    int i, j;
    size_t slen;
    clock_t t0, t1;
    double total;
    int tps;

    t0 = clock();
    for (i = imax, j = 0; i != 0; --i, ++j) {
        if (s[j] == NULL) {
            j = 0;
        }

        slen = strlen(s[j]);
        libinjection_xss(s[j], slen);
    }

    t1 = clock();
    total = (double)(t1 - t0) / (double)CLOCKS_PER_SEC;
    tps = (int)((double)imax / total);
    return tps;
}

int main(void) {
    const int mintps = 500000;
    int tps = testIsSQL();

    printf("\nTPS : %d\n\n", tps);

    if (tps < 500000) {
        printf("FAIL: %d < %d\n", tps, mintps);
        /* FAIL */
        return 1;
    } else {
        printf("OK: %d > %d\n", tps, mintps);
        /* OK */
        return 0;
    }
}
