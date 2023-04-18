#!/bin/bash

function git_update_checker() {
	repo="$1"
	commit="$2"
	main_tmp_folder="/tmp/bunkerweb"
	mkdir -p "${main_tmp_folder}"
	echo "ℹ️ Check updates for ${repo}"
	folder="$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")"
	output="$(git clone "$repo" "${main_tmp_folder}/${folder}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Error cloning $1"
		echo "$output"
		rm -rf "${main_tmp_folder}/${folder}" || true
		return
	fi
	old_dir="$(pwd)"
	cd "${main_tmp_folder}/${folder}"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Commit hash $commit is absent from repository $repo"
		echo "$output"
		rm -rf "${main_tmp_folder}/${folder}" || true
		cd "$old_dir"
		return
	fi
	output="$(git fetch 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "⚠️ Upgrade version checker error on $repo"
		echo "$output"
		rm -rf "${main_tmp_folder}/${folder}" || true
		cd "$old_dir"
		return
	fi
	latest_tag=$(git describe --tags `git rev-list --tags --max-count=1`)
	if [ $? -ne 0 ] ; then
		echo "⚠️ Upgrade version checker error on getting latest tag $repo"
		echo "$latest_tag"
		rm -rf "${main_tmp_folder}/${folder}" || true
		cd "$old_dir"
		return
	fi
	latest_release=$(curl --silent "https://api.github.com/repos/$full_name_repo/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
	if [ $? -ne 0 ] ; then
		echo "⚠️ Upgrade version checker error on getting latest release $repo"
		echo "$latest_release"
		rm -fr "${main_tmp_folder}/${folder}" || true
		cd "$old_dir"
		return
	fi
	current_tag=$(git describe --tags)
	if [[ ! -z "$latest_tag" ]] && [[ "$current_tag" != *"$latest_tag"* ]]; then
		echo "⚠️ ️Update checker: new tag found: $latest_tag, current tag/release: $current_tag, please update"
	fi
	if [[ ! -z "$latest_release" ]] && [[ "$current_tag" != *"$latest_release"* ]]; then
		echo "⚠️ ️Update checker: new tag found: $latest_release, current tag/release: $current_tag, please update"
	fi
	rm -rf "${main_tmp_folder}/${folder}" || true
	cd "$old_dir"
}

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
		git_update_checker $repo $commit
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

# nginx 1.24.0
echo "ℹ️ Downloading nginx"
NGINX_VERSION="1.24.0"
secure_download "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" "nginx-${NGINX_VERSION}.tar.gz" "1114e37de5664a8109c99cfb2faa1f42ff8ac63c932bcf3780d645e5ed32c0b2ac446f80305b4465994c8f9430604968e176ae464fd80f632d1cb2c8f6007ff3"
if [ -f "deps/src/nginx-${NGINX_VERSION}.tar.gz" ] ; then
	do_and_check_cmd tar -xvzf deps/src/nginx-${NGINX_VERSION}.tar.gz -C deps/src
	do_and_check_cmd rm -f deps/src/nginx-${NGINX_VERSION}.tar.gz
fi

# Lua 5.1.5
echo "ℹ️ Downloading Lua"
LUA_VERSION="5.1.5"
secure_download "https://www.lua.org/ftp/lua-${LUA_VERSION}.tar.gz" "lua-${LUA_VERSION}.tar.gz" "0142fefcbd13afcd9b201403592aa60620011cc8e8559d4d2db2f92739d18186860989f48caa45830ff4f99bfc7483287fd3ff3a16d4dec928e2767ce4d542a9"
if [ -f "deps/src/lua-${LUA_VERSION}.tar.gz" ] ; then
	do_and_check_cmd tar -xvzf deps/src/lua-${LUA_VERSION}.tar.gz -C deps/src
	do_and_check_cmd rm -f deps/src/lua-${LUA_VERSION}.tar.gz
	do_and_check_cmd patch deps/src/lua-${LUA_VERSION}/Makefile deps/misc/lua.patch1
	do_and_check_cmd patch deps/src/lua-${LUA_VERSION}/src/Makefile deps/misc/lua.patch2
fi

# LuaJIT v2.1-20230410
echo "ℹ️ Downloading LuaJIT"
git_secure_clone "https://github.com/openresty/luajit2.git" "04f33ff01da97905a1641985fb5c840d234f97f1"

# lua-nginx-module v0.10.24
echo "ℹ️ Downloading lua-nginx-module"
git_secure_clone "https://github.com/openresty/lua-nginx-module.git" "68acad14e4a8f42e31d4a4bb5ed44d6f5b55fc1c"

# lua-resty-core v0.1.26
echo "ℹ️ Downloading lua-resty-core"
git_secure_clone "https://github.com/openresty/lua-resty-core.git" "407000a9856d3a5aab34e8c73f6ab0f049f8b8d7"

# lua-resty-lrucache v0.13
echo "ℹ️ Downloading lua-resty-lrucache"
git_secure_clone "https://github.com/openresty/lua-resty-lrucache.git" "a79615ec9dc547fdb4aaee59ef8f5a50648ce9fd"

# lua-resty-dns v0.22
echo "ℹ️ Downloading lua-resty-dns"
git_secure_clone "https://github.com/openresty/lua-resty-dns.git" "869d2fbb009b6ada93a5a10cb93acd1cc12bd53f"

# lua-resty-session v4.0.3
echo "ℹ️ Downloading lua-resty-session"
git_secure_clone "https://github.com/bungle/lua-resty-session.git" "3373d8138930b6d1e255bb80d9127503019301d7"

# lua-resty-random v?
echo "ℹ️ Downloading lua-resty-random"
git_secure_clone "https://github.com/bungle/lua-resty-random.git" "17b604f7f7dd217557ca548fc1a9a0d373386480"

# lua-resty-string v0.15
echo "ℹ️ Downloading lua-resty-string"
git_secure_clone "https://github.com/openresty/lua-resty-string.git" "b192878f6ed31b0af237935bbc5a8110a3c2256c"

# lua-cjson v2.1.0.12
echo "ℹ️ Downloading lua-cjson"
git_secure_clone "https://github.com/openresty/lua-cjson.git" "881accc8fadca5ec02aa34d364df2a1aa25cd2f9"

# lua-gd v2.0.33r3+
echo "ℹ️ Downloading lua-gd"
git_secure_clone "https://github.com/ittner/lua-gd.git" "2ce8e478a8591afd71e607506bc8c64b161bbd30"

# lua-resty-http v0.17.1
echo "ℹ️ Downloading lua-resty-http"
git_secure_clone "https://github.com/ledgetech/lua-resty-http.git" "4ab4269cf442ba52507aa2c718f606054452fcad"

# lualogging v1.8.2
echo "ℹ️ Downloading lualogging"
git_secure_clone "https://github.com/lunarmodules/lualogging.git" "465c994788f1bc18fca950934fa5ec9a909f496c"

# luasocket v3.1.0
echo "ℹ️ Downloading luasocket"
git_secure_clone "https://github.com/diegonehab/luasocket.git" "95b7efa9da506ef968c1347edf3fc56370f0deed"

# luasec v1.3.1
echo "ℹ️ Downloading luasec"
git_secure_clone "https://github.com/brunoos/luasec.git" "fddde111f7fe9ad5417d75ebbd70429d13eaad97"

# lua-resty-ipmatcher v0.6.1 (3 commits after just in case)
echo "ℹ️ Downloading lua-resty-ipmatcher"
dopatch="no"
if [ ! -d "deps/src/lua-resty-ipmatcher" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/api7/lua-resty-ipmatcher.git" "7fbb618f7221b1af1451027d3c64e51f3182761c"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/lua-resty-ipmatcher/resty/ipmatcher.lua deps/misc/ipmatcher.patch
fi

# lua-resty-redis v0.30
echo "ℹ️ Downloading lua-resty-redis"
git_secure_clone "https://github.com/openresty/lua-resty-redis.git" "d7c25f1b339d79196ff67f061c547a73a920b580"

# lua-resty-upload v0.11
echo "ℹ️ Downloading lua-resty-upload"
git_secure_clone "https://github.com/openresty/lua-resty-upload.git" "03704aee42f7135e7782688d8a9af63a16015edc"

# luajit-geoip v2.1.0
echo "ℹ️ Downloading luajit-geoip"
dopatch="no"
if [ ! -d "deps/src/luajit-geoip" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/leafo/luajit-geoip.git" "12a9388207f40c37ad5cf6de2f8e0cc72bf13477"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/luajit-geoip/geoip/mmdb.lua deps/misc/mmdb.patch
fi

# lbase64 v1.5.3
echo "ℹ️ Downloading lbase64"
git_secure_clone "https://github.com/iskolbin/lbase64.git" "c261320edbdf82c16409d893a96c28c704aa0ab8"

# lua-resty-env v0.4.0
echo "ℹ️ Downloading lua-resty-env"
git_secure_clone "https://github.com/3scale/lua-resty-env.git" "adb294def823dd910ffa11972d2c61eab7cfce3e"

# lua-resty-mlcache v2.6.0
echo "ℹ️ Downloading lua-resty-mlcache"
git_secure_clone "https://github.com/thibaultcha/lua-resty-mlcache.git" "f140f56663cbdb9cdd247d29f75c299c702ff6b4"

# lua-resty-template v2.0
echo "ℹ️ Downloading lua-resty-template"
git_secure_clone "https://github.com/bungle/lua-resty-template.git" "c08c6bc9e27710806990f2dec0f03b19406976ac"

# lua-resty-lock v0.09
echo "ℹ️ Downloading lua-resty-lock"
git_secure_clone "https://github.com/openresty/lua-resty-lock.git" "9dc550e56b6f3b1a2f1a31bb270a91813b5b6861"

# lua-pack v2.0.0
echo "ℹ️ Downloading lua-pack"
dopatch="no"
if [ ! -d "deps/src/lua-pack" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/Kong/lua-pack.git" "495bf30606b9744140258df349862981e3ee7820"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd cp deps/misc/lua-pack.Makefile deps/src/lua-pack/Makefile
fi

# lua-resty-openssl v0.8.21
echo "ℹ️ Downloading lua-resty-openssl"
git_secure_clone "https://github.com/fffonion/lua-resty-openssl.git" "15bc59b97feb5acf25fbdd9426cf73870cf7c838"

# ModSecurity v3.0.9
echo "ℹ️ Downloading ModSecurity"
dopatch="no"
if [ ! -d "deps/src/ModSecurity" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/SpiderLabs/ModSecurity.git" "205dac0e8c675182f96b5c2fb06be7d1cf7af2b2"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/ModSecurity/configure.ac deps/misc/modsecurity.patch
fi

# libinjection v3.10.0+
# TODO: check if the latest commit is fine
echo "ℹ️ Downloading libinjection"
git_secure_clone "https://github.com/libinjection/libinjection.git" "49904c42a6e68dc8f16c022c693e897e4010a06c"
do_and_check_cmd cp -r deps/src/libinjection deps/src/ModSecurity/others

# ModSecurity-nginx v1.0.3
echo "ℹ️ Downloading ModSecurity-nginx"
dopatch="no"
if [ ! -d "deps/src/ModSecurity-nginx" ] ; then
	dopatch="yes"
fi
git_secure_clone "https://github.com/SpiderLabs/ModSecurity-nginx.git" "d59e4ad121df702751940fd66bcc0b3ecb51a079"
if [ "$dopatch" = "yes" ] ; then
	do_and_check_cmd patch deps/src/ModSecurity-nginx/src/ngx_http_modsecurity_log.c deps/misc/modsecurity-nginx.patch
fi

# libmaxminddb v1.7.1
echo "ℹ️ Downloading libmaxminddb"
git_secure_clone "https://github.com/maxmind/libmaxminddb.git" "ac4d0d2480032a8664e251588e57d7b306ca630c"

# headers-more-nginx-module v0.34
echo "ℹ️ Downloading headers-more-nginx-module"
git_secure_clone "https://github.com/openresty/headers-more-nginx-module.git" "bea1be3bbf6af28f6aa8cf0c01c07ee1637e2bd0"

# nginx_cookie_flag_module v1.1.0
echo "ℹ️ Downloading nginx_cookie_flag_module"
git_secure_clone "https://github.com/AirisX/nginx_cookie_flag_module.git" "4e48acf132952bbed43b28a8e6af0584dacb7b4c"

# ngx_brotli v1.0.0
echo "ℹ️ Downloading ngx_brotli"
git_secure_clone "https://github.com/google/ngx_brotli.git" "6e975bcb015f62e1f303054897783355e2a877dc"

# ngx_devel_kit v0.3.2
echo "ℹ️ Downloading ngx_devel_kit"
git_secure_clone "https://github.com/vision5/ngx_devel_kit.git" "b4642d6ca01011bd8cd30b253f5c3872b384fd21"

# stream-lua-nginx-module v0.0.13
echo "ℹ️ Downloading stream-lua-nginx-module"
git_secure_clone "https://github.com/openresty/stream-lua-nginx-module.git" "309198abf26266f1a3e53c71388ed7bb9d1e5ea2"