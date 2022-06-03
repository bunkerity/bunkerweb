dnl Check for LMDB Libraries
dnl CHECK_LMDB(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])

AC_DEFUN([PROG_LMDB], [

# Needed if pkg-config will be used.LMDB
AC_REQUIRE([PKG_PROG_PKG_CONFIG])


# Possible names for the lmdb library/package (pkg-config)
LMDB_POSSIBLE_LIB_NAMES="lmdb"

# Possible extensions for the library
LMDB_POSSIBLE_EXTENSIONS="so so0 la sl dll dylib so.0.0.0"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
LMDB_POSSIBLE_PATHS="/usr/lib /usr/local/lib /usr/local/liblmdb /usr/local/lmdb /usr/local /opt/liblmdb /opt/lmdb /opt /usr /usr/lib64 /opt/local"

# Variables to be set by this very own script.
LMDB_VERSION=""
LMDB_CFLAGS=""
LMDB_CPPFLAGS=""
LMDB_LDADD=""
LMDB_LDFLAGS=""

AC_ARG_WITH(
    lmdb,
    AC_HELP_STRING(
      [--with-lmdb=PATH],
      [Path to lmdb prefix or config script]
    )
)

if test "x${with_lmdb}" == "xno"; then
    AC_DEFINE(HAVE_LMDB, 0, [Support for LMDB was disabled by the utilization of --without-lmdb or --with-lmdb=no])
    AC_MSG_NOTICE([Support for LMDB was disabled by the utilization of --without-lmdb or --with-lmdb=no])
    LMDB_DISABLED=yes
else
    if test "x${with_lmdb}" == "xyes"; then
        LMDB_MANDATORY=yes
        AC_MSG_NOTICE([LMDB support was marked as mandatory by the utilization of --with-lmdb=yes])
    fi
#        for x in ${LMDB_POSSIBLE_LIB_NAMES}; do
#            CHECK_FOR_LMDB_AT(${x})
#            if test -n "${LMDB_VERSION}"; then
#                break
#            fi
#        done

#    if test "x${with_lmdb}" != "xyes" or test "x${with_lmdb}" == "xyes"; then
        if test "x${with_lmdb}" == "x" || test "x${with_lmdb}" == "xyes"; then
            # Nothing about LMDB was informed, using the pkg-config to figure things out.
            if test -n "${PKG_CONFIG}"; then
                LMDB_PKG_NAME=""
                for x in ${LMDB_POSSIBLE_LIB_NAMES}; do
                    if ${PKG_CONFIG} --exists ${x}; then
                        LMDB_PKG_NAME="$x"
                        break
                    fi
                done
            fi
            AC_MSG_NOTICE([Nothing about LMDB was informed during the configure phase. Trying to detect it on the platform...])
            if test -n "${LMDB_PKG_NAME}"; then
                # Package was found using the pkg-config scripts
                LMDB_VERSION="`${PKG_CONFIG} ${LMDB_PKG_NAME} --modversion`"
                LMDB_CFLAGS="`${PKG_CONFIG} ${LMDB_PKG_NAME} --cflags`"
                LMDB_LDADD="`${PKG_CONFIG} ${LMDB_PKG_NAME} --libs-only-l`"
                LMDB_LDFLAGS="`${PKG_CONFIG} ${LMDB_PKG_NAME} --libs-only-L --libs-only-other`"
                LMDB_DISPLAY="${LMDB_LDADD}, ${LMDB_CFLAGS}"
            else
                # If pkg-config did not find anything useful, go over file lookup.
                for x in ${LMDB_POSSIBLE_PATHS}; do
                    CHECK_FOR_LMDB_AT(${x})
                    if test -n "${LMDB_VERSION}"; then
                        break
                    fi
                done
            fi
        fi
        if test "x${with_lmdb}" != "x"; then
            # An specific path was informed, lets check.
            LMDB_MANDATORY=yes
            CHECK_FOR_LMDB_AT(${with_lmdb})
        fi
#    fi
fi

if test -z "${LMDB_LDADD}"; then
    if test -z "${LMDB_MANDATORY}"; then
        if test -z "${LMDB_DISABLED}"; then
            AC_MSG_NOTICE([LMDB library was not found])
            LMDB_FOUND=0
        else
            LMDB_FOUND=2
        fi
    else
        AC_MSG_ERROR([LMDB was explicitly referenced but it was not found])
        LMDB_FOUND=-1
    fi
else
    if test -z "${LMDB_MANDATORY}"; then
        LMDB_FOUND=2
        AC_MSG_NOTICE([LMDB is disabled by default.])
    else
        LMDB_FOUND=1
        AC_MSG_NOTICE([using LMDB v${LMDB_VERSION}])
        LMDB_CFLAGS="-DWITH_LMDB ${LMDB_CFLAGS}"
        LMDB_DISPLAY="${LMDB_LDADD}, ${LMDB_CFLAGS}"
        AC_SUBST(LMDB_VERSION)
        AC_SUBST(LMDB_LDADD)
        AC_SUBST(LMDB_LIBS)
        AC_SUBST(LMDB_LDFLAGS)
        AC_SUBST(LMDB_CFLAGS)
        AC_SUBST(LMDB_DISPLAY)
    fi
fi


AC_SUBST(LMDB_FOUND)

]) # AC_DEFUN [PROG_LMDB]


AC_DEFUN([CHECK_FOR_LMDB_AT], [
    path=$1
    echo "*** LOOKING AT PATH: " ${path}
    for y in ${LMDB_POSSIBLE_EXTENSIONS}; do
        for z in ${LMDB_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               lmdb_lib_path="${path}/"
               lmdb_lib_name="${z}"
               lmdb_lib_file="${lmdb_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               lmdb_lib_path="${path}/"
               lmdb_lib_name="${z}"
               lmdb_lib_file="${lmdb_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               lmdb_lib_path="${path}/lib/"
               lmdb_lib_name="${z}"
               lmdb_lib_file="${lmdb_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               lmdb_lib_path="${path}/lib/x86_64-linux-gnu/"
               lmdb_lib_name="${z}"
               lmdb_lib_file="${lmdb_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/i386-linux-gnu/lib${z}.${y}"; then
               lmdb_lib_path="${path}/lib/i386-linux-gnu/"
               lmdb_lib_name="${z}"
               lmdb_lib_file="${lmdb_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$lmdb_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/lmdb.h"; then
        lmdb_inc_path="${path}/include"
    elif test -e "${path}/lmdb.h"; then
        lmdb_inc_path="${path}"
    elif test -e "${path}/include/lmdb/lmdb.h"; then
        lmdb_inc_path="${path}/include"
    fi

    if test -n "${lmdb_lib_path}"; then
        AC_MSG_NOTICE([LMDB library found at: ${lmdb_lib_file}])
    fi

    if test -n "${lmdb_inc_path}"; then
        AC_MSG_NOTICE([LMDB headers found at: ${lmdb_inc_path}])
    fi

    if test -n "${lmdb_lib_path}" -a -n "${lmdb_inc_path}"; then
        # TODO: Compile a piece of code to check the version.
        LMDB_CFLAGS="-I${lmdb_inc_path}"
        LMDB_LDADD="-l${lmdb_lib_name}"
        LMDB_LDFLAGS="-L${lmdb_lib_path}"
        LMDB_DISPLAY="${lmdb_lib_file}, ${lmdb_inc_path}"
    fi
]) # AC_DEFUN [CHECK_FOR_LMDB_AT]
