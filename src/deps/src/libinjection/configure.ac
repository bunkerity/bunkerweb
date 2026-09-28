AC_PREREQ([2.60])

AC_INIT(
    [libinjection],
    m4_esyscmd([build-aux/git-version-gen .tarball-version]),
    [https://github.com/libinjection/libinjection/issues],
    [libinjection],
    [https://github.com/libinjection/libinjection])

AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_MACRO_DIR([build-aux/m4])
AC_CANONICAL_HOST

AM_INIT_AUTOMAKE([1.11 check-news foreign silent-rules subdir-objects
    -Wall -Werror])
AM_MAINTAINER_MODE

# Checks for programs.
AC_PROG_CXX
AC_PROG_AWK
AC_PROG_CC
AC_PROG_CPP
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_MAKE_SET
AC_PROG_MKDIR_P

# Checks for typedefs, structures, and compiler characteristics.
AC_TYPE_SIZE_T

# Checks for library functions.
AC_FUNC_MALLOC
AC_CHECK_FUNCS([memchr memset strchr strstr])

AX_COMPILER_VERSION
AX_COMPILER_VENDOR

m4_ifdef([AM_PROG_AR], [AM_PROG_AR])
m4_ifdef([AM_SILENT_RULES], [AM_SILENT_RULES([yes])])

AC_DEFINE([__STDC_FORMAT_MACROS], [], [Description])

PKG_PROG_PKG_CONFIG

dnl Enable gprof suport.
AC_ARG_ENABLE([gprof],
              AS_HELP_STRING([--enable-gprof],
                             [build binaries with gprof support]), 
              [use_gprof=$enableval], [use_gprof=no])
if test "$use_gprof" = yes; then
  CFLAGS="$CFLAGS -O2 -pg"
  LDFLAGS="$LDFLAGS -pg"
fi
AM_CONDITIONAL([GPROF], [test "$use_gprof" = yes])

dnl Enable gcov suport.
AC_ARG_ENABLE([gcov],
              AS_HELP_STRING([--enable-gcov],
                             [build binaries with gcov support]), 
              [use_gcov=$enableval], [use_gcov=no])
if test "$use_gcov" = yes; then
  CFLAGS="$CFLAGS -O0 -fprofile-arcs -ftest-coverage"
  LDFLAGS="$LDFLAGS -fprofile-arcs"
fi
AM_CONDITIONAL([GCOV], [test "$use_gcov" = yes])

dnl Enable hardened build.
AC_ARG_ENABLE([hardened],
              AS_HELP_STRING([--enable-hardened],
                             [build hardened binaries]), 
              [use_hardened=$enableval], [use_hardened=no])

dnl Enable debug build.
AC_ARG_ENABLE([debug],
              AS_HELP_STRING([--enable-debug],
                             [enable debugging. If CFLAGS are set, this
                              option will not change them]),
              [], [enable_debug=no])

dnl Enable optimizations.
AC_ARG_ENABLE([optimize],
              AS_HELP_STRING([--enable-optimize],
                             [enable optimizations. If CFLAGS are set,
                              this option will not change them]),
              [], [enable_optimize=no])

dnl Enable sanitizers.
AC_ARG_ENABLE([sanitizers],
              AS_HELP_STRING([--enable-sanitizers],
                             [enable ASAN ans UBSAN. If CFLAGS are set,
                              this option will not change them]),
              [], [enable_sanitizers=no])

dnl Enable fuzzers.
AC_ARG_ENABLE([fuzzers],
              AS_HELP_STRING([--enable-fuzzers],
                             [enable fuzzers; you must use clang compiler]),
              [], [enable_fuzzers=no])

LT_INIT
AC_SUBST([LIBTOOL_DEPS])

AC_PATH_TOOL(CLANG, clang)
AC_PATH_TOOL(GCOV, gcov)
AC_PATH_PROG(LCOV, lcov)
AC_PATH_PROG(GENHTML, genhtml)
AC_PATH_TOOL(CPPCHECK, cppcheck)
AC_PATH_TOOL(VALGRIND, valgrind)

###############################################################################
# Debug/Optimization checks.
###############################################################################
# Check if we should enable debugging, optimization. Note we only
# update CFLAGS if none are provided.
AM_CONDITIONAL([DEBUG], [test x"$enable_debug" = "xyes"])
AM_CONDITIONAL([OPTIMIZE], [test x"$enable_optimize" = "xyes"])
debug_flags="-g1"
if test "x$enable_debug" = "xyes"; then
  debug_flags="-g -fno-omit-frame-pointer"
elif test "x$enable_optimize" = "xyes"; then
  debug_flags=""
fi
if test "x$enable_optimize" = "xyes"; then
  optimize_flags="-O3"
else
  optimize_flags="-O0"
fi

###############################################################################
# Hardening.
###############################################################################
AM_CONDITIONAL([HARDENED], [test x"$enable_hardened" = "xyes"])
if test "$use_hardened" = yes; then
  hardened_flags="-g -fPIE -pie -ansi -fPIC -fstack-protector \
                 --param ssp-buffer-size=4 -Wextra -Wformat -Wformat-security \
                 -Werror=format-security -Wcast-align -Wshadow -Wpointer-arith \
                 -Wcast-qual -Wstack-protector -D_FORTIFY_SOURCE=2 -pedantic"
fi

compiler_flags="-g -fpic -Weverything -Wno-unused-macros -Wno-padded \
                -Wno-covered-switch-default \
                -Wno-disabled-macro-expansion -Wno-unused-local-typedefs"

###############################################################################
# Sanitizers.
###############################################################################
AM_CONDITIONAL([SANITIZERS], [test x"$enable_sanitizers" = "xyes"])
if test "$enable_sanitizers" = yes; then
  sanitizers_flags="-fsanitize=address,undefined -fno-omit-frame-pointer"
  sanitizers_link_flags="-fsanitize=address,undefined"
fi

###############################################################################
# Fuzzing.
###############################################################################
AM_CONDITIONAL([FUZZERS], [test x"$enable_fuzzers" = "xyes"])
if test "$enable_fuzzers" = yes; then
  AX_CHECK_COMPILE_FLAG([-fsanitize=fuzzer],,[AC_MSG_ERROR("Fuzzing not supported by the compiler; you must use clang")])
  LIB_FUZZING_ENGINE=-fsanitize=fuzzer
  fuzzers_flags="-fsanitize=fuzzer-no-link"
  BUILD_FUZZTARGETS=1
fi
AM_CONDITIONAL([BUILD_FUZZTARGETS], [test "x$enable_fuzzers" = "xyes"])
AC_SUBST(BUILD_FUZZTARGETS)
AC_SUBST(LIB_FUZZING_ENGINE)

# Now that we have all flags, check them
AS_IF([test "x${ac_cv_env_CFLAGS_set}" = "x"],
      [
          AX_APPEND_COMPILE_FLAGS([$debug_flags $compiler_flags $optimize_flags $hardened_flags $sanitizers_flags $fuzzers_flags],
          [CFLAGS], [])
      ])
AS_IF([test "x${ac_cv_env_LDFLAGS_set}" = "x"],
      [
          AX_APPEND_LINK_FLAGS([$sanitizers_link_flags],
          [LDFLAGS], [])
      ])

if test x$use_gcov = xyes; then
  if test x$LCOV = x; then
    AC_MSG_ERROR("lcov testing requested but lcov not found")
  fi
  if test x$GCOV = x; then
    AC_MSG_ERROR("lcov testing requested but gcov not found")
  fi
  if test x$GENHTML = x; then
    AC_MSG_ERROR("lcov testing requested but genhtml not found")
  fi
  LCOV="$LCOV --gcov-tool=$GCOV --rc lcov_branch_coverage=1"
  GENHTML="$GENHTML --branch-coverage"
  AX_CHECK_COMPILE_FLAG([--coverage],[CXXFLAGS="$CXXFLAGS --coverage"],
    [AC_MSG_ERROR("lcov testing requested but --coverage flag does not work")])
fi

# Libinjection version to allow embedding
AC_DEFINE_UNQUOTED([LIBINJECTION_VERSION], [["$PACKAGE_VERSION"]])

# Output files
AC_CONFIG_FILES([
	Makefile
	src/Makefile
	src/fuzz/Makefile
    libinjection.pc
])

AC_OUTPUT
