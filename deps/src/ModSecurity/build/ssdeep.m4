dnl Check for SSDEEP Libraries
dnl CHECK_SSDEEP(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])


AC_DEFUN([CHECK_SSDEEP],
[dnl

# Possible names for the ssdeep library/package (pkg-config)
SSDEEP_POSSIBLE_LIB_NAMES="fuzzy"

# Possible extensions for the library
SSDEEP_POSSIBLE_EXTENSIONS="so so0 la sl dll dylib so.0.0.0"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
SSDEEP_POSSIBLE_PATHS="/usr/lib /usr/local/lib /usr/local/fuzzy /usr/local/libfuzzy /usr/local /opt /usr /usr/lib64 /opt/local"

# Variables to be set by this very own script.
SSDEEP_CFLAGS=""
SSDEEP_LDFLAGS=""
SSDEEP_LDADD=""
SSDEEP_DISPLAY=""

AC_ARG_WITH(
    ssdeep,
    AC_HELP_STRING(
    [--with-ssdeep=PATH],
    [Path to ssdeep prefix]
    )
)


if test "x${with_ssdeep}" == "xno"; then
    AC_DEFINE(HAVE_SSDEEP, 0, [Support for SSDEEP was disabled by the utilization of --without-ssdeep or --with-ssdeep=no])
    AC_MSG_NOTICE([Support for SSDEEP was disabled by the utilization of --without-ssdeep or --with-ssdeep=no])
    SSDEEP_DISABLED=yes
else
    if test "x${with_ssdeep}" == "xyes"; then
        SSDEEP_MANDATORY=yes
        AC_MSG_NOTICE([SSDEEP support was marked as mandatory by the utilization of --with-ssdeep=yes])
    else
        SSDEEP_MANDATORY=no
    fi
    for x in ${SSDEEP_POSSIBLE_PATHS}; do
        CHECK_FOR_SSDEEP_AT(${x})
        if test -n "${SSDEEP_CFLAGS}"; then
            break
        fi
    done
fi


if test -z "${SSDEEP_CFLAGS}"; then
    if test -z "${SSDEEP_MANDATORY}" || test "x${SSDEEP_MANDATORY}" == "xno"; then
        if test -z "${SSDEEP_DISABLED}"; then
            AC_MSG_NOTICE([SSDEEP library was not found])
            SSDEEP_FOUND=0
        else
            SSDEEP_FOUND=2
        fi
    else
        AC_MSG_ERROR([SSDEEP was explicitly referenced but it was not found])
        SSDEEP_FOUND=-1
    fi
else
    SSDEEP_FOUND=1
    AC_MSG_NOTICE([using SSDEEP v${SSDEEP_VERSION}])
    SSDEEP_CFLAGS="-DWITH_SSDEEP ${SSDEEP_CFLAGS}"
    SSDEEP_DISPLAY="${SSDEEP_LDADD} ${SSDEEP_LDFLAGS}, ${SSDEEP_CFLAGS}"
    AC_SUBST(SSDEEP_LDFLAGS)
    AC_SUBST(SSDEEP_LDADD)
    AC_SUBST(SSDEEP_CFLAGS)
    AC_SUBST(SSDEEP_DISPLAY)
fi


AC_SUBST(SSDEEP_FOUND)

]) # AC_DEFUN [CHECK_SSDEEP]


AC_DEFUN([CHECK_FOR_SSDEEP_AT], [
    path=$1
    echo "*** LOOKING AT PATH: " ${path}
    for y in ${SSDEEP_POSSIBLE_EXTENSIONS}; do
        for z in ${SSDEEP_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               ssdeep_lib_path="${path}/"
               ssdeep_lib_name="${z}"
               ssdeep_lib_file="${ssdeep_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               ssdeep_lib_path="${path}/"
               ssdeep_lib_name="${z}"
               ssdeep_lib_file="${ssdeep_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               ssdeep_lib_path="${path}/lib/"
               ssdeep_lib_name="${z}"
               ssdeep_lib_file="${ssdeep_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               ssdeep_lib_path="${path}/lib/x86_64-linux-gnu/"
               ssdeep_lib_name="${z}"
               ssdeep_lib_file="${ssdeep_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/i386-linux-gnu/lib${z}.${y}"; then
               ssdeep_lib_path="${path}/lib/i386-linux-gnu/"
               ssdeep_lib_name="${z}"
               ssdeep_lib_file="${ssdeep_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$ssdeep_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/fuzzy.h"; then
        ssdeep_inc_path="${path}/include"
    elif test -e "${path}/fuzzy.h"; then
        ssdeep_inc_path="${path}"
    elif test -e "${path}/include/fuzzy/fuzzy.h"; then
        ssdeep_inc_path="${path}/include"
    fi

    if test -n "${ssdeep_lib_path}"; then
        AC_MSG_NOTICE([SSDEEP library found at: ${ssdeep_lib_file}])
    fi

    if test -n "${ssdeep_inc_path}"; then
        AC_MSG_NOTICE([SSDEEP headers found at: ${ssdeep_inc_path}])
    fi

    if test -n "${ssdeep_lib_path}" -a -n "${ssdeep_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        SSDEEP_CFLAGS="-I${ssdeep_inc_path}"
        SSDEEP_LDADD="-l${ssdeep_lib_name}"
        SSDEEP_LDFLAGS="-L${ssdeep_lib_path}"
        SSDEEP_DISPLAY="${ssdeep_lib_file}, ${ssdeep_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_SSDEEP_AT]



