dnl Check for PCRE Libraries
dnl Sets:
dnl  PCRE_CFLAGS
dnl  PCRE_LDADD
dnl  PCRE_LDFLAGS
dnl  PCRE_VERSION
dnl  PCRE_FOUND

PCRE_CONFIG=""
PCRE_VERSION=""
PCRE_CPPFLAGS=""
PCRE_CFLAGS=""
PCRE_LDFLAGS=""
PCRE_LDADD=""
PCRE_LD_PATH=""

AC_DEFUN([CHECK_PCRE], [
MSC_CHECK_LIB([PCRE], [libpcre], [pcre.h], [pcre], [-DWITH_PCRE])

# Post-processing: JIT detection
if test "x${PCRE_FOUND}" = "x1" && test -n "${PCRE_VERSION}"; then
    AC_MSG_CHECKING([for PCRE JIT])
    _msc_save_CFLAGS=$CFLAGS
    _msc_save_LDFLAGS=$LDFLAGS
    _msc_save_LIBS=$LIBS
    CFLAGS="${PCRE_CFLAGS} ${CFLAGS}"
    LDFLAGS="${PCRE_LDADD} ${LDFLAGS}"
    LIBS="${PCRE_LDADD} ${LIBS}"
    AC_LINK_IFELSE(
        [AC_LANG_PROGRAM([[ #include <pcre.h> ]],
           [[ pcre_jit_exec(NULL, NULL, NULL, 0, 0, 0, NULL, 0, NULL); ]])],
        [ _msc_pcre_jit_available=yes ],
        [:]
    )
    if test "x$_msc_pcre_jit_available" = "xyes"; then
        AC_MSG_RESULT([yes])
        PCRE_CFLAGS="${PCRE_CFLAGS} -DPCRE_HAVE_JIT"
    else
        AC_MSG_RESULT([no])
    fi
    CFLAGS=$_msc_save_CFLAGS
    LDFLAGS=$_msc_save_LDFLAGS
    LIBS=$_msc_save_LIBS
fi

AC_SUBST(PCRE_CONFIG)
AC_SUBST(PCRE_CPPFLAGS)
AC_SUBST(PCRE_LD_PATH)

]) # AC_DEFUN [CHECK_PCRE]
