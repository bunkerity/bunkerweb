dnl Check for MaxMind Libraries
dnl Sets:
dnl  MAXMIND_CFLAGS
dnl  MAXMIND_LDADD
dnl  MAXMIND_LDFLAGS
dnl  MAXMIND_VERSION
dnl  MAXMIND_DISPLAY
dnl  MAXMIND_FOUND

AC_DEFUN([PROG_MAXMIND], [
MSC_CHECK_LIB([MAXMIND], [libmaxminddb], [maxminddb.h], [maxminddb], [-DWITH_MAXMIND])
]) # AC_DEFUN [PROG_MAXMIND]
