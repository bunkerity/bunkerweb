#!/bin/bash

function git_secure_clone() {
	repo="$1"
	commit="$2"
	folder="$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")"
	if [ ! -d "deps/src/${folder}" ] ; then
		output="$(git clone "$repo" "deps/src/${folder}" 2>&1)"
		if [ $? -ne 0 ] ; then
			echo "❌ Error cloning $1"
			echo "$output"
			exit 1
		fi
		old_dir="$(pwd)"
		cd "deps/src/${folder}"
		output="$(git checkout "${commit}^{commit}" 2>&1)"
		if [ $? -ne 0 ] ; then
			echo "❌ Commit hash $commit is absent from repository $repo"
			echo "$output"
			exit 1
		fi
		cd "$old_dir"
		output="$(rm -rf "deps/src/${folder}/.git")"
		if [ $? -ne 0 ] ; then
			echo "❌ Can't delete .git from repository $repo"
			echo "$output"
			exit 1
		fi
	else
		echo "⚠️ Skipping clone of $repo because target directory is already present"
	fi
}

function secure_download() {
	link="$1"
	file="$2"
	hash="$3"
	dir="$(echo $file | sed 's/.tar.gz//g')"
	if [ ! -d "deps/src/${dir}" ] ; then
		output="$(wget -q -O "deps/src/${file}" "$link" 2>&1)"
		if [ $? -ne 0 ] ; then
			echo "❌ Error downloading $link"
			echo "$output"
			exit 1
		fi
		check="$(sha512sum "deps/src/${file}" | cut -d ' ' -f 1)"
		if [ "$check" != "$hash" ] ; then
			echo "❌️ Wrong hash from file $link (expected $hash got $check)"
			exit 1
		fi
	else
		echo "⚠️ Skipping download of $link because target directory is already present"
	fi
}

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

# nginx 1.22.0
echo "ℹ️ Download nginx"
NGINX_VERSION="1.22.0"
secure_download "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" "nginx-${NGINX_VERSION}.tar.gz" "074782dba9cd5f8f493fbb57e20bda6dc9171814d919a47ee9f825d93f12c9f9d496e25d063c983191b55ad6a236bcef252ce16ecc1d253dc8b23433557559b1"
if [ -f "deps/src/nginx-${NGINX_VERSION}.tar.gz" ] ; then
	do_and_check_cmd tar -xvzf deps/src/nginx-${NGINX_VERSION}.tar.gz -C deps/src
	do_and_check_cmd rm -f deps/src/nginx-${NGINX_VERSION}.tar.gz
fi

# Lua 5.1.5
echo "ℹ️ Download Lua"
LUA_VERSION="5.1.5"
secure_download "https://www.lua.org/ftp/lua-${LUA_VERSION}.tar.gz" "lua-${LUA_VERSION}.tar.gz" "0142fefcbd13afcd9b201403592aa60620011cc8e8559d4d2db2f92739d18186860989f48caa45830ff4f99bfc7483287fd3ff3a16d4dec928e2767ce4d542a9"
if [ -f "deps/src/lua-${LUA_VERSION}.tar.gz" ] ; then
	do_and_check_cmd tar -xvzf deps/src/lua-${LUA_VERSION}.tar.gz -C deps/src
	do_and_check_cmd rm -f deps/src/lua-${LUA_VERSION}.tar.gz
	do_and_check_cmd patch deps/src/lua-5.1.5/Makefile deps/misc/lua.patch1
	do_and_check_cmd patch deps/src/lua-5.1.5/src/Makefile deps/misc/lua.patch2
fi

# LuaJIT 2.1-20220111
echo "ℹ️ Download LuaJIT"
git_secure_clone "https://github.com/openresty/luajit2.git" "f1491357fa1dbfa3480ba67513fee19a9c65ca6f"

# lua-nginx-module v0.10.20
echo "ℹ️ Download lua-nginx-module"
git_secure_clone "https://github.com/openresty/lua-nginx-module.git" "9007d673e28938f5dfa7720438991e22b794d225"

# lua-resty-core v0.1.22
echo "ℹ️ Download lua-resty-core"
git_secure_clone "https://github.com/openresty/lua-resty-core.git" "12f26310a35e45c37157420f7e1f395a0e36e457"

# lua-resty-lrucache v0.11
echo "ℹ️ Download lua-resty-lrucache"
git_secure_clone "https://github.com/openresty/lua-resty-lrucache.git" "f20bb8ac9489ba87d90d78f929552c2eab153caa"

# lua-resty-dns v0.22
echo "ℹ️ Download lua-resty-dns"
git_secure_clone "https://github.com/openresty/lua-resty-dns.git" "869d2fbb009b6ada93a5a10cb93acd1cc12bd53f"

# lua-resty-session v3.10
echo "ℹ️ Download lua-resty-session"
git_secure_clone "https://github.com/bungle/lua-resty-session.git" "e6bf2630c90df7b3db35e859f0aa7e096af3e918"

# lua-resty-random v?
echo "ℹ️ Download lua-resty-random"
git_secure_clone "https://github.com/bungle/lua-resty-random.git" "17b604f7f7dd217557ca548fc1a9a0d373386480"

# lua-resty-string v0.15
echo "ℹ️ Download lua-resty-string"
git_secure_clone "https://github.com/openresty/lua-resty-string.git" "b192878f6ed31b0af237935bbc5a8110a3c2256c"

# lua-cjson v2.1.0.8
echo "ℹ️ Download lua-cjson"
git_secure_clone "https://github.com/openresty/lua-cjson.git" "0df488874f52a881d14b5876babaa780bb6200ee"

# lua-gd v?
echo "ℹ️ Download lua-gd"
git_secure_clone "https://github.com/ittner/lua-gd.git" "2ce8e478a8591afd71e607506bc8c64b161bbd30"

# lua-resty-http v1.16.1
echo "ℹ️ Download lua-resty-http"
git_secure_clone "https://github.com/ledgetech/lua-resty-http.git" "9bf951dfe162dd9710a0e1f4525738d4902e9d20"

# lualogging v1.6.0
echo "ℹ️ Download lualogging"
git_secure_clone "https://github.com/lunarmodules/lualogging.git" "0bc4415de03ff1a99c92c02a5bed14a45b078079"

# luasocket v?
echo "ℹ️ Download luasocket"
git_secure_clone "https://github.com/diegonehab/luasocket.git" "5b18e475f38fcf28429b1cc4b17baee3b9793a62"

# luasec v1.0.2
echo "ℹ️ Download luasec"
git_secure_clone "https://github.com/brunoos/luasec.git" "ef14b27a2c8e541cac071165048250e85a7216df"

# lua-resty-ipmatcher v0.6.1 (1 commit after just in case)
echo "ℹ️ Download lua-resty-ipmatcher"
dopatch="no"
if [ ! -d "deps/src/lua-resty-ipmatcher" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/api7/lua-resty-ipmatcher.git" "3948a92d2e168db14fa5ecd4bb10a7c0fe7ead70"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/lua-resty-ipmatcher/resty/ipmatcher.lua deps/misc/ipmatcher.patch
fi

# lua-resty-redis v0.29
echo "ℹ️ Download lua-resty-redis"
git_secure_clone "https://github.com/openresty/lua-resty-redis.git" "053f989c7f43d8edc79d5151e73b79249c6b5d94"

# lua-resty-upload v0.10
echo "ℹ️ Download lua-resty-upload"
git_secure_clone "https://github.com/openresty/lua-resty-upload.git" "cae01f590456561bc8d95da3d2d9f937bef57bec"

# luajit-geoip v2.1.0
echo "ℹ️ Download luajit-geoip"
dopatch="no"
if [ ! -d "deps/src/luajit-geoip" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/leafo/luajit-geoip.git" "12a9388207f40c37ad5cf6de2f8e0cc72bf13477"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/luajit-geoip/geoip/mmdb.lua deps/misc/mmdb.patch
fi

# lbase64 v1.5.3
echo "ℹ️ Download lbase64"
git_secure_clone "https://github.com/iskolbin/lbase64.git" "c261320edbdf82c16409d893a96c28c704aa0ab8"

# ModSecurity v3.0.4 (looks like v3.0.5 has a memleak on reload)
# TODO : test v3.0.6
echo "ℹ️ Download ModSecurity"
if [ ! -d "deps/src/ModSecurity" ] ; then
        dopatch="yes"
fi
git_secure_clone "https://github.com/SpiderLabs/ModSecurity.git" "753145fbd1d6751a6b14fdd700921eb3cc3a1d35"
if [ "$dopatch" = "yes" ] ; then
        do_and_check_cmd patch deps/src/ModSecurity/configure.ac deps/misc/modsecurity.patch
fi
# libinjection v?
echo "ℹ️ Download libinjection"
git_secure_clone "https://github.com/libinjection/libinjection.git" "49904c42a6e68dc8f16c022c693e897e4010a06c"
do_and_check_cmd cp -r deps/src/libinjection deps/src/ModSecurity/others

# ModSecurity-nginx v1.0.2
echo "ℹ️ Download ModSecurity-nginx"
dopatch="no"
if [ ! -d "deps/src/ModSecurity-nginx" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/SpiderLabs/ModSecurity-nginx.git" "2497e6ac654d0b117b9534aa735b757c6b11c84f"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/ModSecurity-nginx/src/ngx_http_modsecurity_log.c deps/misc/modsecurity-nginx.patch
fi

# libmaxminddb v1.6.0
echo "ℹ️ Download libmaxminddb"
git_secure_clone "https://github.com/maxmind/libmaxminddb.git" "2d0e6b7360b88f645e67ffc5a709b2327d361ac3"

# headers-more-nginx-module v?
echo "ℹ️ Download headers-more-nginx-module"
git_secure_clone "https://github.com/openresty/headers-more-nginx-module.git" "a4a0686605161a6777d7d612d5aef79b9e7c13e0"

# ngx_http_geoip2_module v3.3
#echo "ℹ️ Download ngx_http_geoip2_module"
#dosed="no"
#if [ ! -d "deps/src/ngx_http_geoip2_module" ] ; then
#	dosed="yes"
#fi
#git_secure_clone "https://github.com/leev/ngx_http_geoip2_module.git" "5a83b6f958c67ea88d2899d0b3c2a5db8e36b211"
#if [ "$dosed" = "yes" ] ; then
#	do_and_check_cmd sed -i '1s:^:ngx_feature_path=/opt/bunkerweb/deps/include\n:' deps/src/ngx_http_geoip2_module/config
#	do_and_check_cmd sed -i 's:^ngx_feature_libs=.*$:ngx_feature_libs="-Wl,-rpath,/opt/bunkerweb/deps/lib -L/opt/bunkerweb/deps/lib -lmaxminddb":' deps/src/ngx_http_geoip2_module/config
#fi

# nginx_cookie_flag_module v1.1.0
echo "ℹ️ Download nginx_cookie_flag_module"
git_secure_clone "https://github.com/AirisX/nginx_cookie_flag_module.git" "4e48acf132952bbed43b28a8e6af0584dacb7b4c"

# ngx_brotli v?
echo "ℹ️ Download ngx_brotli"
git_secure_clone "https://github.com/google/ngx_brotli.git" "9aec15e2aa6feea2113119ba06460af70ab3ea62"
