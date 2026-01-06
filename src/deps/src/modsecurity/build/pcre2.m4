dnl Check for PCRE2 Libraries
dnl CHECK_PCRE2(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])

AC_DEFUN([PROG_PCRE2], [

# Possible names for the pcre2 library/package (pkg-config)
PCRE2_POSSIBLE_LIB_NAMES="pcre2 pcre2-8 libpcre2-8"

# Possible extensions for the library
PCRE2_POSSIBLE_EXTENSIONS="so so0 la sl dll dylib so.0.0.0"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
PCRE2_POSSIBLE_PATHS="/usr/lib /usr/local/lib /usr/local/libpcre2-8 /usr/local/pcre2 /usr/local /opt/libpcre2-8 /opt/pcre2 /opt /usr /usr/lib64 /opt/local"

# Variables to be set by this very own script.
PCRE2_VERSION=""
PCRE2_CFLAGS=""
PCRE2_CPPFLAGS=""
PCRE2_LDADD=""
PCRE2_LDFLAGS=""

AC_ARG_WITH(
    pcre2,
    [AS_HELP_STRING([--with-pcre2=PATH],[Path to pcre2 prefix or config script])]
)

if test "x${with_pcre2}" == "xno"; then
    AC_DEFINE(HAVE_PCRE2, 0, [Support for PCRE2 was disabled by the utilization of --without-pcre2 or --with-pcre2=no])
    AC_MSG_NOTICE([Support for PCRE2 was disabled by the utilization of --without-pcre2 or --with-pcre2=no])
    PCRE2_DISABLED=yes
else
     PCRE2_MANDATORY=yes
     AC_MSG_NOTICE([PCRE2 is enabled by default.])
#    if test "x${with_pcre2}" == "xyes"; then
#        PCRE2_MANDATORY=yes
#        AC_MSG_NOTICE([PCRE2 support was marked as mandatory by the utilization of --with-pcre2=yes])
#    fi
#        for x in ${PCRE2_POSSIBLE_LIB_NAMES}; do
#            CHECK_FOR_PCRE2_AT(${x})
#            if test -n "${PCRE2_VERSION}"; then
#                break
#            fi
#        done

#    if test "x${with_pcre2}" != "xyes" or test "x${with_pcre2}" == "xyes"; then
        if test "x${with_pcre2}" == "x" || test "x${with_pcre2}" == "xyes"; then
            # Nothing about PCRE2 was informed, using the pkg-config to figure things out.
            if test -n "${PKG_CONFIG}"; then
                PCRE2_PKG_NAME=""
                for x in ${PCRE2_POSSIBLE_LIB_NAMES}; do
                    if ${PKG_CONFIG} --exists ${x}; then
                        PCRE2_PKG_NAME="$x"
                        break
                    fi
                done
            fi
            AC_MSG_NOTICE([Nothing about PCRE2 was informed during the configure phase. Trying to detect it on the platform...])
            if test -n "${PCRE2_PKG_NAME}"; then
                # Package was found using the pkg-config scripts
                PCRE2_VERSION="`${PKG_CONFIG} ${PCRE2_PKG_NAME} --modversion`"
                PCRE2_CFLAGS="`${PKG_CONFIG} ${PCRE2_PKG_NAME} --cflags`"
                PCRE2_LDADD="`${PKG_CONFIG} ${PCRE2_PKG_NAME} --libs-only-l`"
                PCRE2_LDFLAGS="`${PKG_CONFIG} ${PCRE2_PKG_NAME} --libs-only-L --libs-only-other`"
                PCRE2_DISPLAY="${PCRE2_LDADD}, ${PCRE2_CFLAGS}"
            else
                # If pkg-config did not find anything useful, go over file lookup.
                for x in ${PCRE2_POSSIBLE_PATHS}; do
                    CHECK_FOR_PCRE2_AT(${x})
                    if test -n "${PCRE2_VERSION}"; then
                        break
                    fi
                done
            fi
        fi
        if test "x${with_pcre2}" != "x"; then
            # An specific path was informed, lets check.
            PCRE2_MANDATORY=yes
            CHECK_FOR_PCRE2_AT(${with_pcre2})
        fi
#    fi
fi

if test -z "${PCRE2_LDADD}"; then
    if test -z "${PCRE2_MANDATORY}"; then
        if test -z "${PCRE2_DISABLED}"; then
            AC_MSG_NOTICE([PCRE2 library was not found])
            PCRE2_FOUND=0
        else
            PCRE2_FOUND=2
        fi
    else
        AC_MSG_ERROR([PCRE2 was explicitly referenced but it was not found])
        PCRE2_FOUND=-1
    fi
else
    if test -z "${PCRE2_MANDATORY}"; then
        PCRE2_FOUND=2
        AC_MSG_NOTICE([PCRE2 is disabled by default.])
    else
        PCRE2_FOUND=1
        PCRE2_CFLAGS="${PCRE2_CFLAGS}"
        PCRE2_DISPLAY="${PCRE2_LDADD}, ${PCRE2_CFLAGS}"
        AC_MSG_NOTICE([using PCRE2_VERSION ${PCRE2_VERSION}])
        AC_MSG_NOTICE([using PCRE2_LDADD ${PCRE2_LDADD}])
        AC_MSG_NOTICE([using PCRE2_LIBS ${PCRE2_LIBS}])
        AC_MSG_NOTICE([using PCRE2_LDFLAGS ${PCRE2_LDFLAGS}])
        AC_MSG_NOTICE([using PCRE2_CFLAGS ${PCRE2_CFLAGS}])
        AC_MSG_NOTICE([using PCRE2_DISPLAY ${PCRE2_DISPLAY}])
        AC_SUBST(PCRE2_VERSION)
        AC_SUBST(PCRE2_LDADD)
        AC_SUBST(PCRE2_LIBS)
        AC_SUBST(PCRE2_LDFLAGS)
        AC_SUBST(PCRE2_CFLAGS)
        AC_SUBST(PCRE2_DISPLAY)
    fi
fi


AC_SUBST(PCRE2_FOUND)

]) # AC_DEFUN [PROG_PCRE2]


AC_DEFUN([CHECK_FOR_PCRE2_AT], [
    path=$1
    echo "*** LOOKING AT PATH: " ${path}
    for y in ${PCRE2_POSSIBLE_EXTENSIONS}; do
        for z in ${PCRE2_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               pcre2_lib_path="${path}/"
               pcre2_lib_name="${z}"
               pcre2_lib_file="${pcre2_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               pcre2_lib_path="${path}/"
               pcre2_lib_name="${z}"
               pcre2_lib_file="${pcre2_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               pcre2_lib_path="${path}/lib/"
               pcre2_lib_name="${z}"
               pcre2_lib_file="${pcre2_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               pcre2_lib_path="${path}/lib/x86_64-linux-gnu/"
               pcre2_lib_name="${z}"
               pcre2_lib_file="${pcre2_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/i386-linux-gnu/lib${z}.${y}"; then
               pcre2_lib_path="${path}/lib/i386-linux-gnu/"
               pcre2_lib_name="${z}"
               pcre2_lib_file="${pcre2_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$pcre2_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/pcre2.h"; then
        pcre2_inc_path="${path}/include"
    elif test -e "${path}/pcre2.h"; then
        pcre2_inc_path="${path}"
    elif test -e "${path}/include/pcre2/pcre2.h"; then
        pcre2_inc_path="${path}/include"
    fi

    if test -n "${pcre2_lib_path}"; then
        AC_MSG_NOTICE([PCRE2 library found at: ${pcre2_lib_file}])
    fi

    if test -n "${pcre2_inc_path}"; then
        AC_MSG_NOTICE([PCRE2 headers found at: ${pcre2_inc_path}])
    fi

    if test -n "${pcre2_lib_path}" -a -n "${pcre2_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        PCRE2_CFLAGS="-I${pcre2_inc_path}"
        PCRE2_LDADD="-l${pcre2_lib_name}"
        PCRE2_LDFLAGS="-L${pcre2_lib_path}"
        PCRE2_DISPLAY="${pcre2_lib_file}, ${pcre2_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_PCRE2_AT]
