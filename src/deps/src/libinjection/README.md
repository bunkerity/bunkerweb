
<img src="https://raw.githubusercontent.com/libinjection/libinjection/main/misc/libinjection.svg" width="70%">

![CI](https://github.com/libinjection/libinjection/workflows/CI/badge.svg)
[![license](https://img.shields.io/badge/license-BSD_3--Clause-blue.svg?style=flat)](https://raw.githubusercontent.com/libinjection/libinjection/main/COPYING)


SQL / SQLI tokenizer parser analyzer. For

* C and C++
* [PHP](https://libinjection.client9.com/doc-sqli-php)
* [Python](https://libinjection.client9.com/doc-sqli-python)
* [Lua](/lua)
* [Java](https://github.com/jeonglee/Libinjection) (external port)
* [LuaJIT/FFI](https://github.com/p0pr0ck5/lua-ffi-libinjection) (external port)

See [https://www.client9.com/](https://www.client9.com/)
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
    injection_result_t result;

    const char* input = argv[1];
    size_t slen = strlen(input);

    /* in real-world, you would url-decode the input, etc */

    libinjection_sqli_init(&state, input, slen, FLAG_NONE);
    result = libinjection_is_sqli(&state);
    
    if (result == LIBINJECTION_RESULT_ERROR) {
        fprintf(stderr, "error: parser encountered an error\n");
        return 2;
    } else if (result == LIBINJECTION_RESULT_TRUE) {
        fprintf(stderr, "sqli detected with fingerprint of '%s'\n", state.fingerprint);
        return 1;
    }
    
    /* LIBINJECTION_RESULT_FALSE - no SQLi detected */
    return 0;
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

See [CHANGELOG](CHANGELOG.md) for details.

Versions are listed as "major.minor.point"

Major are significant changes to the API and/or fingerprint format.
Applications will need recompiling and/or refactoring.

Minor are C code changes.  These may include
 * logical change to detect or suppress
 * optimization changes
 * code refactoring

Point releases are purely data changes.  These may be safely applied.

ERROR HANDLING
==============

As of version 4.0.0, libinjection uses an `injection_result_t` enum for return values instead of `int`:

```c
typedef enum injection_result_t {
    LIBINJECTION_RESULT_FALSE = 0,   // No injection detected (benign input)
    LIBINJECTION_RESULT_TRUE = 1,    // Injection detected
    LIBINJECTION_RESULT_ERROR = -1   // Parser error (invalid state)
} injection_result_t;
```

**Important:** Prior to v4.0.0, libinjection would call `abort()` and terminate the process when encountering parser errors. Now it returns `LIBINJECTION_RESULT_ERROR` instead, allowing your application to handle errors gracefully.

**Backward Compatibility:** The enum values `LIBINJECTION_RESULT_FALSE` (0) and `LIBINJECTION_RESULT_TRUE` (1) maintain backward compatibility with code that checks for true/false values. However, applications should be updated to handle `LIBINJECTION_RESULT_ERROR` (-1) to prevent treating parser errors as benign input.

**Migration:** See [MIGRATION.md](MIGRATION.md) for guidance on updating existing code.

QUALITY AND DIAGNOSITICS
========================

The continuous integration results at GitHub tests the following:

- [x] build and unit-tests under GCC
- [x] build and unit-tests under Clang
- [x] static analysis using [clang static analyzer](http://clang-analyzer.llvm.org)
- [x] static analysis using [cppcheck](https://github.com/danmar/cppcheck)
- [x] checks for memory errors using [valgrind](http://valgrind.org/)

LICENSE
=============

Copyright (c) 2012-2016, Nick Galbreath
Copyright (c) 2017-2024, libinjection Contributors

Licensed under the standard [BSD 3-Clause](http://opensource.org/licenses/BSD-3-Clause) open source
license.  See [COPYING](/COPYING) for details.

## BUILD TARGETS

Some of the previous help runners have been merged into the Makefile. E.g.:

* run-clang-asan.sh -> `make clan-asan`
* make-ci.sh -> `make ci`

### Building and Installing Libraries

The autotools build system uses **libtool**, which places built libraries in the `src/.libs/` directory (not directly in `src/` like older versions).

**Basic build:**
```bash
./autogen.sh
./configure
make

# Built libraries are located at:
# - src/.libs/libinjection.a (static library)
# - src/.libs/libinjection.so (Linux shared) or src/.libs/libinjection.dylib (macOS shared)
```

**Building static libraries:**
```bash
./configure --enable-static
make
find . -name "*.a"
# Output: ./src/.libs/libinjection.a
```

**Installing to a specific location:**
```bash
./configure --prefix=/path/to/install
make
make install

# This installs:
# - Headers: /path/to/install/include/libinjection*.h
# - Libraries: /path/to/install/lib/libinjection.{a,so,dylib}
# - pkg-config: /path/to/install/lib/pkgconfig/libinjection.pc
```

**Linking against libinjection:**

Option 1 - Link against installed library (via pkg-config):
```bash
./configure --prefix=/usr/local
make install
gcc myapp.c $(pkg-config --cflags --libs libinjection)
```

Option 2 - Link against build tree without installing:
```bash
gcc myapp.c -I/path/to/libinjection/src -L/path/to/libinjection/src/.libs -linjection
```

Option 3 - Static linking from build tree:
```bash
gcc myapp.c -I/path/to/libinjection/src /path/to/libinjection/src/.libs/libinjection.a
```

### Migrating from Older Versions (client9/libinjection)

If you're upgrading from the old Makefile-based build system where `libinjection.a` was in `src/`, note that libraries are now in `src/.libs/`.

**Update your build scripts:**

For Makefiles:
```makefile
LIBINJECTION_DIR = ../libinjection
CFLAGS += -I$(LIBINJECTION_DIR)/src
LDFLAGS += -L$(LIBINJECTION_DIR)/src/.libs -linjection
```

For CMake:
```cmake
target_include_directories(myapp PRIVATE ../libinjection/src)
target_link_directories(myapp PRIVATE ../libinjection/src/.libs)
target_link_libraries(myapp injection)
```

If your build system requires libraries in a specific location:
```bash
./configure && make
cp src/.libs/libinjection.a /desired/location/
```

For more information, see:
- GNU Libtool documentation: https://www.gnu.org/software/libtool/manual/html_node/Linking-libraries.html
- GitHub issue #54

### Static Analysis

If you run `make cppcheck` you will see this warning printed:
```
nofile:0 information missingIncludeSystem Cppcheck cannot find all the include files (use --check-config for details)
```
You can safely ignore it as it is just saying that standard include files are being ignored (which is the recommended option):
```
example1.c:1:0: information: Include file: <stdio.h> not found. Please note: Cppcheck does not need standard library headers to get proper results. [missingIncludeSystem]
```

EMBEDDING
=============

The [src](/src)
directory contains everything, but you only need to copy the following
into your source tree:

* [src/libinjection.h](/src/libinjection.h)
* [src/libinjection_error.h](/src/libinjection_error.h)
* [src/libinjection_sqli.h](/src/libinjection_sqli.h)
* [src/libinjection_sqli.c](/src/libinjection_sqli.c)
* [src/libinjection_sqli_data.h](/src/libinjection_sqli_data.h)
* [COPYING](/COPYING)

For XSS detection, also copy:

* [src/libinjection_xss.h](/src/libinjection_xss.h)
* [src/libinjection_xss.c](/src/libinjection_xss.c)
* [src/libinjection_html5.h](/src/libinjection_html5.h)
* [src/libinjection_html5.c](/src/libinjection_html5.c)

The source includes a default version string (`"4.0.0"`).
You can override this at build time, for example by defining `LIBINJECTION_VERSION`:

```
CFLAGS="-DLIBINJECTION_VERSION=\"4.0.0-custom\""
```
