dnl Check for GeoIP Libraries
dnl Sets:
dnl  GEOIP_CFLAGS
dnl  GEOIP_LDADD
dnl  GEOIP_LDFLAGS
dnl  GEOIP_VERSION
dnl  GEOIP_DISPLAY
dnl  GEOIP_FOUND

AC_DEFUN([PROG_GEOIP], [
MSC_CHECK_LIB([GEOIP], [geoip2 geoip GeoIP], [GeoIPCity.h], [GeoIP], [-DWITH_GEOIP])
]) # AC_DEFUN [PROG_GEOIP]
