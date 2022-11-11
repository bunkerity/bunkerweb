dnl Check for YAJL Libraries
dnl CHECK_YAJL(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])

AC_DEFUN([PROG_YAJL], [

# Needed if pkg-config will be used.
AC_REQUIRE([PKG_PROG_PKG_CONFIG])


# Possible names for the yajl library/package (pkg-config)
YAJL_POSSIBLE_LIB_NAMES="yajl2 yajl"

# Possible extensions for the library
YAJL_POSSIBLE_EXTENSIONS="so la sl dll dylib"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
YAJL_POSSIBLE_PATHS="/usr/lib /usr/local/lib /usr/local/libyajl /usr/local/yajl /usr/local /opt/libyajl /opt/yajl /opt /usr /usr/lib64"

# Variables to be set by this very own script.
YAJL_VERSION=""
YAJL_CFLAGS=""
YAJL_CPPFLAGS=""
YAJL_LDADD=""
YAJL_LDFLAGS=""

AC_ARG_WITH(
    yajl,
    AC_HELP_STRING(
      [--with-yajl=PATH],
      [Path to yajl prefix or config script]
    )
)

if test "x${with_yajl}" == "xno"; then
    AC_DEFINE(HAVE_GEOIP, 0, [Support for GeoIP was disabled by the utilization of --without-yajl or --with-yajl=no])
    AC_MSG_NOTICE([Support for GeoIP was disabled by the utilization of --without-yajl or --with-yajl=no])
    YAJL_DISABLED=yes
else
    if test "x${with_yajl}" == "xyes"; then
        YAJL_MANDATORY=yes
        AC_MSG_NOTICE([GeoIP support was marked as mandatory by the utilization of --with-yajl=yes])
    fi
#        for x in ${YAJL_POSSIBLE_LIB_NAMES}; do
#            CHECK_FOR_YAJL_AT(${x})
#            if test -n "${YAJL_VERSION}"; then
#                break
#            fi
#        done

#    if test "x${with_yajl}" != "xyes" or test "x${with_yajl}" == "xyes"; then
        if test "x${with_yajl}" == "x" || test "x${with_yajl}" == "xyes"; then
            # Nothing about GeoIP was informed, using the pkg-config to figure things out.
            if test -n "${PKG_CONFIG}"; then
                YAJL_PKG_NAME=""
                for x in ${YAJL_POSSIBLE_LIB_NAMES}; do
                    if ${PKG_CONFIG} --exists ${x}; then
                        YAJL_PKG_NAME="$x"
                        break
                    fi
                done
            fi
            AC_MSG_NOTICE([Nothing about GeoIP was informed during the configure phase. Trying to detect it on the platform...])
            if test -n "${YAJL_PKG_NAME}"; then
                # Package was found using the pkg-config scripts
                YAJL_VERSION="`${PKG_CONFIG} ${YAJL_PKG_NAME} --modversion`"
                YAJL_CFLAGS="`${PKG_CONFIG} ${YAJL_PKG_NAME} --cflags`"
                YAJL_LDADD="`${PKG_CONFIG} ${YAJL_PKG_NAME} --libs-only-l`"
                YAJL_LDFLAGS="`${PKG_CONFIG} ${YAJL_PKG_NAME} --libs-only-L --libs-only-other`"
                YAJL_DISPLAY="${YAJL_LDADD}, ${YAJL_CFLAGS}"
            else
                # If pkg-config did not find anything useful, go over file lookup.
                for x in ${YAJL_POSSIBLE_LIB_NAMES}; do
                    CHECK_FOR_YAJL_AT(${x})
                    if test -n "${YAJL_VERSION}"; then
                        break
                    fi
                done
            fi
        fi
        if test "x${with_yajl}" != "x"; then
            # An specific path was informed, lets check.
            YAJL_MANDATORY=yes
            CHECK_FOR_YAJL_AT(${with_yajl})
        fi
#    fi
fi

if test -z "${YAJL_LDADD}"; then
    if test -z "${YAJL_MANDATORY}"; then
        if test -z "${YAJL_DISABLED}"; then
            AC_MSG_NOTICE([YAJL library was not found])
            YAJL_FOUND=0
        else
            YAJL_FOUND=2
        fi
    else
        AC_MSG_ERROR([YAJL was explicitly referenced but it was not found])
        YAJL_FOUND=-1
    fi
else
    YAJL_FOUND=1
    AC_MSG_NOTICE([using YAJL v${YAJL_VERSION}])
    YAJL_CFLAGS="-DWITH_YAJL ${YAJL_CFLAGS}"
    YAJL_DISPLAY="${YAJL_LDADD}, ${YAJL_CFLAGS}"
    AC_SUBST(YAJL_VERSION)
    AC_SUBST(YAJL_LDADD)
    AC_SUBST(YAJL_LIBS)
    AC_SUBST(YAJL_LDFLAGS)
    AC_SUBST(YAJL_CFLAGS)
    AC_SUBST(YAJL_DISPLAY)
fi



AC_SUBST(YAJL_FOUND)

]) # AC_DEFUN [PROG_YAJL]


AC_DEFUN([CHECK_FOR_YAJL_AT], [
    path=$1
    for y in ${YAJL_POSSIBLE_EXTENSIONS}; do
        for z in ${YAJL_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               yajl_lib_path="${path}/"
               yajl_lib_name="${z}"
               yajl_lib_file="${yajl_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               yajl_lib_path="${path}/"
               yajl_lib_name="${z}"
               yajl_lib_file="${yajl_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               yajl_lib_path="${path}/lib/"
               yajl_lib_name="${z}"
               yajl_lib_file="${yajl_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               yajl_lib_path="${path}/lib/x86_64-linux-gnu/"
               yajl_lib_name="${z}"
               yajl_lib_file="${yajl_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$yajl_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/yajl_parse.h"; then
        yajl_inc_path="${path}/include"
    elif test -e "${path}/yajl_parse.h"; then
        yajl_inc_path="${path}"
    elif test -e "${path}/include/yajl/yajl_parse.h"; then
        yajl_inc_path="${path}/include"
    fi

    if test -n "${yajl_lib_path}"; then
        AC_MSG_NOTICE([YAJL library found at: ${yajl_lib_file}])
    fi

    if test -n "${yajl_inc_path}"; then
        AC_MSG_NOTICE([YAJL headers found at: ${yajl_inc_path}])
    fi

    if test -n "${yajl_lib_path}" -a -n "${yajl_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        YAJL_CFLAGS="-I${yajl_inc_path}"
        YAJL_LDADD="-l${yajl_lib_name}"
        YAJL_LDFLAGS="-L${yajl_lib_path}"
        YAJL_DISPLAY="${yajl_lib_file}, ${yajl_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_YAJL_AT]
