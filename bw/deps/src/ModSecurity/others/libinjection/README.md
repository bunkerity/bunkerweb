
<img src="https://raw.githubusercontent.com/libinjection/libinjection/main/misc/libinjection.svg" width="70%">

![CI](https://github.com/libinjection/libinjection/workflows/CI/badge.svg)
[![license](https://img.shields.io/badge/license-BSD_3--Clause-blue.svg?style=flat)](https://raw.githubusercontent.com/client9/libinjection/master/COPYING)



SQL / SQLI tokenizer parser analyzer. For

* C and C++
* [PHP](https://libinjection.client9.com/doc-sqli-php)
* [Python](https://libinjection.client9.com/doc-sqli-python)
* [Lua](/lua)
* [Java](https://github.com/jeonglee/Libinjection) (external port)
* [LuaJIT/FFI] (https://github.com/p0pr0ck5/lua-ffi-libinjection) (external port)

See
[https://www.client9.com/](https://www.client9.com/)
for details and presentations.

Simple example:

```c
#include <stdio.h>
#include <strings.h>
#include <errno.h>
#include "libinjection.h"
#include "libinjection_sqli.h"

int main(int argc, const char* argv[])
{
    struct libinjection_sqli_state state;
    int issqli;

    const char* input = argv[1];
    size_t slen = strlen(input);

    /* in real-world, you would url-decode the input, etc */

    libinjection_sqli_init(&state, input, slen, FLAG_NONE);
    issqli = libinjection_is_sqli(&state);
    if (issqli) {
        fprintf(stderr, "sqli detected with fingerprint of '%s'\n", state.fingerprint);
    }
    return issqli;
}
```

```
$ gcc -Wall -Wextra examples.c libinjection_sqli.c
$ ./a.out "-1' and 1=1 union/* foo */select load_file('/etc/passwd')--"
sqli detected with fingerprint of 's&1UE'
```

More advanced samples:

* [sqli_cli.c](/src/sqli_cli.c)
* [reader.c](/src/reader.c)
* [fptool](/src/fptool.c)

VERSION INFORMATION
===================

See [CHANGELOG](/CHANGELOG) for details.

Versions are listed as "major.minor.point"

Major are significant changes to the API and/or fingerprint format.
Applications will need recompiling and/or refactoring.

Minor are C code changes.  These may include
 * logical change to detect or suppress
 * optimization changes
 * code refactoring

Point releases are purely data changes.  These may be safely applied.

QUALITY AND DIAGNOSITICS
========================

The continuous integration results at
https://travis-ci.org/client9/libinjection tests the following:

- [x] build and unit-tests under GCC
- [x] build and unit-tests under Clang
- [x] static analysis using [clang static analyzer](http://clang-analyzer.llvm.org)
- [x] static analysis using [cppcheck](https://github.com/danmar/cppcheck)
- [x] checks for memory errors using [valgrind](http://valgrind.org/)

LICENSE
=============

Copyright (c) 2012-2016 Nick Galbreath

Licensed under the standard [BSD 3-Clause](http://opensource.org/licenses/BSD-3-Clause) open source
license.  See [COPYING](/COPYING) for details.

EMBEDDING
=============

The [src](https://github.com/client9/libinjection/tree/master/src)
directory contains everything, but you only need to copy the following
into your source tree:

* [src/libinjection.h](/src/libinjection.h)
* [src/libinjection_sqli.c](/src/libinjection_sqli.c)
* [src/libinjection_sqli_data.h](/src/libinjection_sqli_data.h)
* [COPYING](/COPYING)

