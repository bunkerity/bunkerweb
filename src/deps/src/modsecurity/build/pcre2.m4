dnl Check for PCRE2 Libraries
dnl PCRE2 is enabled by default (mandatory unless --with-pcre is used).
dnl Sets:
dnl  PCRE2_CFLAGS
dnl  PCRE2_LDADD
dnl  PCRE2_LDFLAGS
dnl  PCRE2_VERSION
dnl  PCRE2_DISPLAY
dnl  PCRE2_FOUND

AC_DEFUN([PROG_PCRE2], [
MSC_CHECK_LIB([PCRE2], [libpcre2-8 pcre2-8 pcre2], [pcre2.h], [pcre2-8], [])
]) # AC_DEFUN [PROG_PCRE2]
