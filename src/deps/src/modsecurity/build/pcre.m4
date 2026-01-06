dnl Check for PCRE Libraries
dnl CHECK_PCRE(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])
dnl Sets:
dnl  PCRE_CFLAGS
dnl  PCRE_LIBS

PCRE_CONFIG=""
PCRE_VERSION=""
PCRE_CPPFLAGS=""
PCRE_CFLAGS=""
PCRE_LDFLAGS=""
PCRE_LDADD=""
PCRE_LD_PATH=""

AC_DEFUN([CHECK_PCRE],
[dnl

AC_ARG_WITH(
    pcre,
    [AS_HELP_STRING([--with-pcre=PATH],[Path to pcre prefix or config script])],
    [test_paths="${with_pcre}"],
    [test_paths="/usr/local/libpcre /usr/local/pcre /usr/local /opt/libpcre /opt/pcre /opt /usr /opt/local"])

if test "x${with_pcre}" == "x" && test "x${with_pcre}" != "xno"; then
    AC_MSG_NOTICE([Support for pcre not requested; omitting check for pcre])
else

    AC_MSG_CHECKING([for libpcre config script])

    AC_CHECK_PROG([PCRE_CONFIG_IN_ENV], [pcre-config], [yes], [no])

    if test "$PCRE_CONFIG_IN_ENV" = "yes"; then
        AC_MSG_NOTICE([pcre-config found in envinronment])

        PCRE_CONFIG=pcre-config
        pcre_path="no"
    else
        AC_MSG_NOTICE([pcre-config not found in environment. checking known paths])

        for x in ${test_paths}; do
            dnl # Determine if the script was specified and use it directly
            if test ! -d "$x" -a -e "$x"; then
                PCRE_CONFIG=$x
                pcre_path="no"
                break
            fi

            dnl # Try known config script names/locations
            for PCRE_CONFIG in pcre-config; do
                if test -e "${x}/bin/${PCRE_CONFIG}"; then
                    pcre_path="${x}/bin"
                    break
                elif test -e "${x}/${PCRE_CONFIG}"; then
                    pcre_path="${x}"
                    break
                else
                    pcre_path=""
                fi
            done
            if test -n "$pcre_path"; then
                break
            fi
        done
    fi

    if test -n "${pcre_path}"; then
        if test "${pcre_path}" != "no"; then
            PCRE_CONFIG="${pcre_path}/${PCRE_CONFIG}"
        fi
        AC_MSG_RESULT([${PCRE_CONFIG}])
        PCRE_VERSION="`${PCRE_CONFIG} --version`"
        if test ! -z "${PCRE_VERSION}"; then AC_MSG_NOTICE(pcre VERSION: $PCRE_VERSION); fi
        PCRE_CFLAGS="`${PCRE_CONFIG} --cflags`"
        if test ! -z "${PCRE_CFLAGS}"; then AC_MSG_NOTICE(pcre CFLAGS: $PCRE_CFLAGS); fi
        PCRE_LDADD="`${PCRE_CONFIG} --libs`"
        if test ! -z "${PCRE_LDADD}"; then AC_MSG_NOTICE(pcre LDADD: $PCRE_LDADD); fi
        PCRE_LD_PATH="/`${PCRE_CONFIG} --libs | cut -d'/' -f2,3,4,5,6 | cut -d ' ' -f1`"
        if test ! -z "${PCRE_LD_PATH}"; then AC_MSG_NOTICE(pcre PCRE_LD_PATH: $PCRE_LD_PATH); fi
    else
        AC_MSG_RESULT([no])
    fi

    if test -n "${PCRE_VERSION}"; then
        AC_MSG_CHECKING(for PCRE JIT)
        save_CFLAGS=$CFLAGS
        save_LDFLAGS=$LDFLAGS
        save_LIBS=$LIBS
        CFLAGS="${PCRE_CFLAGS} ${CFLAGS}"
        LDFLAGS="${PCRE_LDADD} ${LDFLAGS}"
        LIBS="${PCRE_LDADD} ${LIBS}"
        AC_LINK_IFELSE(
            [AC_LANG_PROGRAM([[ #include <pcre.h> ]],
               [[ pcre_jit_exec(NULL, NULL, NULL, 0, 0, 0, NULL, 0, NULL); ]])],
            [ pcre_jit_available=yes ],
            [:]
        )

        if test "x$pcre_jit_available" = "xyes"; then
            AC_MSG_RESULT(yes)
            PCRE_CFLAGS="${PCRE_CFLAGS} -DPCRE_HAVE_JIT"
        else
            AC_MSG_RESULT(no)
        fi
        CFLAGS=$save_CFLAGS
        LDFLAGS=$save_LDFLAGS
        LIBS=$save_LIBS
    fi

    PCRE_CFLAGS="-DWITH_PCRE ${PCRE_CFLAGS}"
    AC_SUBST(PCRE_CONFIG)
    AC_SUBST(PCRE_VERSION)
    AC_SUBST(PCRE_CPPFLAGS)
    AC_SUBST(PCRE_CFLAGS)
    AC_SUBST(PCRE_LDFLAGS)
    AC_SUBST(PCRE_LDADD)
    AC_SUBST(PCRE_LD_PATH)

    if test -z "${PCRE_VERSION}"; then
        AC_MSG_NOTICE([*** pcre library not found.])
        ifelse([$2], , AC_MSG_ERROR([pcre library is required]), $2)
    else
        AC_MSG_NOTICE([using pcre v${PCRE_VERSION}])
        ifelse([$1], , , $1) 
        PCRE_LDADD="${PCRE_LDADD} -lpcre"
    fi 
fi
])
