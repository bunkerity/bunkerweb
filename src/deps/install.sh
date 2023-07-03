#!/bin/bash

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	#echo $output
	return 0
}

NTASK=$(nproc)

# Compiling and installing lua
echo "ℹ️ Compiling and installing lua-5.1.5"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-5.1.5" do_and_check_cmd make -j $NTASK linux
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-5.1.5" do_and_check_cmd make INSTALL_TOP=/usr/share/bunkerweb/deps install

# Compiling and installing libmaxminddb
echo "ℹ️ Compiling and installing libmaxminddb"
# TODO : temp fix run it twice...
cd /tmp/bunkerweb/deps/src/libmaxminddb && ./bootstrap > /dev/null 2>&1
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd ./bootstrap
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd ./configure --prefix=/usr/share/bunkerweb/deps --disable-tests
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd make install

# Compiling and installing zlib
echo "ℹ️ Compiling and installing zlib"
CHANGE_DIR="/tmp/bunkerweb/deps/src/zlib" do_and_check_cmd ./configure --prefix=/usr/share/bunkerweb/deps --libdir=/usr/share/bunkerweb/deps/lib/lua
CHANGE_DIR="/tmp/bunkerweb/deps/src/zlib" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/zlib" do_and_check_cmd make install

# Compiling and installing ModSecurity
echo "ℹ️ Compiling and installing ModSecurity"
# temp fix : Debian run it twice
# TODO : patch it in clone.sh
do_and_check_cmd patch /tmp/bunkerweb/deps/src/modsecurity/configure.ac /tmp/bunkerweb/deps/misc/modsecurity.patch
CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity" do_and_check_cmd rm -rf others/libinjection
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/libinjection /tmp/bunkerweb/deps/src/modsecurity/others/libinjection
cd /tmp/bunkerweb/deps/src/modsecurity && ./build.sh > /dev/null 2>&1
CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity" do_and_check_cmd sh build.sh
CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity" do_and_check_cmd ./configure --disable-dependency-tracking --disable-static --disable-examples --disable-doxygen-doc --disable-doxygen-html --disable-valgrind-memcheck --disable-valgrind-helgrind --prefix=/usr/share/bunkerweb/deps --with-maxmind=/usr/share/bunkerweb/deps
CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/modsecurity" do_and_check_cmd make install-strip

# Compiling and installing luajit
echo "ℹ️ Compiling and installing luajit"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-core
echo "ℹ️ Installing openresty/lua-resty-core"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-core" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-lrucache
echo "ℹ️ Installing lua-resty-lrucache"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-lrucache" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-dns
echo "ℹ️ Installing lua-resty-dns"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-dns" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-session
echo "ℹ️ Installing lua-resty-session"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lua-resty-session/lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty

# Installing lua-resty-random
echo "ℹ️ Installing lua-resty-random"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-random" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Installing lua-resty-string
echo "ℹ️ Installing lua-resty-string"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-string" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Compiling and installing lua-cjson
echo "ℹ️ Compiling and installing lua-cjson"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make LUA_INCLUDE_DIR=/usr/share/bunkerweb/deps/include -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_CMODULE_DIR=/usr/share/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/usr/share/bunkerweb/deps/lib/lua install
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_CMODULE_DIR=/usr/share/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/usr/share/bunkerweb/deps/lib/lua install-extra

# Compiling and installing lua-gd
echo "ℹ️ Compiling and installing lua-gd"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-gd" do_and_check_cmd make "CFLAGS=-O3 -Wall -fPIC -fomit-frame-pointer -I/usr/share/bunkerweb/deps/include -DVERSION=\\\"2.0.33r3\\\"" "LFLAGS=-shared -L/usr/share/bunkerweb/deps/lib -llua -lgd -Wl,-rpath=/usr/share/bunkerweb/deps/lib" LUABIN=/usr/share/bunkerweb/deps/bin/lua -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-gd" do_and_check_cmd make INSTALL_PATH=/usr/share/bunkerweb/deps/lib/lua install

# Download and install lua-resty-http
echo "ℹ️ Installing lua-resty-http"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-http" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps install

# Download and install lualogging
echo "ℹ️ Installing lualogging"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lualogging/src/* /usr/share/bunkerweb/deps/lib/lua

# Compiling and installing luasocket
echo "ℹ️ Compiling and installing luasocket"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasocket" do_and_check_cmd make LUAINC_linux=/usr/share/bunkerweb/deps/include -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasocket" do_and_check_cmd make prefix=/usr/share/bunkerweb/deps CDIR_linux=lib/lua LDIR_linux=lib/lua install

# Compiling and installing luasec
echo "ℹ️ Compiling and installing luasec"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasec" do_and_check_cmd make INC_PATH=-I/usr/share/bunkerweb/deps/include linux -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasec" do_and_check_cmd make LUACPATH=/usr/share/bunkerweb/deps/lib/lua LUAPATH=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-ipmatcher
echo "ℹ️ Installing lua-resty-ipmatcher"
do_and_check_cmd patch /tmp/bunkerweb/deps/src/lua-resty-ipmatcher/resty/ipmatcher.lua /tmp/bunkerweb/deps/misc/ipmatcher.patch
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-ipmatcher" do_and_check_cmd make INST_PREFIX=/usr/share/bunkerweb/deps INST_LIBDIR=/usr/share/bunkerweb/deps/lib/lua INST_LUADIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-redis
echo "ℹ️ Installing lua-resty-redis"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-redis" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-upload
echo "ℹ️ Installing lua-resty-upload"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-upload" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lujit-geoip
echo "ℹ️ Installing luajit-geoip"
do_and_check_cmd patch /tmp/bunkerweb/deps/src/luajit-geoip/geoip/mmdb.lua /tmp/bunkerweb/deps/misc/mmdb.patch
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/luajit-geoip/geoip /usr/share/bunkerweb/deps/lib/lua

# Installing lbase64
echo "ℹ️ Installing lbase64"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lbase64/base64.lua /usr/share/bunkerweb/deps/lib/lua

# Installing lua-resty-env
echo "ℹ️ Installing lua-resty-env"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lua-resty-env/src/resty/env.lua /usr/share/bunkerweb/deps/lib/lua/resty

# Installing lua-resty-mlcache
echo "ℹ️ Installing lua-resty-mlcache"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lua-resty-mlcache/lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty

# Installing lua-resty-template
echo "ℹ️ Installing lua-resty-template"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lua-resty-template/lib/resty/* /usr/share/bunkerweb/deps/lib/lua/resty

# Installing lua-resty-lock
echo "ℹ️ Installing lua-resty-lock"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-lock" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

# Installing lua-resty-openssl
echo "ℹ️ Installing lua-resty-openssl"
do_and_check_cmd rm -r /tmp/bunkerweb/deps/src/lua-resty-openssl/t
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-openssl" do_and_check_cmd make LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install
do_and_check_cmd cp /tmp/bunkerweb/deps/src/lua-resty-openssl/lib/resty/openssl.lua /usr/share/bunkerweb/deps/lib/lua/resty

# Installing lua-ffi-zlib
echo "ℹ️ Installing lua-ffi-zlib"
do_and_check_cmd patch /tmp/bunkerweb/deps/src/lua-ffi-zlib/lib/ffi-zlib.lua /tmp/bunkerweb/deps/misc/lua-ffi-zlib.patch
do_and_check_cmd cp /tmp/bunkerweb/deps/src/lua-ffi-zlib/lib/ffi-zlib.lua /usr/share/bunkerweb/deps/lib/lua

# Installing lua-resty-signal
echo "ℹ️ Installing lua-resty-signal"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-signal" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-signal" do_and_check_cmd make PREFIX=/usr/share/bunkerweb/deps LUA_LIB_DIR=/usr/share/bunkerweb/deps/lib/lua install

do_and_check_cmd patch /tmp/bunkerweb/deps/src/modsecurity-nginx/src/ngx_http_modsecurity_log.c /tmp/bunkerweb/deps/misc/modsecurity-nginx.patch
do_and_check_cmd patch /tmp/bunkerweb/deps/src/modsecurity-nginx/config /tmp/bunkerweb/deps/misc/config.patch
do_and_check_cmd patch /tmp/bunkerweb/deps/src/modsecurity-nginx/src/ngx_http_modsecurity_common.h /tmp/bunkerweb/deps/misc/ngx_http_modsecurity_common.h.patch
do_and_check_cmd patch /tmp/bunkerweb/deps/src/modsecurity-nginx/src/ngx_http_modsecurity_module.c /tmp/bunkerweb/deps/misc/ngx_http_modsecurity_module.c.patch
do_and_check_cmd cp /tmp/bunkerweb/deps/misc/ngx_http_modsecurity_access.c /tmp/bunkerweb/deps/src/modsecurity-nginx/src

# Compile dynamic modules
echo "ℹ️ Compiling and installing dynamic modules"
CONFARGS="$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')"
CONFARGS="${CONFARGS/-Os -fomit-frame-pointer -g/-Os}"
CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt=-Wl/--with-ld-opt='-lpcre -Wl'/")"
CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt='-Wl/--with-ld-opt='-lpcre -Wl/")"
if [ "$OS" = "fedora" ] ; then
	CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt='.*'/--with-ld-opt=-lpcre/" | sed "s/--with-cc-opt='.*'//")"
fi

CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx" do_and_check_cmd mv auto/configure ./
echo '#!/bin/bash' > "/tmp/bunkerweb/deps/src/nginx/configure-fix.sh"
echo "./configure $CONFARGS --add-dynamic-module=/tmp/bunkerweb/deps/src/headers-more-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/nginx_cookie_flag_module --add-dynamic-module=/tmp/bunkerweb/deps/src/lua-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_brotli --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_devel_kit --add-dynamic-module=/tmp/bunkerweb/deps/src/stream-lua-nginx-module" --add-dynamic-module=/tmp/bunkerweb/deps/src/modsecurity-nginx >> "/tmp/bunkerweb/deps/src/nginx/configure-fix.sh"
do_and_check_cmd chmod +x "/tmp/bunkerweb/deps/src/nginx/configure-fix.sh"
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx" LUAJIT_LIB="/usr/share/bunkerweb/deps/lib -Wl,-rpath,/usr/share/bunkerweb/deps/lib" LUAJIT_INC="/usr/share/bunkerweb/deps/include/luajit-2.1" MODSECURITY_LIB="/usr/share/bunkerweb/deps/lib" MODSECURITY_INC="/usr/share/bunkerweb/deps/include" do_and_check_cmd ./configure-fix.sh
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx" do_and_check_cmd make -j $NTASK modules
do_and_check_cmd mkdir /usr/share/bunkerweb/modules
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx" do_and_check_cmd cp ./objs/*.so /usr/share/bunkerweb/modules

# Dependencies are installed
echo "ℹ️ Dependencies for BunkerWeb successfully compiled and installed !"
