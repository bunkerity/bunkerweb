/* config.h.cmake.  Based upon generated config.h.in.  */

#ifndef MODSECURITY_CONFIG_H
#define MODSECURITY_CONFIG_H 1

/* Define to 1 if you have the <dlfcn.h> header file. */
#cmakedefine HAVE_DLFCN_H

/* Define to 1 if you have the <inttypes.h> header file. */
#cmakedefine HAVE_INTTYPES_H

/* Define to 1 if you have the <iostream> header file. */
#cmakedefine HAVE_IOSTREAM

/* Define to 1 if you have the <stdint.h> header file. */
#cmakedefine HAVE_STDINT_H

/* Define to 1 if you have the <stdio.h> header file. */
#cmakedefine HAVE_STDIO_H

/* Define to 1 if you have the <stdlib.h> header file. */
#cmakedefine HAVE_STDLIB_H

/* Define to 1 if you have the <string> header file. */
#cmakedefine HAVE_STRING

/* Define to 1 if you have the <strings.h> header file. */
#cmakedefine HAVE_STRINGS_H

/* Define to 1 if you have the <string.h> header file. */
#cmakedefine HAVE_STRING_H

/* Define to 1 if you have the <sys/stat.h> header file. */
#cmakedefine HAVE_SYS_STAT_H

/* Define to 1 if you have the <sys/types.h> header file. */
#cmakedefine HAVE_SYS_TYPES_H

/* Define to 1 if you have the <sys/utsname.h> header file. */
#cmakedefine HAVE_SYS_UTSNAME_H

/* Define to 1 if you have the <unistd.h> header file. */
#cmakedefine HAVE_UNISTD_H

/* Define if GeoIP is available */
#cmakedefine HAVE_GEOIP

/* Define if LMDB is available */
#cmakedefine HAVE_LMDB

/* Define if LUA is available */
#cmakedefine HAVE_LUA

/* Define if MaxMind is available */
#cmakedefine HAVE_MAXMIND

/* Define if SSDEEP is available */
#cmakedefine HAVE_SSDEEP

/* Define if YAJL is available */
#cmakedefine HAVE_YAJL

/* Define if libcurl is available */
#cmakedefine HAVE_CURL

/* Name of package */
#define PACKAGE "@PACKAGE_NAME@"

/* Define to the address where bug reports for this package should be sent. */
#cmakedefine PACKAGE_BUGREPORT "@PACKAGE_BUGREPORT@"

/* Define to the full name of this package. */
#cmakedefine PACKAGE_NAME "@PACKAGE_NAME@"

/* Define to the full name and version of this package. */
#cmakedefine PACKAGE_STRING "@PACKAGE_STRING@"

/* Define to the one symbol short name of this package. */
#cmakedefine PACKAGE_TARNAME "@PACKAGE_TARNAME@"

/* Define to the home page for this package. */
#define PACKAGE_URL ""

/* Define to the version of this package. */
#cmakedefine PACKAGE_VERSION "@PACKAGE_VERSION@"

/* Define to 1 if you have the ANSI C header files. */
#ifndef STDC_HEADERS
#cmakedefine STDC_HEADERS
#endif

#endif // ndef MODSECURITY_CONFIG_H