/*
 *  Windows CE console application entry point
 *
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#if defined(_WIN32_WCE)

#include <windows.h>

extern int main(int, const char **);

int _tmain(int argc, _TCHAR *targv[])
{
    char **argv;
    int i;

    argv = (char **) calloc(argc, sizeof(char *));

    for (i = 0; i < argc; i++) {
        size_t len;
        len = _tcslen(targv[i]) + 1;
        argv[i] = (char *) calloc(len, sizeof(char));
        wcstombs(argv[i], targv[i], len);
    }

    return main(argc, argv);
}

#endif  /* defined(_WIN32_WCE) */
