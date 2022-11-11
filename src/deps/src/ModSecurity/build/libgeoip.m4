dnl Check for GEOIP Libraries
dnl CHECK_GEOIP(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])
dnl Sets:
dnl  GEOIP_CFLAGS
dnl  GEOIP_LDADD
dnl  GEOIP_LDFLAGS
dnl  GEOIP_LIBS
dnl  GEOIP_VERSION

AC_DEFUN([PROG_GEOIP], [


# Needed if pkg-config will be used.
AC_REQUIRE([PKG_PROG_PKG_CONFIG])


# Possible names for the geoip library/package (pkg-config)
GEOIP_POSSIBLE_LIB_NAMES="geoip2 geoip GeoIP"

# Possible extensions for the library
GEOIP_POSSIBLE_EXTENSIONS="so la sl dll dylib"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
GEOIP_POSSIBLE_PATHS="/usr/local/libgeoip /usr/local/geoip /usr/local /opt/libgeoip /opt/geoip /opt /usr /opt/local/include /opt/local /usr/lib /usr/local/lib /usr/lib64 /usr"

# Variables to be set by this very own script.
GEOIP_VERSION=""
GEOIP_CFLAGS=""
GEOIP_CPPFLAGS=""
GEOIP_LDADD=""
GEOIP_LDFLAGS=""

AC_ARG_WITH(
    geoip,
    AS_HELP_STRING(
      [--with-geoip=PATH],
      [Path to GeoIP (including headers). Use 'no' to disable GeoIP support.]
    )
)

#    AS_HELP_STRING(
#      [--without-geoip],
#      [Complete dsiables GeoIP support]
#    )


if test "x${with_geoip}" == "xno"; then
    AC_DEFINE(HAVE_GEOIP, 0, [Support for GeoIP was disabled by the utilization of --without-geoip or --with-geoip=no])
    AC_MSG_NOTICE([Support for GeoIP was disabled by the utilization of --without-geoip or --with-geoip=no])
    GEOIP_DISABLED=yes
else
    if test "x${with_geoip}" == "xyes"; then
        GEOIP_MANDATORY=yes
        AC_MSG_NOTICE([GeoIP support was marked as mandatory by the utilization of --with-geoip=yes])
    fi
#        for x in ${GEOIP_POSSIBLE_LIB_NAMES}; do
#            CHECK_FOR_GEOIP_AT(${x})
#            if test -n "${GEOIP_VERSION}"; then
#                break
#            fi
#        done

#    if test "x${with_geoip}" != "xyes" or test "x${with_geoip}" == "xyes"; then
        if test "x${with_geoip}" == "x" || test "x${with_geoip}" == "xyes"; then
            # Nothing about GeoIP was informed, using the pkg-config to figure things out.
            if test -n "${PKG_CONFIG}"; then
                GEOIP_PKG_NAME=""
                for x in ${GEOIP_POSSIBLE_LIB_NAMES}; do
                    if ${PKG_CONFIG} --exists ${x}; then
                        GEOIP_PKG_NAME="$x"
                        break
                    fi
                done
            fi
            AC_MSG_NOTICE([Nothing about GeoIP was informed during the configure phase. Trying to detect it on the platform...])
            if test -n "${GEOIP_PKG_NAME}"; then
                # Package was found using the pkg-config scripts
                GEOIP_VERSION="`${PKG_CONFIG} ${GEOIP_PKG_NAME} --modversion`"
                GEOIP_CFLAGS="`${PKG_CONFIG} ${GEOIP_PKG_NAME} --cflags`"
                GEOIP_LDADD="`${PKG_CONFIG} ${GEOIP_PKG_NAME} --libs-only-l`"
                GEOIP_LDFLAGS="`${PKG_CONFIG} ${GEOIP_PKG_NAME} --libs-only-L --libs-only-other`"
                GEOIP_DISPLAY="${GEOIP_LDADD}, ${GEOIP_CFLAGS}"
            else
                # If pkg-config did not find anything useful, go over file lookup.
                for x in ${GEOIP_POSSIBLE_PATHS}; do
                    CHECK_FOR_GEOIP_AT(${x})
                    if test -n "${GEOIP_VERSION}"; then
                        break
                    fi
                done
            fi
        fi
        if test "x${with_geoip}" != "x"; then
            # An specific path was informed, lets check.
            GEOIP_MANDATORY=yes
            CHECK_FOR_GEOIP_AT(${with_geoip})
        fi
#    fi
fi

if test -z "${GEOIP_CFLAGS}"; then
    if test -z "${GEOIP_MANDATORY}"; then
        if test -z "${GEOIP_DISABLED}"; then
            AC_MSG_NOTICE([GeoIP library was not found])
            GEOIP_FOUND=0
        else
            GEOIP_FOUND=2
        fi
    else
        AC_MSG_ERROR([GeoIP was explicit requested but it was not found])
        GEOIP_FOUND=-1
    fi
else
    GEOIP_FOUND=1
    AC_MSG_NOTICE([using GeoIP v${GEOIP_VERSION}])
    GEOIP_CFLAGS="-DWITH_GEOIP ${GEOIP_CFLAGS}"
    AC_SUBST(GEOIP_VERSION)
    AC_SUBST(GEOIP_LDADD)
    AC_SUBST(GEOIP_LIBS)
    AC_SUBST(GEOIP_LDFLAGS)
    AC_SUBST(GEOIP_CFLAGS)
    AC_SUBST(GEOIP_DISPLAY)
fi



AC_SUBST(GEOIP_FOUND)

]) # AC_DEFUN [PROG_GEOIP]


AC_DEFUN([CHECK_FOR_GEOIP_AT], [
    path=$1
    for y in ${GEOIP_POSSIBLE_EXTENSIONS}; do
        for z in ${GEOIP_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               geoip_lib_path="${path}/"
               geoip_lib_name="${z}"
               geoip_lib_file="${geoip_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               geoip_lib_path="${path}/"
               geoip_lib_name="${z}"
               geoip_lib_file="${geoip_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               geoip_lib_path="${path}/lib/"
               geoip_lib_name="${z}"
               geoip_lib_file="${geoip_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib64/lib${z}.${y}"; then
               geoip_lib_path="${path}/lib64/"
               geoip_lib_name="${z}"
               geoip_lib_file="${geoip_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               geoip_lib_path="${path}/lib/x86_64-linux-gnu/"
               geoip_lib_name="${z}"
               geoip_lib_file="${geoip_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$geoip_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/GeoIPCity.h"; then
        geoip_inc_path="${path}/include"
    elif test -e "${path}/GeoIPCity.h"; then
        geoip_inc_path="${path}"
    fi


    if test -n "${geoip_inc_path}" -a -n "${geoip_lib_path}"; then

        AC_MSG_NOTICE([GeoIP headers found at: ${geoip_inc_path}])
        AC_MSG_NOTICE([GeoIP library found at: ${geoip_lib_file}])
    fi

    if test -n "${geoip_lib_path}" -a -n "${geoip_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        GEOIP_CFLAGS="-I${geoip_inc_path}"
        GEOIP_LDADD="-l${geoip_lib_name}"
        GEOIP_LDFLAGS="-L${geoip_lib_path}"
        GEOIP_DISPLAY="${geoip_lib_file}, ${geoip_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_GEOIP_AT]
