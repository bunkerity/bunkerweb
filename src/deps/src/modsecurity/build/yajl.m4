dnl Check for YAJL Libraries
dnl Sets:
dnl  YAJL_CFLAGS
dnl  YAJL_LDADD
dnl  YAJL_LDFLAGS
dnl  YAJL_VERSION
dnl  YAJL_DISPLAY
dnl  YAJL_FOUND

AC_DEFUN([PROG_YAJL], [
MSC_CHECK_LIB([YAJL], [yajl2 yajl], [yajl/yajl_parse.h], [yajl], [-DWITH_YAJL])

# FIX: if the include directory in CFLAGS ends with "include/yajl",
# remove the suffix "/yajl". The library header files are included
# using the prefix (e.g., #include <yajl/yajl_tree.h>), and
# this is even the case for the library itself (e.g.,
# yajl_tree.h includes yajl/yajl_common.h).
_msc_yajl_new_cflags=""
for _msc_yajl_flag in $YAJL_CFLAGS; do
    case "$_msc_yajl_flag" in
        -I*/include/yajl)
            _msc_yajl_new_flag="${_msc_yajl_flag%/yajl}"
            _msc_yajl_new_cflags="$_msc_yajl_new_cflags $_msc_yajl_new_flag"
            ;;
        *)
            _msc_yajl_new_cflags="$_msc_yajl_new_cflags $_msc_yajl_flag"
            ;;
    esac
done
YAJL_CFLAGS="$_msc_yajl_new_cflags"
YAJL_DISPLAY="${YAJL_LDADD}, ${YAJL_CFLAGS}"

]) # AC_DEFUN [PROG_YAJL]
