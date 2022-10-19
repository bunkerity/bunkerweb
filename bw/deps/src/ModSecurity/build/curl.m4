dnl Check for CURL Libraries
dnl CHECK_CURL(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])
dnl Sets:
dnl  CURL_CFLAGS
dnl  CURL_LIBS

CURL_CONFIG=""
CURL_VERSION=""
CURL_CPPFLAGS=""
CURL_CFLAGS=""
CURL_LDFLAGS=""
CURL_LDADD=""
CURL_MIN_VERSION="7.15.1"

AC_DEFUN([CHECK_CURL], [


AC_ARG_WITH(
    curl,
    [AC_HELP_STRING([--with-curl=PATH],[Path to curl prefix or config script])],
    [test_paths="${with_curl}"],
    [test_paths="/usr/local/libcurl /usr/local/curl /usr/local /opt/libcurl /opt/curl /opt /usr"])

AC_MSG_CHECKING([for libcurl config script])

for x in ${test_paths}; do
    dnl # Determine if the script was specified and use it directly
    if test ! -d "$x" -a -e "$x"; then
        CURL_CONFIG=$x
        curl_path="no"
        break
    fi

    dnl # Try known config script names/locations
    for CURL_CONFIG in curl-config; do
        if test -e "${x}/bin/${CURL_CONFIG}"; then
            curl_path="${x}/bin"
            break
        elif test -e "${x}/${CURL_CONFIG}"; then
            curl_path="${x}"
            break
        else
            curl_path=""
        fi
    done
    if test -n "$curl_path"; then
        break
    fi
done

if test -n "${curl_path}"; then
    if test "${curl_path}" != "no"; then
        CURL_CONFIG="${curl_path}/${CURL_CONFIG}"
    fi
    AC_MSG_RESULT([${CURL_CONFIG}])
    CURL_VERSION=`${CURL_CONFIG} --version | sed 's/^[[^0-9]][[^[:space:]]][[^[:space:]]]*[[[:space:]]]*//' | tr '\r\n' ' '`
    if test ! -z "${CURL_VERSION}"; then AC_MSG_NOTICE(curl VERSION: $CURL_VERSION); fi
    CURL_CFLAGS="`${CURL_CONFIG} --cflags`"
    if test ! -z "${CURL_CFLAGS}"; then AC_MSG_NOTICE(curl CFLAGS: $CURL_CFLAGS); fi
    CURL_LDADD="`${CURL_CONFIG} --libs`"
    if test ! -z "${CURL_CONFIG}"; then AC_MSG_NOTICE(curl LDADD: $CURL_LIBS); fi

    dnl # Check version is ok
    AC_MSG_CHECKING([if libcurl is at least v${CURL_MIN_VERSION}])
    curl_min_ver=`echo ${CURL_MIN_VERSION} | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    curl_ver=`echo ${CURL_VERSION} | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    if test "$curl_min_ver" -le "$curl_ver"; then
        AC_MSG_RESULT([yes, $CURL_VERSION])
	curl_tlsv2_ver=`echo 7.34.0 | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
	if test "$curl_tlsv2_ver" -le "$curl_ver"; then
	    CURL_CFLAGS="${CURL_CFLAGS} -DWITH_CURL_SSLVERSION_TLSv1_2"
	fi
	CURL_CFLAGS="${CURL_CFLAGS} -DWITH_CURL"
    else
        AC_MSG_RESULT([no, $CURL_VERSION])
        AC_MSG_NOTICE([NOTE: curl library may be too old])
    fi

    dnl # Check/warn if GnuTLS is used
    AC_MSG_CHECKING([if libcurl is linked with gnutls])
    curl_uses_gnutls=`echo ${CURL_LIBS} | grep gnutls | wc -l`
    if test "$curl_uses_gnutls" -ne 0; then
        AC_MSG_RESULT([yes])
        AC_MSG_NOTICE([NOTE: curl linked with gnutls may be buggy, openssl recommended])
        CURL_USES_GNUTLS=yes
    else
        AC_MSG_RESULT([no])
        CURL_USES_GNUTLS=no
    fi

else
    AC_MSG_RESULT([no])
fi

AC_SUBST(CURL_CONFIG)
AC_SUBST(CURL_VERSION)
AC_SUBST(CURL_CPPFLAGS)
AC_SUBST(CURL_CFLAGS)
AC_SUBST(CURL_LDFLAGS)
AC_SUBST(CURL_LDADD)
AC_SUBST(CURL_USES_GNUTLS)

if test "x${with_curl}" == "xno"; then
    CURL_DISABLED=yes
else
    if test "x${with_curl}" != "x"; then
        CURL_MANDATORY=yes
    fi
fi

if test -z "${CURL_VERSION}"; then
    AC_MSG_NOTICE([*** curl library not found.])
    if test -z "${CURL_MANDATORY}"; then
        if test -z "${CURL_DISABLED}"; then
            CURL_FOUND=0
        else
            CURL_FOUND=2
        fi
    else
        AC_MSG_ERROR([Curl was explicitly referenced but it was not found])
        CURL_FOUND=-1
    fi
else
    CURL_FOUND=1
    AC_MSG_NOTICE([using curl v${CURL_VERSION}])
    CURL_DISPLAY="${CURL_LDADD}, ${CURL_CFLAGS}"
fi

AC_SUBST(CURL_FOUND)
AC_SUBST(CURL_DISPLAY)
])
