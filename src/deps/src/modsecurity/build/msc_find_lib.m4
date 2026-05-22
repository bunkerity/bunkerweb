dnl MSC_CHECK_LIB: Generic library detection macro
dnl
dnl MSC_CHECK_LIB(NAME, PKG_NAMES, HEADER, LIB_NAMES, EXTRA_CFLAGS,
dnl               [MIN_VERSION], [WITH_NAME])
dnl
dnl Detects a library via pkg-config first, then falls back to manual
dnl file-system scanning. Preserves the --with-LIB=PATH|yes|no interface.
dnl
dnl Sets and AC_SUBSTs:
dnl   ${NAME}_CFLAGS, ${NAME}_LDADD, ${NAME}_LDFLAGS,
dnl   ${NAME}_VERSION, ${NAME}_DISPLAY, ${NAME}_FOUND (0/1/2)
dnl
dnl NAME         - Variable prefix (e.g., YAJL, CURL, LIBXML2)
dnl PKG_NAMES    - Space-separated pkg-config names to try
dnl HEADER       - Header file to look for (e.g., yajl/yajl_parse.h)
dnl LIB_NAMES    - Space-separated library names for -l flags
dnl EXTRA_CFLAGS - Additional CFLAGS when found (e.g., -DWITH_YAJL)
dnl MIN_VERSION  - Optional minimum version for pkg-config check
dnl WITH_NAME    - Optional --with-X name if different from lowercased NAME

AC_DEFUN([MSC_CHECK_LIB], [
m4_pushdef([_MSC_NAME], [$1])dnl
m4_pushdef([_MSC_PKG_NAMES], [$2])dnl
m4_pushdef([_MSC_HEADER], [$3])dnl
m4_pushdef([_MSC_LIB_NAMES], [$4])dnl
m4_pushdef([_MSC_EXTRA_CFLAGS], [$5])dnl
m4_pushdef([_MSC_MIN_VERSION], [$6])dnl
m4_pushdef([_MSC_WITH_NAME], [m4_default([$7], m4_tolower([$1]))])dnl
m4_pushdef([_MSC_POSSIBLE_PATHS], [/usr/local /usr /opt /opt/local /usr/lib /usr/local/lib /usr/lib64])dnl
m4_pushdef([_MSC_POSSIBLE_EXTENSIONS], [so la sl dll dylib])dnl

# Initialize variables
$1_VERSION=""
$1_CFLAGS=""
$1_LDADD=""
$1_LDFLAGS=""
$1_DISPLAY=""
$1_FOUND=0
_msc_[]m4_tolower($1)[]_mandatory=""
_msc_[]m4_tolower($1)[]_disabled=""

AC_ARG_WITH(
    _MSC_WITH_NAME,
    [AS_HELP_STRING([--with-]_MSC_WITH_NAME[=PATH],
        [Path to ]_MSC_NAME[ prefix. Use 'no' to disable.])])

# Get the value of the --with flag
_msc_with_val="$with_[]m4_translit(_MSC_WITH_NAME, [-], [_])"

if test "x${_msc_with_val}" = "xno"; then
    AC_MSG_NOTICE([$1 support disabled via --without-]_MSC_WITH_NAME)
    _msc_[]m4_tolower($1)[]_disabled=yes
elif test "x${_msc_with_val}" = "xyes"; then
    _msc_[]m4_tolower($1)[]_mandatory=yes
    AC_MSG_NOTICE([$1 support marked as mandatory])
    # Try pkg-config
    _MSC_TRY_PKG_CONFIG([$1], [_MSC_PKG_NAMES], [_MSC_MIN_VERSION])
    if test -z "${$1_VERSION}"; then
        _MSC_TRY_MANUAL([$1], [_MSC_HEADER], [_MSC_LIB_NAMES])
    fi
elif test "x${_msc_with_val}" = "x"; then
    # Auto-detect
    AC_MSG_NOTICE([Auto-detecting $1...])
    _MSC_TRY_PKG_CONFIG([$1], [_MSC_PKG_NAMES], [_MSC_MIN_VERSION])
    if test -z "${$1_VERSION}"; then
        _MSC_TRY_MANUAL([$1], [_MSC_HEADER], [_MSC_LIB_NAMES])
    fi
else
    # Specific path provided
    _msc_[]m4_tolower($1)[]_mandatory=yes
    _MSC_TRY_PKG_CONFIG_AT([$1], [_MSC_PKG_NAMES], [_MSC_MIN_VERSION], [${_msc_with_val}])
    if test -z "${$1_VERSION}"; then
        _MSC_CHECK_AT([$1], [_MSC_HEADER], [_MSC_LIB_NAMES], [${_msc_with_val}])
    fi
fi

# Evaluate results
if test -n "${$1_LDADD}" || test -n "${$1_VERSION}"; then
    $1_FOUND=1
    AC_MSG_NOTICE([using $1 v${$1_VERSION}])
    $1_CFLAGS="_MSC_EXTRA_CFLAGS ${$1_CFLAGS}"
    if test -z "${$1_DISPLAY}"; then
        $1_DISPLAY="${$1_LDADD}, ${$1_CFLAGS}"
    fi
    AC_SUBST($1_VERSION)
    AC_SUBST($1_LDADD)
    AC_SUBST($1_LDFLAGS)
    AC_SUBST($1_CFLAGS)
    AC_SUBST($1_DISPLAY)
elif test -n "${_msc_[]m4_tolower($1)[]_disabled}"; then
    $1_FOUND=2
elif test -n "${_msc_[]m4_tolower($1)[]_mandatory}"; then
    AC_MSG_ERROR([$1 was explicitly requested but not found])
else
    AC_MSG_NOTICE([$1 library not found])
    $1_FOUND=0
fi

AC_SUBST($1_FOUND)

m4_popdef([_MSC_POSSIBLE_EXTENSIONS])dnl
m4_popdef([_MSC_POSSIBLE_PATHS])dnl
m4_popdef([_MSC_WITH_NAME])dnl
m4_popdef([_MSC_MIN_VERSION])dnl
m4_popdef([_MSC_EXTRA_CFLAGS])dnl
m4_popdef([_MSC_LIB_NAMES])dnl
m4_popdef([_MSC_HEADER])dnl
m4_popdef([_MSC_PKG_NAMES])dnl
m4_popdef([_MSC_NAME])dnl
]) # MSC_CHECK_LIB


dnl _MSC_TRY_PKG_CONFIG(NAME, PKG_NAMES, MIN_VERSION)
dnl Try to find the library via pkg-config
AC_DEFUN([_MSC_TRY_PKG_CONFIG], [
if test -n "${PKG_CONFIG}"; then
    _msc_pkg_name=""
    for _msc_p in $2; do
        if test -n "$3"; then
            if ${PKG_CONFIG} --exists "${_msc_p} >= $3" 2>/dev/null; then
                _msc_pkg_name="${_msc_p}"
                break
            fi
        else
            if ${PKG_CONFIG} --exists "${_msc_p}" 2>/dev/null; then
                _msc_pkg_name="${_msc_p}"
                break
            fi
        fi
    done
    if test -n "${_msc_pkg_name}"; then
        $1_VERSION="`${PKG_CONFIG} ${_msc_pkg_name} --modversion`"
        $1_CFLAGS="`${PKG_CONFIG} ${_msc_pkg_name} --cflags`"
        $1_LDADD="`${PKG_CONFIG} ${_msc_pkg_name} --libs-only-l`"
        $1_LDFLAGS="`${PKG_CONFIG} ${_msc_pkg_name} --libs-only-L --libs-only-other`"
        $1_DISPLAY="${$1_LDADD}, ${$1_CFLAGS}"
        AC_MSG_NOTICE([$1 found via pkg-config: ${_msc_pkg_name} v${$1_VERSION}])
    fi
fi
]) # _MSC_TRY_PKG_CONFIG


dnl _MSC_TRY_PKG_CONFIG_AT(NAME, PKG_NAMES, MIN_VERSION, PATH)
dnl Try pkg-config with PKG_CONFIG_PATH set to a specific location
AC_DEFUN([_MSC_TRY_PKG_CONFIG_AT], [
if test -n "${PKG_CONFIG}"; then
    _msc_save_pkg_config_path="${PKG_CONFIG_PATH}"
    PKG_CONFIG_PATH="$4/lib/pkgconfig:$4/lib64/pkgconfig:$4/share/pkgconfig:${PKG_CONFIG_PATH}"
    export PKG_CONFIG_PATH
    _MSC_TRY_PKG_CONFIG([$1], [$2], [$3])
    PKG_CONFIG_PATH="${_msc_save_pkg_config_path}"
    export PKG_CONFIG_PATH
fi
]) # _MSC_TRY_PKG_CONFIG_AT


dnl _MSC_TRY_MANUAL(NAME, HEADER, LIB_NAMES)
dnl Try to find the library by scanning common paths
AC_DEFUN([_MSC_TRY_MANUAL], [
for _msc_search_path in /usr/local /usr /opt /opt/local /usr/lib /usr/local/lib /usr/lib64; do
    _MSC_CHECK_AT([$1], [$2], [$3], [${_msc_search_path}])
    if test -n "${$1_VERSION}"; then
        break
    fi
    # Also check if LDADD was set (version may not always be detected manually)
    if test -n "${$1_LDADD}"; then
        break
    fi
done
]) # _MSC_TRY_MANUAL


dnl _MSC_CHECK_AT(NAME, HEADER, LIB_NAMES, PATH)
dnl Check for a library at a specific path
AC_DEFUN([_MSC_CHECK_AT], [
_msc_check_lib_path=""
_msc_check_lib_name=""
_msc_check_lib_file=""
_msc_check_inc_path=""

# Search for library files
for _msc_ext in so la sl dll dylib; do
    for _msc_ln in $3; do
        for _msc_try_path in \
            "$4/lib${_msc_ln}.${_msc_ext}" \
            "$4/lib/lib${_msc_ln}.${_msc_ext}" \
            "$4/lib64/lib${_msc_ln}.${_msc_ext}" \
            "$4/lib/x86_64-linux-gnu/lib${_msc_ln}.${_msc_ext}" \
            "$4/lib/i386-linux-gnu/lib${_msc_ln}.${_msc_ext}"; do
            if test -e "${_msc_try_path}"; then
                _msc_check_lib_path="`dirname ${_msc_try_path}`"
                _msc_check_lib_name="${_msc_ln}"
                _msc_check_lib_file="${_msc_try_path}"
                break 3
            fi
        done
    done
done

# Search for header file
_msc_header_base="`basename $2`"
_msc_header_dir="`dirname $2`"
if test "${_msc_header_dir}" = "."; then
    # Simple header name (e.g., "lmdb.h")
    if test -e "$4/include/$2"; then
        _msc_check_inc_path="$4/include"
    elif test -e "$4/$2"; then
        _msc_check_inc_path="$4"
    fi
else
    # Header with subdirectory (e.g., "yajl/yajl_parse.h")
    if test -e "$4/include/$2"; then
        _msc_check_inc_path="$4/include"
    elif test -e "$4/$2"; then
        _msc_check_inc_path="$4"
    fi
fi

if test -n "${_msc_check_lib_path}" && test -n "${_msc_check_inc_path}"; then
    AC_MSG_NOTICE([$1 headers found at: ${_msc_check_inc_path}])
    AC_MSG_NOTICE([$1 library found at: ${_msc_check_lib_file}])
    $1_CFLAGS="-I${_msc_check_inc_path}"
    $1_LDADD="-l${_msc_check_lib_name}"
    $1_LDFLAGS="-L${_msc_check_lib_path}"
    $1_DISPLAY="${_msc_check_lib_file}, ${_msc_check_inc_path}"
    # Version is unknown from manual detection
    if test -z "${$1_VERSION}"; then
        $1_VERSION="unknown"
    fi
fi
]) # _MSC_CHECK_AT


dnl MSC_STATUS_LIB(DISPLAY_NAME, VAR_PREFIX)
dnl Print a status line for the configure summary
AC_DEFUN([MSC_STATUS_LIB], [
if test "x${$2_FOUND}" = "x0"; then
    echo "   + $1 ....not found"
fi
if test "x${$2_FOUND}" = "x1"; then
    AS_ECHO_N(["   + $1 ....found "])
    if ! test "x${$2_VERSION}" = "x"; then
        echo "v${$2_VERSION}"
    else
        echo ""
    fi
    echo "      ${$2_DISPLAY}"
fi
if test "x${$2_FOUND}" = "x2"; then
    echo "   + $1 ....disabled"
fi
]) # MSC_STATUS_LIB


dnl MSC_ARG_ENABLE_BOOL(NAME, HELP_TEXT, DEFAULT, VARIABLE)
dnl Wrapper for boolean AC_ARG_ENABLE options
AC_DEFUN([MSC_ARG_ENABLE_BOOL], [
AC_ARG_ENABLE($1,
    [AS_HELP_STRING([--enable-$1],[$2])],
    [case "${enableval}" in
        yes) $4=true ;;
        no)  $4=false ;;
        *) AC_MSG_ERROR([bad value ${enableval} for --enable-$1]) ;;
    esac],
    [$4=$3])
]) # MSC_ARG_ENABLE_BOOL
