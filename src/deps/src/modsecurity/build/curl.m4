dnl Check for CURL Libraries
dnl Sets:
dnl  CURL_CFLAGS
dnl  CURL_LDADD
dnl  CURL_LDFLAGS
dnl  CURL_VERSION
dnl  CURL_DISPLAY
dnl  CURL_FOUND

AC_DEFUN([CHECK_CURL], [
MSC_CHECK_LIB([CURL], [libcurl], [curl/curl.h], [curl], [-DWITH_CURL], [7.15.1])

# Post-processing: TLSv1.2 version check
if test "x${CURL_FOUND}" = "x1" && test -n "${CURL_VERSION}"; then
    AC_MSG_CHECKING([if libcurl supports TLSv1.2])
    _msc_curl_tlsv2_ver=`echo 7.34.0 | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    _msc_curl_ver=`echo ${CURL_VERSION} | awk -F. '{print (\$ 1 * 1000000) + (\$ 2 * 1000) + \$ 3}'`
    if test "${_msc_curl_tlsv2_ver}" -le "${_msc_curl_ver}" 2>/dev/null; then
        AC_MSG_RESULT([yes])
        CURL_CFLAGS="${CURL_CFLAGS} -DWITH_CURL_SSLVERSION_TLSv1_2"
    else
        AC_MSG_RESULT([no])
    fi

    # Check/warn if GnuTLS is used
    AC_MSG_CHECKING([if libcurl is linked with gnutls])
    _msc_curl_uses_gnutls=`echo ${CURL_LDADD} | grep gnutls | wc -l`
    if test "$_msc_curl_uses_gnutls" -ne 0; then
        AC_MSG_RESULT([yes])
        AC_MSG_NOTICE([NOTE: curl linked with gnutls may be buggy, openssl recommended])
    else
        AC_MSG_RESULT([no])
    fi
fi

]) # AC_DEFUN [CHECK_CURL]
