# ModSecurity configure.ac


# Get the hash of the last commit, to be used if it is not an
# official release.
AC_DEFUN([MSC_GIT_HASH], m4_esyscmd_s(git log -1 --format="%h" --abbrev-commit))
AC_DEFUN([MSC_MAJOR], m4_esyscmd_s(cat headers/modsecurity/modsecurity.h | grep "define MODSECURITY_MAJOR " | awk {'print $3'} | sed 's/\"//g'))
AC_DEFUN([MSC_MINOR], m4_esyscmd_s(cat headers/modsecurity/modsecurity.h | grep "define MODSECURITY_MINOR " | awk {'print $3'} | sed 's/\"//g'))
AC_DEFUN([MSC_PATCHLEVEL], m4_esyscmd_s(cat headers/modsecurity/modsecurity.h | grep "define MODSECURITY_PATCHLEVEL " | awk {'print $3'} | sed 's/\"//g'))
AC_DEFUN([MSC_TAG], m4_esyscmd_s(cat headers/modsecurity/modsecurity.h | grep "define MODSECURITY_FTAG " | awk {'print $3'} | sed 's/\"//g'))


# Version definition to be further used by AC_INIT and 
# .so file naming.
m4_define([msc_version_major], [MSC_MAJOR])
m4_define([msc_version_minor], [MSC_MINOR])
m4_define([msc_version_patchlevel], [MSC_PATCHLEVEL])

m4_define([msc_version_c_plus_a], [m4_eval(msc_version_major + msc_version_minor)])


m4_define([msc_version],
    [msc_version_major.msc_version_minor])

m4_define([msc_version_with_patchlevel],
    [msc_version_major.msc_version_minor.msc_version_patchlevel])

m4_define([msc_version_git],
    [m4_esyscmd_s(git describe)])

m4_define([msc_version_info],
    [msc_version_c_plus_a:msc_version_patchlevel:msc_version_minor])


# Project Information
AC_INIT([modsecurity], [3.0], [security@modsecurity.org])


# General definitions
AC_CONFIG_MACRO_DIR([build])
AC_PREFIX_DEFAULT([/usr/local/modsecurity])


# General automake options.
AM_INIT_AUTOMAKE([-Wall foreign subdir-objects])


# Check for dependencies (C++, AR, Lex, Yacc and Make)
AC_PROG_CXX
AM_PROG_AR
AC_PROG_MAKE_SET
PKG_PROG_PKG_CONFIG


# Set C++ standard version and check if compiler supports it.
AX_CXX_COMPILE_STDCXX(17, noext, mandatory)

# Check for libinjection
if ! test -f "${srcdir}/others/libinjection/src/libinjection_html5.c"; then
AC_MSG_ERROR([\


  libInjection was not found within ModSecurity source directory.

  libInjection code is available as part of ModSecurity source code in a format
  of a git-submodule. git-submodule allow us to specify the correct version of
  libInjection and still uses the libInjection repository to download it.

  You can download libInjection using git:

     $ git submodule init
     $ git submodule update

   ])
fi
# Libinjection version
AC_DEFUN([LIBINJECTION_VERSION], m4_esyscmd_s(cd "others/libinjection" && git describe && cd ../..))
AC_SUBST([LIBINJECTION_VERSION])

# Check for Mbed TLS
if ! test -f "${srcdir}/others/mbedtls/library/base64.c"; then
AC_MSG_ERROR([\


  Mbed TLS was not found within ModSecurity source directory.

  Mbed TLS code is available as part of ModSecurity source code in a format
  of a git-submodule. git-submodule allow us to specify the correct version of
  Mbed TLS and still uses the Mbed TLS repository to download it.

  You can download Mbed TLS using git:

     $ git submodule init
     $ git submodule update

   ])
fi
# Mbed TLS version
AC_DEFUN([MBEDTLS_VERSION], m4_esyscmd_s(cd "others/mbedtls" && git describe && cd ../..))

# SecLang test version
AC_DEFUN([SECLANG_TEST_VERSION], m4_esyscmd_s(cd "test/test-cases/secrules-language-tests" && git log -1 --format="%h" --abbrev-commit && cd ../../..))


# Check for yajl
PROG_YAJL

AM_CONDITIONAL([YAJL_VERSION], [test "$YAJL_VERSION" != ""])

# Check for LibGeoIP
PROG_GEOIP

# Check for MaxMind
PROG_MAXMIND


# Check for LMDB
PROG_LMDB

# Check for SSDEEP
CHECK_SSDEEP

# Check for LUA
CHECK_LUA


#
# Check for curl
#
CHECK_CURL

if ! test -z "${CURL_VERSION}"; then
  AC_DEFINE([MSC_WITH_CURL], [1], [Define if libcurl is available])
fi


#
# Check for LibXML
#
CHECK_LIBXML2


#
# Check for libpcre only if explicitly requested
#
if test "x${with_pcre}" != "x" && test "x${with_pcre}" != "xno"; then
  CHECK_PCRE
else
  #
  # Check for pcre2
  #
  PROG_PCRE2
fi


# Checks for header files.
AC_CHECK_HEADERS([string])
AC_CHECK_HEADERS([iostream])
AC_CHECK_HEADERS([sys/utsname.h])


# Initialize libtool
LT_INIT

# Identify platform
AC_CANONICAL_HOST

case $host in
  *-*-aix*)
    echo "Checking platform... Identified as AIX"
    AC_DEFINE([AIX], [1], [Define if the operating system is AIX])
    PLATFORM="AIX"
    ;;
  *-*-hpux*)
    echo "Checking platform... Identified as HPUX"
    AC_DEFINE([HPUX], [1], [Define if the operating system is HPUX])
    PLATFORM="HPUX"
    ;;
  *-*-darwin*)
    echo "Checking platform... Identified as Macintosh OS X"
    AC_DEFINE([MACOSX], [1], [Define if the operating system is Macintosh OSX])
    PLATFORM="MacOSX"
    ;;
  *-*-linux* | *-*uclinux*)
    echo "Checking platform... Identified as Linux"
    AC_DEFINE([LINUX], [1], [Define if the operating system is LINUX])
    PLATFORM="Linux"
    ;;
  *-*-solaris*)
    echo "Checking platform... Identified as Solaris"
    AC_DEFINE([SOLARIS], [1], [Define if the operating system is SOLARIS])
    PLATFORM="Solaris"
    ;;
  *-*-freebsd*)
    echo "Checking platform... Identified as FreeBSD"
    AC_DEFINE([FREEBSD], [1], [Define if the operating system is FREEBSD])
    PLATFORM="FreeBSD"
    ;;
  *-*-netbsd*)
    echo "Checking platform... Identified as NetBSD"
    AC_DEFINE([NETBSD], [1], [Define if the operating system is NETBSD])
    PLATFORM="NetBSD"
    ;;
  *-*-openbsd*)
    echo "Checking platform... Identified as OpenBSD"
    AC_DEFINE([OPENBSD], [1], [Define if the operating system is OPENBSD])
    PLATFORM="OpenBSD"
    ;;
  *-*-kfreebsd*)
    echo "Checking platform... Identified as kFreeBSD, treating as linux"
    AC_DEFINE([FREEBSD], [1], [Define if the operating system is FREEBSD])
    PLATFORM="kFreeBSD"
    ;;
  *-*-dragonfly*)
    echo "Checking platform... Identified as DragonFlyBSD, treating as linux"
    AC_DEFINE([DRAGONFLY], [1], [Define if the operating system is DRAGONFLY])
    PLATFORM="DragonFly"
    ;;
  *-*-gnu*.*)
    echo "Checking platform... Identified as HURD, treating as linux"
    AC_DEFINE([LINUX], [1], [Define if the operating system is LINUX])
    PLATFORM="HURD"
    ;;
       *)
    echo "Unknown CANONICAL_HOST $host"
    exit 1
    ;;
esac

# Variables to be used inside the Makefile.am files.
MSC_BASE_DIR=`pwd`
AC_SUBST([MSC_BASE_DIR])

MSC_VERSION_INFO=msc_version_info
AC_SUBST([MSC_VERSION_INFO])

MSC_VERSION_WITH_PATCHLEVEL=msc_version_with_patchlevel
AC_SUBST([MSC_VERSION_WITH_PATCHLEVEL])

MSC_VERSION=msc_version
AC_SUBST([MSC_VERSION])

MSC_GIT_VERSION=msc_version_git
AC_SUBST([MSC_GIT_VERSION])

AC_ARG_ENABLE(assertions,
    [AS_HELP_STRING([--enable-assertions],[Turn on assertions feature: undefine NDEBUG])],

    [case "${enableval}" in
        yes) assertions=true ;;
        no)  assertions=false ;;
        *) AC_MSG_ERROR(bad value ${enableval} for --enable-assertions) ;;
        esac],

        [assertions=false]
        )

AC_ARG_ENABLE(debug-logs,
    [AS_HELP_STRING([--disable-debug-logs],[Turn off the SecDebugLog feature])],

    [case "${enableval}" in
        yes) debugLogs=true ;;
        no)  debugLogs=false ;;
        *) AC_MSG_ERROR(bad value ${enableval} for --enable-debug-logs) ;;
    esac],

    [debugLogs=true]
    )
if test "$debugLogs" != "true"; then
    MODSEC_NO_LOGS="-DNO_LOGS=1"
    AC_SUBST(MODSEC_NO_LOGS)
fi


# Fuzzer
AC_ARG_ENABLE(afl-fuzz,
    [AS_HELP_STRING([--enable-afl-fuzz],[Turn on the afl fuzzer compilation utilities])],

    [case "${enableval}" in
        yes) aflFuzzer=true ;;
        no)  aflFuzzer=false ;;
        *) AC_MSG_ERROR(bad value ${enableval} for --enable-afl-fuzz) ;;
    esac],

    [aflFuzzer=false]
    )

# Examples
AC_ARG_ENABLE(examples,
    [AS_HELP_STRING([--enable-examples],[Turn on the examples compilation (default option)])],

    [case "${enableval}" in
        yes) buildExamples=true ;;
        no)  buildExamples=false ;;
        *) AC_MSG_ERROR(bad value ${enableval} for --enable-examples) ;;
    esac],

    [buildExamples=true]
    )

# Parser
AC_ARG_ENABLE(parser-generation,
    [AS_HELP_STRING([--enable-parser-generation],[Enables parser generation during the build])],

    [case "${enableval}" in
        yes) buildParser=true ;;
        no)  buildParser=false ;;
        *) AC_MSG_ERROR(bad value ${enableval} for --enable-parser-generation) ;;
    esac],

    [buildParser=false]
    )


if test $buildParser = true; then
    AC_PROG_YACC
    AC_PROG_LEX(noyywrap)
    AC_PATH_PROG([FLEX], [flex])
    test "x$FLEX" = "x" && AC_MSG_ERROR([flex is needed to build ModSecurity])

    AC_PATH_PROG([BISON], [bison])
    test "x$BISON" = "x" && AC_MSG_ERROR([bison is needed to build ModSecurity])

    AC_PATH_PROG([YACC_INST], $YACC)
    if test ! -f "$srcdir/gram.c"; then
        if test -z "$YACC_INST"; then
            AC_MSG_ERROR([yacc not found - unable to compile ModSecurity])
        fi
    fi
fi


# Decide if we want to build the tests or not.
buildTestUtilities=false
if test "x$YAJL_FOUND" = "x1"; then
    # Regression tests will not be able to run without the logging support.
    # But we still have the unit tests.
    # if test "$debugLogs" = "true"; then
        buildTestUtilities=true
    # fi
fi


AM_CONDITIONAL([TEST_UTILITIES], [test $buildTestUtilities = true])
if test $buildTestUtilities = true; then
    if test $debugLogs = true; then
        if test -f ./test/test-list.sh; then
            TEST_CASES=`./test/test-list.sh`
        fi
    fi
fi

AM_CONDITIONAL([EXAMPLES], [test $buildExamples = true])
AM_CONDITIONAL([BUILD_PARSER], [test $buildParser = true])
AM_CONDITIONAL([USE_MUTEX_ON_PM], [test $mutexPm = true])


# General link options
if test "$PLATFORM" != "MacOSX" -a "$PLATFORM" != "OpenBSD"; then
    GLOBAL_LDADD="-lrt  "
fi

if test "$aflFuzzer" == "true"; then
    FUZZ_CPPCFLAGS="-fsanitize=address -fsanitize-coverage=4 "
    GLOBAL_LDADD="$GLOBAL_LDADD -fsanitize=address "
    GLOBAL_CPPFLAGS="$GLOBAL_CPPFLAGS $FUZZ_CPPCFLAGS"
    $buildExamples = false
fi

case $assertions in
    false) ASSERTIONS_CPPCFLAGS="-DNDEBUG" ;;
    true) ASSERTIONS_CPPCFLAGS="-UNDEBUG" ;;
    *) AC_MSG_ERROR(bad value ${assertions} for assertions) ;;
esac
GLOBAL_CPPFLAGS="$GLOBAL_CPPFLAGS $ASSERTIONS_CPPCFLAGS"

AC_SUBST(GLOBAL_LDADD)
AC_SUBST(GLOBAL_CPPFLAGS)

AM_CONDITIONAL([AFL_FUZZER], [test $aflFuzzer = true])

GLOBAL_CFLAGS=""
AC_SUBST(GLOBAL_CFLAGS)

# Files to be generated via autotools.
AC_CONFIG_FILES([\
    modsecurity.pc \
    Makefile \
    doc/Makefile \
    src/Makefile \
    others/Makefile \
    tools/Makefile \
    tools/rules-check/Makefile
    ])

AM_COND_IF([TEST_UTILITIES],
       [AC_CONFIG_FILES([test/Makefile test/benchmark/Makefile])])

AM_COND_IF([EXAMPLES],
       [AC_CONFIG_FILES([ \
            examples/Makefile \
            examples/simple_example_using_c/Makefile \
            examples/multiprocess_c/Makefile \
            examples/multithread/Makefile \
            examples/reading_logs_with_offset/Makefile \
            examples/reading_logs_via_rule_message/Makefile \
            examples/using_bodies_in_chunks/Makefile \
            ])])

AM_COND_IF([AFL_FUZZER],
       [AC_CONFIG_FILES([test/fuzzer/Makefile])])

AM_COND_IF([BUILD_PARSER],
       [AC_CONFIG_FILES([src/parser/Makefile])])


AC_CONFIG_HEADERS([src/config.h])


# Doxygen support
DX_HTML_FEATURE(ON)
DX_CHM_FEATURE(OFF)
DX_CHI_FEATURE(OFF)
DX_MAN_FEATURE(OFF)
DX_RTF_FEATURE(OFF)
DX_XML_FEATURE(OFF)
DX_PDF_FEATURE(OFF)
DX_PS_FEATURE(OFF)

DX_INIT_DOXYGEN([ModSecurity],[doc/doxygen.cfg])

# make check-valgrind
AX_VALGRIND_DFLT([sgcheck], [off])
AX_VALGRIND_CHECK

# Generate the files.
AC_OUTPUT


# Print a fancy summary
echo " "
echo " "
echo "ModSecurity - ${MSC_GIT_VERSION} for $PLATFORM"
echo " "
echo " Mandatory dependencies"
AS_ECHO_N("   + libInjection                                  ....")
echo LIBINJECTION_VERSION
AS_ECHO_N("   + Mbed TLS                                      ....")
echo MBEDTLS_VERSION
AS_ECHO_N("   + SecLang tests                                 ....")
echo SECLANG_TEST_VERSION

echo " "
echo " Optional dependencies"



## GeoIP - MaxMind
if test "x$GEOIP_FOUND" = "x0" && test "x$MAXMIND_FOUND" = "x0"; then
    echo "   + GeoIP/MaxMind                                 ....not found"
fi
if test "x$GEOIP_FOUND" = "x1" || test "x$MAXMIND_FOUND" = "x1"; then
    AS_ECHO_N("   + GeoIP/MaxMind                                 ....found ")
    echo ""
    if test "x$MAXMIND_FOUND" = "x1"; then
        echo "      * (MaxMind) v${MAXMIND_VERSION}"
        echo "         ${MAXMIND_DISPLAY}"
    fi
    if test "x$GEOIP_FOUND" = "x1"; then
        echo "      * (GeoIP) v${GEOIP_VERSION}"
        echo "         ${GEOIP_DISPLAY}"
    fi
fi
if test "x$GEOIP_FOUND" = "x2" && test "x$MAXMIND_FOUND" = "x2"; then
    echo "   + GeoIP/MaxMind                                 ....disabled"
fi


## LibCurl
if test "x$CURL_FOUND" = "x0"; then
    echo "   + LibCURL                                       ....not found"
fi
if test "x$CURL_FOUND" = "x1"; then
    AS_ECHO_N("   + LibCURL                                       ....found ")
    if ! test "x$CURL_VERSION" = "x"; then
        echo "v${CURL_VERSION}"
    else
        echo ""
    fi
    echo "      ${CURL_DISPLAY}"
fi
if test "x$CURL_FOUND" = "x2"; then
    echo "   + LibCURL                                       ....disabled"
fi


## YAJL
if test "x$YAJL_FOUND" = "x0"; then
    echo "   + YAJL                                          ....not found"
fi
if test "x$YAJL_FOUND" = "x1"; then
    AS_ECHO_N("   + YAJL                                          ....found ")
    if ! test "x$YAJL_VERSION" = "x"; then
        echo "v${YAJL_VERSION}"
    else
        echo ""
    fi
    echo "      ${YAJL_DISPLAY}"
fi
if test "x$YAJL_FOUND" = "x2"; then
    echo "   + YAJL                                          ....disabled"
fi


## LMDB
if test "x$LMDB_FOUND" = "x0"; then
    echo "   + LMDB                                          ....not found"
fi
if test "x$LMDB_FOUND" = "x1"; then
    AS_ECHO_N("   + LMDB                                          ....found ")
    if ! test "x$LMDB_VERSION" = "x"; then
        echo "v${LMDB_VERSION}"
    else
        echo ""
    fi
    echo "      ${LMDB_DISPLAY}"
fi
if test "x$LMDB_FOUND" = "x2"; then
    echo "   + LMDB                                          ....disabled"
fi


## libxml2
if test "x$LIBXML2_FOUND" = "x0"; then
    echo "   + LibXML2                                       ....not found"
fi
if test "x$LIBXML2_FOUND" = "x1"; then
    AS_ECHO_N("   + LibXML2                                       ....found ")
    if ! test "x$LIBXML2_VERSION" = "x"; then
        echo "v${LIBXML2_VERSION}"
    else
        echo ""
    fi
    echo "      ${LIBXML2_DISPLAY}"
fi
if test "x$LIBXML2_FOUND" = "x2"; then
    echo "   + LibXML2                                       ....disabled"
fi


## SSDEEP
if test "x$SSDEEP_FOUND" = "x0"; then
    echo "   + SSDEEP                                        ....not found"
fi
if test "x$SSDEEP_FOUND" = "x1"; then
    AS_ECHO_N("   + SSDEEP                                        ....found ")
    if ! test "x$SSDEEP_VERSION" = "x"; then
        echo "v${SSDEEP_VERSION}"
    else
        echo ""
    fi
    echo "      ${SSDEEP_DISPLAY}"
fi
if test "x$SSDEEP_FOUND" = "x2"; then
    echo "   + SSDEEP                                        ....disabled"
fi

## LUA
if test "x$LUA_FOUND" = "x0"; then
    echo "   + LUA                                           ....not found"
fi
if test "x$LUA_FOUND" = "x1"; then
    AS_ECHO_N("   + LUA                                           ....found ")
    if ! test "x$LUA_VERSION" = "x"; then
        echo "v${LUA_VERSION}"
    else
        echo ""
    fi
    echo "      ${LUA_DISPLAY}"
fi
if test "x$LUA_FOUND" = "x2"; then
    echo "   + LUA                                           ....disabled"
fi

##PCRE
if test "x${with_pcre}" != "x" \
   && test "x${with_pcre}" != "xno" \
   && test "x${PCRE_VERSION}" == "x"; then
    AC_MSG_NOTICE([*** pcre library not found.])
else
    echo "   + PCRE                                          ....found "
    echo "     using pcre v${PCRE_VERSION}"
    echo "      ${PCRE_LDADD}, ${PCRE_CFLAGS}"
fi


## PCRE2
if test "x$PCRE2_FOUND" = "x0"; then
    echo "   + PCRE2                                          ....not found"
fi
if test "x$PCRE2_FOUND" = "x1"; then
    AS_ECHO_N("   + PCRE2                                          ....found ")
    if ! test "x$PCRE2_VERSION" = "x"; then
        echo "v${PCRE2_VERSION}"
    else
        echo ""
    fi
    echo "      ${PCRE2_DISPLAY}"
fi
if test "x$PCRE2_FOUND" = "x2"; then
    echo "   + PCRE2                                          ....disabled"
fi

echo " "
echo " Other Options"
if test $buildTestUtilities = true; then
    if test $debugLogs = true; then
        echo "   + Test Utilities                                ....enabled"
    else
        echo "   + Test Utilities                                ....partially"
    fi
else
    echo "   + Test Utilities                                ....disabled"
fi
if test $assertions = true; then
    echo "   + Assertions                                    ....enabled"
else
    echo "   + Assertions                                    ....disabled"
fi
if test $debugLogs = true; then
    echo "   + SecDebugLog                                   ....enabled"
else
    echo "   + SecDebugLog                                   ....disabled"
fi

if test "$aflFuzzer" = "true"; then
    echo "   + afl fuzzer                                    ....enabled"
    echo "    ($FUZZ_CPPCFLAGS)"
else
    echo "   + afl fuzzer                                    ....disabled"
fi

if test "$buildExamples" = "true"; then
    echo "   + library examples                              ....enabled"
else
    echo "   + library examples                              ....disabled"
fi

if test "$buildParser" = "true"; then
    echo "   + Building parser                               ....enabled"
else
    echo "   + Building parser                               ....disabled"
fi

if test "$mutexPm" = "true"; then
    echo "   + Treating pm operations as critical section    ....enabled"
else
    echo "   + Treating pm operations as critical section    ....disabled"
fi


echo " "


if test "$aflFuzzer" = "true"; then
    echo "WARNING: afl fuzzer was enabled. Make sure you are using the"
    echo " 'afl-clang-fast' as the compiler, otherwise the compilation"
    echo "  will fail."
    echo " "
    echo " You can set the compiler using:"
    echo " "
    echo "  $ export CXX=afl-clang-fast++ "
    echo "  $ export CC=afl-clang-fast "
    echo " "
fi

