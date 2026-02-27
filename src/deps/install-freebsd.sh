#!/usr/local/bin/bash

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR" || return 1
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
}

if [ -n "${NTASK:-}" ]; then
	:
elif command -v nproc >/dev/null 2>&1; then
	NTASK="$(nproc)"
elif command -v sysctl >/dev/null 2>&1; then
	NTASK="$(sysctl -n hw.ncpu 2>/dev/null || echo 1)"
else
	NTASK=1
fi

case "$NTASK" in
	''|*[!0-9]*|0) NTASK=1 ;;
esac

# Detect a working C/C++ toolchain (base-system Clang or fallback).
if command -v gcc >/dev/null 2>&1; then
	BUILD_CC="$(command -v gcc)"
	BUILD_CXX="$(command -v g++ 2>/dev/null || true)"
elif command -v cc >/dev/null 2>&1; then
	BUILD_CC="$(command -v cc)"
	BUILD_CXX="$(command -v c++ 2>/dev/null || true)"
fi

if [ -z "$BUILD_CC" ]; then
	echo "❌ Error: no C compiler found"
	exit 1
fi

if [ -z "$BUILD_CXX" ]; then
	BUILD_CXX="$BUILD_CC"
fi

export CC="${CC:-$BUILD_CC}"
export CXX="${CXX:-$BUILD_CXX}"

# Some upstream Makefiles hardcode `gcc`/`g++` instead of honoring CC/CXX.
# Provide temporary wrappers so builds use the detected toolchain.
COMPAT_BIN_DIR="/tmp/bunkerweb/toolchain/bin"
mkdir -p "$COMPAT_BIN_DIR"

if ! command -v gcc >/dev/null 2>&1; then
	ln -sf "$CC" "$COMPAT_BIN_DIR/gcc"
fi

if ! command -v g++ >/dev/null 2>&1; then
	ln -sf "$CXX" "$COMPAT_BIN_DIR/g++"
fi

export PATH="$COMPAT_BIN_DIR:$PATH"

# Compiling and installing lua
echo "ℹ️ Compiling and installing lua-5.1.5"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-5.1.5"
# Use the 'bsd' platform target instead of 'freebsd': both set the same
# MYCFLAGS="-DLUA_USE_POSIX -DLUA_USE_DLOPEN" but 'freebsd' hard-codes
# MYLIBS="-Wl,-E -lreadline" which requires readline to be installed.
# 'bsd' omits readline (MYLIBS="-Wl,-E"), which is correct for a
# non-interactive WAF environment.
do_and_check_cmd gmake "CC=$CC" "CFLAGS=-O2 -Wall -fPIC -DLUA_USE_DLOPEN" "LFLAGS=-Wl,-rpath,/usr/share/bunkerweb/deps/lib" -j "$NTASK" bsd
do_and_check_cmd gmake INSTALL_TOP=/usr/share/bunkerweb/deps install

# Compiling and installing libmaxminddb
echo "ℹ️ Compiling and installing libmaxminddb"
# TODO : temp fix run it twice...
chmod +x /tmp/bunkerweb/deps/src/libmaxminddb/bootstrap
cd /tmp/bunkerweb/deps/src/libmaxminddb && ./bootstrap > /dev/null 2>&1
export CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb"
do_and_check_cmd ./bootstrap
do_and_check_cmd ./configure --prefix=/usr/share/bunkerweb/deps --disable-tests
do_and_check_cmd gmake -j "$NTASK"
# FreeBSD: Skip man page installation (no pandoc available)
# Install binaries, libraries, and headers
echo "ℹ️ Installing libmaxminddb components (skipping man pages)"
do_and_check_cmd gmake install-exec
do_and_check_cmd gmake install-includeHEADERS
# Install pkgconfig file manually
do_and_check_cmd mkdir -p /usr/share/bunkerweb/deps/lib/pkgconfig
do_and_check_cmd cp src/libmaxminddb.pc /usr/share/bunkerweb/deps/lib/pkgconfig/

# Compiling and installing zlib
echo "ℹ️ Compiling and installing zlib"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/zlib"
do_and_check_cmd chmod +x "configure"
do_and_check_cmd ./configure --prefix=/usr/share/bunkerweb/deps --libdir=/usr/share/bunkerweb/deps/lib/lua
do_and_check_cmd gmake -j "$NTASK"
do_and_check_cmd gmake install

# Compiling and installing ModSecurity
echo "ℹ️ Compiling and installing ModSecurity"
# temp fix : Debian run it twice
# TODO : patch it in clone.sh
do_and_check_cmd mv /tmp/bunkerweb/deps/src/libinjection /tmp/bunkerweb/deps/src/modsecurity/others/libinjection
do_and_check_cmd mv /tmp/bunkerweb/deps/src/mbedtls /tmp/bunkerweb/deps/src/modsecurity/others/mbedtls
export CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity"
export CXXFLAGS="${CXXFLAGS} -include cstdint"
# ModSecurity is C++ and its shared library embeds a dependency on the C++
# runtime it was compiled against. Using Clang (FreeBSD base system) links
# against /usr/lib/libc++ which is always present — no additional package is
# needed at runtime, keeping the installed footprint minimal and secure.
if command -v clang++ >/dev/null 2>&1; then
	MODSEC_CC="clang"
	MODSEC_CXX="clang++"
	echo "ℹ️ Compiling ModSecurity with Clang (base-system libc++)"
else
	MODSEC_CC="cc"
	MODSEC_CXX="c++"
	echo "ℹ️ Compiling ModSecurity with base-system cc/c++"
fi
export CC="$MODSEC_CC"
export CXX="$MODSEC_CXX"
do_and_check_cmd chmod +x "build.sh"
do_and_check_cmd ./build.sh
do_and_check_cmd sh build.sh
ARGS="--disable-dependency-tracking --disable-static --disable-examples --disable-doxygen-doc --disable-doxygen-html --disable-valgrind-memcheck --disable-valgrind-helgrind --prefix=/usr/share/bunkerweb/deps --with-maxmind=/usr/share/bunkerweb/deps --with-pcre2"
# shellcheck disable=SC2086
do_and_check_cmd ./configure $ARGS
do_and_check_cmd gmake -j "$NTASK"
do_and_check_cmd gmake install-strip

# Restore build compiler for subsequent components.
export CC="$BUILD_CC"
export CXX="$BUILD_CXX"

# Compiling and installing luajit
echo "ℹ️ Compiling and installing luajit"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit"
do_and_check_cmd gmake "CC=$CC" "HOST_CC=$CC" -j "$NTASK"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-core
echo "ℹ️ Installing openresty/lua-resty-core"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-core"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-lrucache
echo "ℹ️ Installing lua-resty-lrucache"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-lrucache"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-dns
echo "ℹ️ Installing lua-resty-dns"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-dns"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-session
echo "ℹ️ Installing lua-resty-session"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-session"
do_and_check_cmd /usr/local/bin/bash -c "cp -rf lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty/"

# Installing lua-resty-random
echo "ℹ️ Installing lua-resty-random"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-random"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-string
echo "ℹ️ Installing lua-resty-string"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-string"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Compiling and installing lua-cjson
echo "ℹ️ Compiling and installing lua-cjson"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson"
do_and_check_cmd gmake LUA_INCLUDE_DIR=/usr/share/bunkerweb/deps/include -j "$NTASK"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_CMODULE_DIR=/usr/share/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/usr/share/bunkerweb/deps/lib/lua install
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_CMODULE_DIR=/usr/share/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/usr/share/bunkerweb/deps/lib/lua install-extra

# Compiling and installing lua-gd
echo "ℹ️ Compiling and installing lua-gd"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-gd"
do_and_check_cmd gmake "CFLAGS=-O3 -Wall -fPIC -fomit-frame-pointer -I/usr/share/bunkerweb/deps/include -I/usr/local/include -DVERSION=\\\"2.0.33r3\\\"" "LFLAGS=-shared -L/usr/share/bunkerweb/deps/lib -L/usr/local/lib -llua -lgd -Wl,-rpath=/usr/share/bunkerweb/deps/lib -Wl,-rpath=/usr/local/lib" LUABIN=/usr/share/bunkerweb/deps/bin/lua -j "$NTASK"
do_and_check_cmd gmake INSTALL_PATH=/usr/share/bunkerweb/deps/lib/lua install

# Download and install lua-resty-http
echo "ℹ️ Installing lua-resty-http"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-http"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps install

# Download and install lualogging
echo "ℹ️ Installing lualogging"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lualogging"
do_and_check_cmd /usr/local/bin/bash -c "cp -rf src/* /usr/share/bunkerweb/deps/lib/lua/"

# Compiling and installing luasocket
echo "ℹ️ Compiling and installing luasocket"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/luasocket"
do_and_check_cmd gmake LUAINC_freebsd=/usr/share/bunkerweb/deps/include -j "$NTASK" freebsd
do_and_check_cmd gmake prefix=/usr/share/bunkerweb/deps CDIR_freebsd=lib/lua LDIR_freebsd=lib/lua install

# Compiling and installing luasec
echo "ℹ️ Compiling and installing luasec"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/luasec"
do_and_check_cmd gmake INC_PATH=-I/usr/share/bunkerweb/deps/include LIB_PATH=-L/usr/share/bunkerweb/deps/lib bsd -j "$NTASK"
do_and_check_cmd gmake LUACPATH=/usr/share/bunkerweb/deps/lib/lua LUAPATH=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-ipmatcher
echo "ℹ️ Installing lua-resty-ipmatcher"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-ipmatcher"
do_and_check_cmd gmake INST_PREFIX=/usr/share/bunkerweb/deps INST_LIBDIR=/usr/share/bunkerweb/deps/lib/lua INST_LUADIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-redis
echo "ℹ️ Installing lua-resty-redis"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-redis"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-upload
echo "ℹ️ Installing lua-resty-upload"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-upload"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lujit-geoip
echo "ℹ️ Installing luajit-geoip"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit-geoip"
do_and_check_cmd /usr/local/bin/bash -c "cp -rf geoip /usr/share/bunkerweb/deps/lib/lua/"

# Installing lbase64
echo "ℹ️ Installing lbase64"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lbase64"
do_and_check_cmd /usr/local/bin/bash -c "cp -f base64.lua /usr/share/bunkerweb/deps/lib/lua/"

# Installing lua-resty-env
echo "ℹ️ Installing lua-resty-env"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-env"
do_and_check_cmd /usr/local/bin/bash -c "cp -f src/resty/env.lua /usr/share/bunkerweb/deps/lib/lua/resty/"

# Installing lua-resty-mlcache
echo "ℹ️ Installing lua-resty-mlcache"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-mlcache"
do_and_check_cmd /usr/local/bin/bash -c "cp -rf lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty/"

# Installing lua-resty-template
echo "ℹ️ Installing lua-resty-template"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-template"
do_and_check_cmd /usr/local/bin/bash -c "cp -rf lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty/"

# Installing lua-resty-lock
echo "ℹ️ Installing lua-resty-lock"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-lock"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-openssl
echo "ℹ️ Installing lua-resty-openssl"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-openssl"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-ffi-zlib
echo "ℹ️ Installing lua-ffi-zlib"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-ffi-zlib"
do_and_check_cmd /usr/local/bin/bash -c "cp -f lib/ffi-zlib.lua /usr/share/bunkerweb/deps/lib/lua/"

# Installing lua-resty-signal
echo "ℹ️ Installing lua-resty-signal"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-signal"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps -j "$NTASK"
do_and_check_cmd gmake PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-redis-connector
echo "ℹ️ Installing lua-resty-redis-connector"
export CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-redis-connector"
do_and_check_cmd gmake SHELL=/usr/local/bin/bash PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Patch modsec module
export CHANGE_DIR="/tmp/bunkerweb/deps/misc"
do_and_check_cmd /usr/local/bin/bash -c "cp -f ngx_http_modsecurity_access.c /tmp/bunkerweb/deps/src/modsecurity-nginx/src/"

# Move brotli to ngx_brotli deps directory
if [ ! -d "/tmp/bunkerweb/deps/src/ngx_brotli/deps" ] ; then
	do_and_check_cmd mkdir /tmp/bunkerweb/deps/src/ngx_brotli/deps
fi
do_and_check_cmd mv /tmp/bunkerweb/deps/src/brotli /tmp/bunkerweb/deps/src/ngx_brotli/deps/brotli

# Compile dynamic modules
echo "ℹ️ Compiling and installing dynamic modules"
CONFARGS="$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')"
CONFARGS="${CONFARGS/-Os -fomit-frame-pointer -g/-Os}"
CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt=-Wl/--with-ld-opt='-lpcre2-8 -Wl'/")"
CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt='-Wl/--with-ld-opt='-lpcre2-8 -Wl/")"

# Set CFALGS
export CFLAGS="$CFLAGS -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=1"

# Detect FreeBSD major version to select the correct nginx source directory.
FREEBSD_MAJOR="$(uname -r | cut -d. -f1)"
if [ "$FREEBSD_MAJOR" = "14" ]; then
	NGINX_SRC_DIR="/tmp/bunkerweb/deps/src/nginx-1.28.0"
else
	NGINX_SRC_DIR="/tmp/bunkerweb/deps/src/nginx"
fi
export CHANGE_DIR="$NGINX_SRC_DIR"
do_and_check_cmd mv auto/configure ./
echo '#!/usr/local/bin/bash' > "${CHANGE_DIR}/configure-fix.sh"
echo "./configure $CONFARGS --add-dynamic-module=/tmp/bunkerweb/deps/src/headers-more-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/nginx_cookie_flag_module --add-dynamic-module=/tmp/bunkerweb/deps/src/lua-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_brotli --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_devel_kit --add-dynamic-module=/tmp/bunkerweb/deps/src/stream-lua-nginx-module" --add-dynamic-module=/tmp/bunkerweb/deps/src/modsecurity-nginx --add-dynamic-module=/tmp/bunkerweb/deps/src/lua-upstream-nginx-module >> "${CHANGE_DIR}/configure-fix.sh"

do_and_check_cmd chmod +x "configure"
do_and_check_cmd chmod +x "configure-fix.sh"
export LUAJIT_LIB="/usr/share/bunkerweb/deps/lib -Wl,-rpath,/usr/share/bunkerweb/deps/lib"
export LUAJIT_INC="/usr/share/bunkerweb/deps/include/luajit-2.1"
export MODSECURITY_LIB="/usr/share/bunkerweb/deps/lib"
export MODSECURITY_INC="/usr/share/bunkerweb/deps/include"
do_and_check_cmd ./configure-fix.sh
do_and_check_cmd gmake -j "$NTASK" modules
do_and_check_cmd mkdir /usr/share/bunkerweb/modules
do_and_check_cmd /usr/local/bin/bash -c "mv ./objs/*.so /usr/share/bunkerweb/modules/"

# Dependencies are installed
echo "ℹ️ Dependencies for BunkerWeb successfully compiled and installed !"
