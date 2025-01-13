#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])
AC_INIT([libmaxminddb], [1.12.2], [support@maxmind.com])
AC_CONFIG_SRCDIR([include/maxminddb.h])
AC_CONFIG_HEADERS([config.h include/maxminddb_config.h])

PKG_PROG_PKG_CONFIG
m4_ifdef([PKG_INSTALLDIR], [PKG_INSTALLDIR], [AC_SUBST([pkgconfigdir], [${libdir}/pkgconfig])])
AC_CONFIG_FILES([src/libmaxminddb.pc])

LT_INIT
AM_INIT_AUTOMAKE(foreign m4_esyscmd([case `automake --version | head -n 1` in
                                     *1.14*) echo subdir-objects;;
                                     *1.11*);;
                                     *) echo serial-tests;;
                                     esac]))
AC_PROG_LIBTOOL
# Checks for programs.
AC_PROG_CC_C99

# Copied from http://stackoverflow.com/a/10682813/9832 and tweaked for C (as
# opposed to C++)
#
# AX_CHECK_CFLAGS(ADDITIONAL-CFLAGS, ACTION-IF-FOUND, ACTION-IF-NOT-FOUND)
#
# checks whether the $(CC) compiler accepts the ADDITIONAL-CFLAGS
# if so, they are added to the CXXFLAGS
AC_DEFUN([AX_CHECK_CFLAGS],
[
  AC_MSG_CHECKING([whether compiler accepts "$1"])
  cat > conftest.c << EOF
  int main(){
    return 0;
  }
EOF
  if $CC $CFLAGS -o conftest.o conftest.c [$1] > /dev/null 2>&1
  then
    AC_MSG_RESULT([yes])
    CFLAGS="${CFLAGS} [$1]"
    [$2]
  else
    AC_MSG_RESULT([no])
   [$3]
  fi
])dnl AX_CHECK_CFLAGS

AX_CHECK_CFLAGS([-fms-extensions])

# We will add this back for non-debug builds in the common.mk file
CFLAGS=`echo ${CFLAGS} | sed 's/-O2//'`
CXXFLAGS=`echo ${CXXFLAGS} | sed 's/-O2//'`

# autoconf insists on giving us gnu99 if it's available
CC=`echo ${CC} | sed 's/-std=gnu99/-std=c99/'`

AC_C_RESTRICT

AC_CHECK_HEADERS([arpa/inet.h assert.h fcntl.h inttypes.h libgen.h math.h netdb.h netinet/in.h stdarg.h stdbool.h stdint.h stdio.h stdlib.h string.h sys/mman.h sys/socket.h sys/stat.h sys/time.h sys/types.h unistd.h])

# configure generates an invalid config for MinGW because of the type checks
# so we only run them on non MinGW-Systems. For MinGW we also need to link
# against ws2_32.
AC_CANONICAL_HOST
is_windows=false
case $host_os in
        mingw*)
                LDFLAGS="-lws2_32"
                is_windows=true
        ;;
        *)
                AC_TYPE_OFF_T
                AC_TYPE_SIZE_T
                AC_TYPE_SSIZE_T
                AC_TYPE_UINT8_T
                AC_TYPE_UINT32_T
                AC_TYPE_UINT64_T
        ;;
esac

AM_CONDITIONAL([WINDOWS], [test x$is_windows = xtrue])

# This check is backwards in order to make life easier for people writing
# extensions in other languages that link to this library. If they want to
# simply assume that they are using a newish compiler, they don't need to
# check for this type nor do they need to define anything on the CLI. They'll
# just get code that assumes this type exists.
AC_CHECK_TYPE(
        [unsigned __int128],
        [AC_DEFINE([MMDB_UINT128_IS_BYTE_ARRAY], [0], [Missing the unsigned __int128 type])],
        [AC_CHECK_TYPE(
                [unsigned int __attribute__((mode(TI)))],
                [AC_DEFINE([MMDB_UINT128_IS_BYTE_ARRAY], [0], [Missing the unsigned __int128 type])
                 AC_DEFINE([MMDB_UINT128_USING_MODE], [1], [int128 types are available with __attribute__((mode(TI)))])],
                [AC_DEFINE([MMDB_UINT128_IS_BYTE_ARRAY], [1], [Missing the unsigned __int128 type])])])

AC_CHECK_TYPES([boolean])

AC_CHECK_FUNCS([clock_gettime open_memstream])

AC_C_BIGENDIAN(
        [AC_DEFINE([MMDB_LITTLE_ENDIAN], [0], [System is big-endian])],
        [AC_DEFINE([MMDB_LITTLE_ENDIAN], [1], [System is little-endian])])

AC_FUNC_MMAP

AC_SEARCH_LIBS([fabs], [m])
AC_SEARCH_LIBS([fabsf], [m])
AC_SEARCH_LIBS([getaddrinfo], [socket])

AC_ARG_ENABLE(
        [debug],
        [  --enable-debug    Turn on debugging],
        [case "${enableval}" in
          yes) debug=true ;;
          no)  debug=false ;;
          *) AC_MSG_ERROR([bad value ${enableval} for --enable-debug]) ;;
        esac],[debug=false])
AM_CONDITIONAL([DEBUG], [test x$debug = xtrue])

AC_ARG_ENABLE([binaries],
        AS_HELP_STRING([--enable-binaries], [Compilation of binaries code]),
        [enable_binaries=${enableval}],
        [enable_binaries=yes])
AM_CONDITIONAL([BINARIES], [test "${enable_binaries}" = "yes"])

AC_ARG_ENABLE([tests],
        AS_HELP_STRING([--enable-tests], [Compilation of tests code]),
        [enable_tests=${enableval}],
        [enable_tests=yes])
AM_CONDITIONAL([TESTS], [test "${enable_tests}" = "yes"])

AC_CONFIG_FILES([Makefile
                 src/Makefile
                 bin/Makefile
                 t/Makefile])
AC_OUTPUT
