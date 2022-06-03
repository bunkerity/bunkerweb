dnl Check for LUA Libraries
dnl CHECK_LUA(ACTION-IF-FOUND [, ACTION-IF-NOT-FOUND])


AC_DEFUN([CHECK_LUA],
[dnl

# Possible names for the lua library/package (pkg-config)
LUA_POSSIBLE_LIB_NAMES="luajit luajit-5.1 lua53 lua5.3 lua-5.3 lua52 lua5.2 lua-5.2 lua51 lua5.1 lua-5.1 lua"

# Possible extensions for the library
LUA_POSSIBLE_EXTENSIONS="so so0 la sl dll dylib so.0.0.0"

# Possible paths (if pkg-config was not found, proceed with the file lookup)
LUA_POSSIBLE_PATHS="/usr/lib /usr/local/lib /usr/local/lib64 /usr/local/lua /usr/local/liblua /usr/local /opt /usr /usr/lib64 /opt/local"

# Variables to be set by this very own script.
LUA_CFLAGS=""
LUA_LDFLAGS=""
LUA_LDADD=""
LUA_DISPLAY=""

AC_ARG_WITH(
    lua,
    AC_HELP_STRING(
    [--with-lua=PATH],
    [Path to lua prefix]
    )
)


if test "x${with_lua}" == "xno"; then
    AC_DEFINE(HAVE_LUA, 0, [Support for LUA was disabled by the utilization of --without-lua or --with-lua=no])
    AC_MSG_NOTICE([Support for LUA was disabled by the utilization of --without-lua or --with-lua=no])
    LUA_DISABLED=yes
else
    if test "x${with_lua}" == "xyes"; then
        LUA_MANDATORY=yes
        AC_MSG_NOTICE([LUA support was marked as mandatory by the utilization of --with-lua=yes])
    else
        LUA_MANDATORY=no
    fi
    for x in ${LUA_POSSIBLE_PATHS}; do
        CHECK_FOR_LUA_AT(${x})
        if test -n "${LUA_CFLAGS}"; then
            break
        fi
    done
    if test -z "${LUA_CFLAGS}"; then
     #Trying to figure out the version using pkg-config...
        if test -n "${PKG_CONFIG}"; then
            LUA_PKG_NAME=""
            for x in ${LUA_POSSIBLE_LIB_NAMES}; do
                if ${PKG_CONFIG} --exists ${x}; then
                    LUA_PKG_NAME="$x"
                    LUA_PKG_VERSION="`${PKG_CONFIG} ${LUA_PKG_NAME} --modversion`"
                    break
                fi
            done
        fi
        if test -n "${LUA_PKG_NAME}"; then
           # Package was found using the pkg-config scripts
           LUA_PKG_VERSION="`${PKG_CONFIG} ${LUA_PKG_NAME} --modversion`"
           LUA_CFLAGS="`${PKG_CONFIG} ${LUA_PKG_NAME} --cflags`"
           LUA_LDADD="`${PKG_CONFIG} ${LUA_PKG_NAME} --libs-only-l`"
           LUA_LDFLAGS="`${PKG_CONFIG} ${LUA_PKG_NAME} --libs-only-L --libs-only-other`"
           LUA_DISPLAY="${LUA_LDADD}, ${LUA_CFLAGS}"
        case $LUA_PKG_VERSION in
           (5.1*) LUA_CFLAGS="-DWITH_LUA_5_1 ${LUA_CFLAGS}" ; lua_5_1=1 ;;
           (5.2*) LUA_CFLAGS="-DWITH_LUA_5_2 ${LUA_CFLAGS}" ; lua_5_2=1 ;;
           (2.0*) LUA_CFLAGS="-DWITH_LUA_5_1 ${LUA_CFLAGS}" ; lua_5_1=1 ;;
           (2.1*) LUA_CFLAGS="-DWITH_LUA_5_1 -DWITH_LUA_JIT_2_1 ${LUA_CFLAGS}" ; lua_5_1=1 ;;
        esac
           AC_MSG_NOTICE([LUA pkg-config version: ${LUA_PKG_VERSION}])
        fi
    fi
fi


if test -z "${LUA_CFLAGS}"; then
    if test -z "${LUA_MANDATORY}" || test "x${LUA_MANDATORY}" == "xno"; then
        if test -z "${LUA_DISABLED}"; then
            AC_MSG_NOTICE([LUA library was not found])
            LUA_FOUND=0
        else
            LUA_FOUND=2
        fi
    else
       AC_MSG_ERROR([LUA was explicitly referenced but it was not found])
       LUA_FOUND=-1
    fi
else
    if test -z "${LUA_MANDATORY}" || test "x${LUA_MANDATORY}" == "xno"; then
        LUA_FOUND=1
        AC_MSG_NOTICE([using LUA ${LUA_LDADD}])
        LUA_CFLAGS="-DWITH_LUA ${LUA_CFLAGS}"
        LUA_DISPLAY="${LUA_LDADD} ${LUA_LDFLAGS}, ${LUA_CFLAGS}"
        AC_SUBST(LUA_LDFLAGS)
        AC_SUBST(LUA_LDADD)
        AC_SUBST(LUA_CFLAGS)
        AC_SUBST(LUA_DISPLAY)
    else
        LUA_FOUND=1
        AC_MSG_NOTICE([using LUA ${LUA_LDADD}])
        LUA_CFLAGS="-DWITH_LUA ${LUA_CFLAGS}"
        LUA_DISPLAY="${LUA_LDADD} ${LUA_LDFLAGS}, ${LUA_CFLAGS}"
        AC_SUBST(LUA_LDFLAGS)
        AC_SUBST(LUA_LDADD)
        AC_SUBST(LUA_CFLAGS)
        AC_SUBST(LUA_DISPLAY)
    fi
fi

AC_SUBST(LUA_FOUND)

]) # AC_DEFUN [CHECK_LUA]


AC_DEFUN([CHECK_FOR_LUA_AT], [
    path=$1
    echo "*** LOOKING AT PATH: " ${path}
    for y in ${LUA_POSSIBLE_EXTENSIONS}; do
        for z in ${LUA_POSSIBLE_LIB_NAMES}; do
           if test -e "${path}/${z}.${y}"; then
               lua_lib_path="${path}/"
               lua_lib_name="${z}"
               lua_lib_file="${lua_lib_path}/${z}.${y}"
               break
           fi
           if test -e "${path}/lib${z}.${y}"; then
               lua_lib_path="${path}/"
               lua_lib_name="${z}"
               lua_lib_file="${lua_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/lib${z}.${y}"; then
               lua_lib_path="${path}/lib/"
               lua_lib_name="${z}"
               lua_lib_file="${lua_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/x86_64-linux-gnu/lib${z}.${y}"; then
               lua_lib_path="${path}/lib/x86_64-linux-gnu/"
               lua_lib_name="${z}"
               lua_lib_file="${lua_lib_path}/lib${z}.${y}"
               break
           fi
           if test -e "${path}/lib/i386-linux-gnu/lib${z}.${y}"; then
               lua_lib_path="${path}/lib/i386-linux-gnu/"
               lua_lib_name="${z}"
               lua_lib_file="${lua_lib_path}/lib${z}.${y}"
               break
           fi
       done
       if test -n "$lua_lib_path"; then
           break
       fi
    done
    if test -e "${path}/include/lua.h"; then
        lua_inc_path="${path}/include"
    elif test -e "${path}/lua.h"; then
       lua_inc_path="${path}"
    elif test -e "${path}/include/lua/lua.h"; then
        lua_inc_path="${path}/include/lua"
    elif test -e "${path}/include/lua5.3/lua.h"; then
        lua_inc_path="${path}/include/lua5.3"
	LUA_VERSION=503
    elif test -e "${path}/include/lua5.2/lua.h"; then
        lua_inc_path="${path}/include/lua5.2"
	LUA_VERSION=502
    elif test -e "${path}/include/lua5.1/lua.h"; then
        lua_inc_path="${path}/include/lua5.1"
	LUA_VERSION=501
    elif test -e "${path}/include/luajit-2.0/lua.h"; then
        lua_inc_path="${path}/include/luajit-2.0"
	LUA_VERSION=501
    fi

    if test -n "${lua_lib_path}"; then
        AC_MSG_NOTICE([LUA library found at: ${lua_lib_file}])
    fi

    if test -n "${lua_inc_path}"; then
        AC_MSG_NOTICE([LUA headers found at: ${lua_inc_path}])
    fi
    if test -n "${lua_lib_path}" -a -n "${lua_inc_path}"; then
           LUA_CFLAGS="-I${lua_inc_path}"
           LUA_LDADD="-l${lua_lib_name}"
           LUA_LDFLAGS="-L${lua_lib_path}"
           LUA_DISPLAY="${lua_lib_file}, ${lua_inc_path}"

        # Double checking version from lua.h...
        AC_TRY_COMPILE([ #include <lua.h>> ],
                         [ #if (LUA_VERSION_NUM < 502)
                           return 0;
                           #else
                           #error Lua 5.1 not detected
                           #endif ],
                             [ LUA_VERSION=501 ], [ lua_5_1=0 ]
                      )

        AC_TRY_COMPILE([ #include <lua.h> ],
                         [ #if (LUA_VERSION_NUM == 502)
                           return 0;
                           #else
                           #error Lua 5.2 not detected
                           #endif ],
                             [ LUA_VERSION=502 ], [ lua_5_2=0 ]
                      )

        if test -z "${LUA_VERSION}" ; then
        # As a last resort, try to find LUA version from $lua_inc_path
            while read -r line
            do
            case "$line" in
                (\#define\ LUA_VERSION_NUM*501*) LUA_VERSION=501 ;;
                (\#define\ LUA_VERSION_NUM*502*) LUA_VERSION=501 ;;
                (\#define\ LUA_VERSION_NUM*503*) LUA_VERSION=503
            esac
            done <"${lua_inc_path}/lua.h"
            AC_MSG_NOTICE([LUA_VERSION is ${LUA_VERSION} found at: ${lua_inc_path}])
        else
            AC_MSG_NOTICE([LUA version from includes: ${LUA_VERSION}])
        fi

        case $LUA_VERSION in
           (501) LUA_CFLAGS="-DWITH_LUA_5_1 ${LUA_CFLAGS}" ; lua_5_1=1 ;;
           (502) LUA_CFLAGS="-DWITH_LUA_5_2 ${LUA_CFLAGS}" ; lua_5_2=1 ;;
        esac
    fi

]) # AC_DEFUN [CHECK_FOR_LUA_AT]



