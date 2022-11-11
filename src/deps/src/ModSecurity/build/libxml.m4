dnl Check for LIBXML2 Libraries
dnl CHECK_LIBXML2(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])
dnl Sets:
dnl  LIBXML2_CFLAGS
dnl  LIBXML2_LIBS

LIBXML2_CONFIG=""
LIBXML2_VERSION=""
LIBXML2_CFLAGS=""
LIBXML2_CPPFLAGS=""
LIBXML2_LDADD=""
LIBXML2_LDFLAGS=""

AC_DEFUN([CHECK_LIBXML2], [

AC_ARG_WITH(
    libxml,
    [AC_HELP_STRING([--with-libxml=PATH],[Path to libxml2 prefix or config script])],
    [test_paths="${with_libxml}"],
    [test_paths="/usr/local/libxml2 /usr/local/xml2 /usr/local/xml /usr/local /opt/libxml2 /opt/libxml /opt/xml2 /opt/xml /opt /usr"])

AC_MSG_CHECKING([for libxml2 config script])

for x in ${test_paths}; do
    dnl # Determine if the script was specified and use it directly
    if test ! -d "$x" -a -e "$x"; then
        LIBXML2_CONFIG=$x
        libxml2_path="no"
        break
    fi

    dnl # Try known config script names/locations
    for LIBXML2_CONFIG in xml2-config xml-2-config xml-config; do
        if test -e "${x}/bin/${LIBXML2_CONFIG}"; then
            libxml2_path="${x}/bin"
            break
        elif test -e "${x}/${LIBXML2_CONFIG}"; then
            libxml2_path="${x}"
            break
        else
            libxml2_path=""
        fi
    done
    if test -n "$libxml2_path"; then
        break
    fi
done

if test -n "${libxml2_path}"; then
    if test "${libxml2_path}" != "no"; then
        LIBXML2_CONFIG="${libxml2_path}/${LIBXML2_CONFIG}"
    fi
    AC_MSG_RESULT([${LIBXML2_CONFIG}])
    LIBXML2_VERSION=`${LIBXML2_CONFIG} --version | sed 's/^[[^0-9]][[^[:space:]]][[^[:space:]]]*[[[:space:]]]*//'`
    if test ! -z "${LIBXML2_VERSION}"; then AC_MSG_NOTICE(xml VERSION: $LIBXML2_VERSION); fi
    LIBXML2_CFLAGS="`${LIBXML2_CONFIG} --cflags` -DWITH_LIBXML2"
    if test ! -z "${LIBXML2_CFLAGS}"; then AC_MSG_NOTICE(xml CFLAGS: $LIBXML2_CFLAGS); fi
    LIBXML2_LDADD="`${LIBXML2_CONFIG} --libs`"
    if test ! -z "${LIBXML2_LDADD}"; then AC_MSG_NOTICE(xml LDADD: $LIBXML2_LDADD); fi

    AC_MSG_CHECKING([if libxml2 is at least v2.6.29])
    libxml2_min_ver=`echo 2.6.29 | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    libxml2_ver=`echo ${LIBXML2_VERSION} | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    if test "$libxml2_ver" -ge "$libxml2_min_ver"; then
        AC_MSG_RESULT([yes, $LIBXML2_VERSION])
    else
        AC_MSG_RESULT([no, $LIBXML2_VERSION])
        AC_MSG_ERROR([NOTE: libxml2 library must be at least 2.6.29])
    fi

else
    AC_MSG_RESULT([no])
fi

AC_SUBST(LIBXML2_CONFIG)
AC_SUBST(LIBXML2_VERSION)
AC_SUBST(LIBXML2_CFLAGS)
AC_SUBST(LIBXML2_CPPFLAGS)
AC_SUBST(LIBXML2_LDADD)
AC_SUBST(LIBXML2_LDFLAGS)


if test "x${with_libxml}" == "xno"; then
    LIBXML2_DISABLED=yes
else
    if test "x${with_libxml}" != "x"; then
        LIBXML2_MANDATORY=yes
    fi
fi

if test -z "${LIBXML2_VERSION}"; then
    AC_MSG_NOTICE([*** libxml2 library not found.])
    if test -z "${LIBXML2_MANDATORY}"; then
        if test -z "${LIBXML2_DISABLED}"; then
            LIBXML2_FOUND=0
        else
            LIBXML2_FOUND=2
        fi
    else
        AC_MSG_ERROR([Libxml2 was explicitly referenced but it was not found])
        LIBXML2_FOUND=-1
    fi
else
    LIBXML2_FOUND=1
    AC_MSG_NOTICE([using libxml2 v${LIBXML2_VERSION}])
    LIBXML2_DISPLAY="${LIBXML2_LDADD}, ${LIBXML2_CFLAGS}"
fi

AC_SUBST(LIBXML2_FOUND)
AC_SUBST(LIBXML2_DISPLAY)
])
