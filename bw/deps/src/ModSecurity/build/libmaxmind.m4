dnl Check for MAXMIND Libraries
dnl CHECK_MAXMIND(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])
dnl Sets:
dnl  MAXMIND_CFLAGS
dnl  MAXMIND_LDADD
dnl  MAXMIND_LDFLAGS
dnl  MAXMIND_LIBS
dnl  MAXMIND_VERSION

AC_DEFUN([PROG_MAXMIND], [


# Needed if pkg-config will be used.
AC_REQUIRE([PKG_PROG_PKG_CONFIG])


# Possible names for the maxmind library/package (pkg-config)
MAXMIND_POSSIBLE_LIB_NAMES="libmaxminddb maxminddb maxmind"

# Possible extensions for the library
MAXMIND_POSSIBLE_EXTENSIONS="so la sl dll dylib"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
MAXMIND_POSSIBLE_PATHS="/usr/local/libmaxmind /usr/local/maxmind /usr/local /opt/libmaxmind /opt/maxmind /opt /usr /opt/local/include /opt/local /usr/lib /usr/local/lib /usr/lib64 /usr /usr/include/x86_64-linux-gnu/"

# Variables to be set by this very own script.
MAXMIND_VERSION=""
MAXMIND_CFLAGS=""
MAXMIND_CPPFLAGS=""
MAXMIND_LDADD=""
MAXMIND_LDFLAGS=""

AC_ARG_WITH(
    maxmind,
    AS_HELP_STRING(
      [--with-maxmind=PATH],
      [Path to MaxMind (including headers). Use 'no' to disable MaxMind support.]
    )
)

#    AS_HELP_STRING(
#      [--without-maxmind],
#      [Complete dsiables MaxMind support]
#    )


if test "x${with_maxmind}" == "xno"; then
    AC_DEFINE(HAVE_MAXMIND, 0, [Support for MaxMind was disabled by the utilization of --without-maxmind or --with-maxmind=no])
    AC_MSG_NOTICE([Support for MaxMind was disabled by the utilization of --without-maxmind or --with-maxmind=no])
    MAXMIND_DISABLED=yes
else
    if test "x${with_maxmind}" == "xyes"; then
        MAXMIND_MANDATORY=yes
        AC_MSG_NOTICE([MaxMind support was marked as mandatory by the utilization of --with-maxmind=yes])
    fi
#        for x in ${MAXMIND_POSSIBLE_LIB_NAMES}; do
#            CHECK_FOR_MAXMIND_AT(${x})
#            if test -n "${MAXMIND_VERSION}"; then
#                break
#            fi
#        done

#    if test "x${with_maxmind}" != "xyes" or test "x${with_maxmind}" == "xyes"; then
        if test "x${with_maxmind}" == "x" || test "x${with_maxmind}" == "xyes"; then
            # Nothing about MaxMind was informed, using the pkg-config to figure things out.
            if test -n "${PKG_CONFIG}"; then
                MAXMIND_PKG_NAME=""
                for x in ${MAXMIND_POSSIBLE_LIB_NAMES}; do
                    if ${PKG_CONFIG} --exists ${x}; then
                        MAXMIND_PKG_NAME="$x"
                        break
                    fi
                done
            fi
            AC_MSG_NOTICE([Nothing about MaxMind was informed during the configure phase. Trying to detect it on the platform...])
            if test -n "${MAXMIND_PKG_NAME}"; then
                # Package was found using the pkg-config scripts
                MAXMIND_VERSION="`${PKG_CONFIG} ${MAXMIND_PKG_NAME} --modversion`"
                MAXMIND_CFLAGS="`${PKG_CONFIG} ${MAXMIND_PKG_NAME} --cflags`"
                MAXMIND_LDADD="`${PKG_CONFIG} ${MAXMIND_PKG_NAME} --libs-only-l`"
                MAXMIND_LDFLAGS="`${PKG_CONFIG} ${MAXMIND_PKG_NAME} --libs-only-L --libs-only-other`"
                MAXMIND_DISPLAY="${MAXMIND_LDADD}"
            else
                # If pkg-config did not find anything useful, go over file lookup.
                for x in ${MAXMIND_POSSIBLE_PATHS}; do
                    CHECK_FOR_MAXMIND_AT(${x})
                    if test -n "${MAXMIND_VERSION}"; then
                        break
                    fi
                done
            fi
        fi
        if test "x${with_maxmind}" != "x"; then
            # An specific path was informed, lets check.
            MAXMIND_MANDATORY=yes
            CHECK_FOR_MAXMIND_AT(${with_maxmind})
        fi
#    fi
fi

if test -z "${MAXMIND_DISPLAY}"; then
    if test -z "${MAXMIND_MANDATORY}"; then
        if test -z "${MAXMIND_DISABLED}"; then
            AC_MSG_NOTICE([MaxMind library was not found])
            MAXMIND_FOUND=0
        else
            MAXMIND_FOUND=2
        fi
    else
        AC_MSG_ERROR([MaxMind was explicit requested but it was not found])
        MAXMIND_FOUND=-1
    fi
else
    MAXMIND_FOUND=1
    AC_MSG_NOTICE([using MaxMind v${MAXMIND_VERSION}])
    MAXMIND_CFLAGS="-DWITH_MAXMIND ${MAXMIND_CFLAGS}"
    if ! test "x$MAXMIND_CFLAGS" = "x"; then
        MAXMIND_DISPLAY="${MAXMIND_DISPLAY}, ${MAXMIND_CFLAGS}"
    fi
    AC_SUBST(MAXMIND_VERSION)
    AC_SUBST(MAXMIND_LDADD)
    AC_SUBST(MAXMIND_LIBS)
    AC_SUBST(MAXMIND_LDFLAGS)
    AC_SUBST(MAXMIND_CFLAGS)
    AC_SUBST(MAXMIND_DISPLAY)
fi



AC_SUBST(MAXMIND_FOUND)

]) # AC_DEFUN [PROG_MAXMIND]


AC_DEFUN([CHECK_FOR_MAXMIND_AT], [
    path=$1
    for y in ${MAXMIND_POSSIBLE_EXTENSIONS}; do
        for z in ${MAXMIND_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               maxmind_lib_path="${path}/"
               maxmind_lib_name="${z}"
               maxmind_lib_file="${maxmind_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               maxmind_lib_path="${path}/"
               maxmind_lib_name="${z}"
               maxmind_lib_file="${maxmind_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               maxmind_lib_path="${path}/lib/"
               maxmind_lib_name="${z}"
               maxmind_lib_file="${maxmind_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib64/lib${z}.${y}"; then
               maxmind_lib_path="${path}/lib64/"
               maxmind_lib_name="${z}"
               maxmind_lib_file="${maxmind_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               maxmind_lib_path="${path}/lib/x86_64-linux-gnu/"
               maxmind_lib_name="${z}"
               maxmind_lib_file="${maxmind_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$maxmind_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/maxminddb.h"; then
        maxmind_inc_path="${path}/include"
    elif test -e "${path}/maxminddb.h"; then
        maxmind_inc_path="${path}"
    fi


    if test -n "${maxmind_inc_path}" -a -n "${maxmind_lib_path}"; then

        AC_MSG_NOTICE([MaxMind headers found at: ${maxmind_inc_path}])
        AC_MSG_NOTICE([MaxMind library found at: ${maxmind_lib_file}])
    fi

    if test -n "${maxmind_lib_path}" -a -n "${maxmind_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        MAXMIND_CFLAGS="-I${maxmind_inc_path}"
        MAXMIND_LDADD="-l${maxmind_lib_name}"
        MAXMIND_LDFLAGS="-L${maxmind_lib_path}"
        MAXMIND_DISPLAY="${maxmind_lib_file}, ${maxmind_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_MAXMIND_AT]
