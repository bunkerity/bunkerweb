#!/bin/sh

function git_secure_checkout() {
	path="$1"
	commit="$2"
	ret=$(pwd)
	cd $path
	git checkout "${commit}^{commit}"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from submodules $path !"
		exit 3
	fi
	cd $ret
}

function git_secure_clone() {
	repo="$1"
	commit="$2"
	folder=$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")
	git clone "$repo"
	cd "$folder"
	git checkout "${commit}^{commit}"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from repository $repo !"
		exit 2
	fi
	cd ..
}

NTASK=$(nproc)

# install build dependencies
apk add --no-cache --virtual build autoconf libtool automake git geoip-dev yajl-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers libmaxminddb-dev musl-dev lua-dev gd-dev gnupg brotli-dev openssl-dev outils-signify

# turn the detached message off
git config --global advice.detachedHead false

# compile and install ModSecurity library
cd /tmp
git_secure_clone https://github.com/SpiderLabs/ModSecurity.git 753145fbd1d6751a6b14fdd700921eb3cc3a1d35
cd ModSecurity
./build.sh
git submodule init
git submodule update
git_secure_checkout bindings/python 47a6925df187f96e4593afab18dc92d5f22bd4d5
git_secure_checkout others/libinjection bf234eb2f385b969c4f803b35fda53cffdd93922
git_secure_checkout test/test-cases/secrules-language-tests d03f4c1e930440df46c1faa37d820a919704d9da
./configure --enable-static=no --disable-doxygen-doc --disable-dependency-tracking
make -j $NTASK
make install-strip

# download and install CRS rules
cd /tmp
git_secure_clone https://github.com/coreruleset/coreruleset.git 7776fe23f127fd2315bad0e400bdceb2cabb97dc
cd coreruleset
cp -r rules /etc/nginx/owasp-crs
cp crs-setup.conf.example /etc/nginx/owasp-crs.conf

# get nginx modules
cd /tmp
# ModSecurity connector for nginx
git_secure_clone https://github.com/SpiderLabs/ModSecurity-nginx.git 22e53aba4e3ae8c7d59a3672d6727e49246afe96
# headers more
git_secure_clone https://github.com/openresty/headers-more-nginx-module.git d6d7ebab3c0c5b32ab421ba186783d3e5d2c6a17
# geoip
git_secure_clone https://github.com/leev/ngx_http_geoip2_module.git 1cabd8a1f68ea3998f94e9f3504431970f848fbf
# cookie
git_secure_clone https://github.com/AirisX/nginx_cookie_flag_module.git c4ff449318474fbbb4ba5f40cb67ccd54dc595d4
# brotli
git_secure_clone https://github.com/google/ngx_brotli.git 9aec15e2aa6feea2113119ba06460af70ab3ea62

# LUA requirements
git_secure_clone https://github.com/openresty/luajit2.git fe32831adcb3f5fe9259a9ce404fc54e1399bba3
cd luajit2
make -j $NTASK
make install
cd /tmp
git_secure_clone https://github.com/openresty/lua-resty-core.git b7d0a681bb41e6e3f29e8ddc438ef26fd819bb19
cd lua-resty-core
make install
cd /tmp
git_secure_clone https://github.com/openresty/lua-resty-lrucache.git b2035269ac353444ac65af3969692bcae4fc1605
cd lua-resty-lrucache
make install
cd /tmp
git_secure_clone https://github.com/openresty/lua-resty-dns.git 24c9a69808aedfaf029ae57707cdef75d83e2d19
cd lua-resty-dns
make install
cd /tmp
git_secure_clone https://github.com/bungle/lua-resty-session.git f300870ce4eee3f4903e0565c589f1faf0c1c5aa
cd lua-resty-session
cp -r lib/resty/* /usr/local/lib/lua/resty
cd /tmp
git_secure_clone https://github.com/bungle/lua-resty-random.git 17b604f7f7dd217557ca548fc1a9a0d373386480
cd lua-resty-random
make install
cd /tmp
git_secure_clone https://github.com/openresty/lua-resty-string.git 9a543f8531241745f8814e8e02475351042774ec
cd lua-resty-string
make install
cd /tmp
git_secure_clone https://github.com/openresty/lua-cjson.git 0df488874f52a881d14b5876babaa780bb6200ee
cd lua-cjson
make -j $NTASK
make install
make install-extra
cd /tmp
git_secure_clone https://github.com/ittner/lua-gd.git 2ce8e478a8591afd71e607506bc8c64b161bbd30
cd lua-gd
make -j $NTASK
make INSTALL_PATH=/usr/local/lib/lua/5.1 install
cd /tmp
git_secure_clone https://github.com/ledgetech/lua-resty-http.git 984fdc26054376384e3df238fb0f7dfde01cacf1
cd lua-resty-http
make install
cd /tmp
git_secure_clone https://github.com/Neopallium/lualogging.git cadc4e8fd652be07a65b121a3e024838db330c15
cd lualogging
cp -r src/* /usr/local/lib/lua
cd /tmp
git_secure_clone https://github.com/diegonehab/luasocket.git 5b18e475f38fcf28429b1cc4b17baee3b9793a62
cd luasocket
make -j $NTASK
make CDIR_linux=lib/lua/5.1 LDIR_linux=lib/lua install
cd /tmp
git_secure_clone https://github.com/brunoos/luasec.git c6704919bdc85f3324340bdb35c2795a02f7d625
cd luasec
make linux -j $NTASK
make LUACPATH=/usr/local/lib/lua/5.1 LUAPATH=/usr/local/lib/lua install
cd /tmp
git_secure_clone https://github.com/crowdsecurity/lua-cs-bouncer.git 71c4247d6b66234e3f3426b2ea721ad50c741579
cd lua-cs-bouncer
mkdir /usr/local/lib/lua/crowdsec
cp lib/*.lua /usr/local/lib/lua/crowdsec
cp template.conf /usr/local/lib/lua/crowdsec/crowdsec.conf
sed -i 's/^API_URL=.*/API_URL=%CROWDSEC_HOST%/' /usr/local/lib/lua/crowdsec/crowdsec.conf
sed -i 's/^API_KEY=.*/API_KEY=%CROWDSEC_KEY%/' /usr/local/lib/lua/crowdsec/crowdsec.conf
sed -i 's/require "lrucache"/require "resty.lrucache"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua
sed -i 's/require "config"/require "crowdsec.config"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua
cd /tmp
git_secure_clone https://github.com/openresty/lua-nginx-module.git 2d23bc4f0a29ed79aaaa754c11bffb1080aa44ba
export LUAJIT_LIB=/usr/local/lib
export LUAJIT_INC=/usr/local/include/luajit-2.1

if [ "${USE_LIBRESSL}" = "yes" ] ; then
	echo "Recompile nginx with libressl"
	# if dockerfile is configure to use libressl we need to rebuild nginx
	
	# prepare libressl
	cd /tmp
	LATEST_LIBRESSL_VERSION=$(curl -L https://ftp.openbsd.org/pub/OpenBSD/LibreSSL/ | egrep -o "libressl\-[0-9.]+\.tar\.gz" | tail -n 1)
	wget "https://ftp.openbsd.org/pub/OpenBSD/LibreSSL/${LATEST_LIBRESSL_VERSION}"
	wget "https://ftp.openbsd.org/pub/OpenBSD/LibreSSL/SHA256.sig"
	check=$(signify -C -p /tmp/libressl-keys/libressl.pub -x SHA256.sig ${LATEST_LIBRESSL_VERSION} 2>&1 | grep "^${LATEST_LIBRESSL_VERSION}: OK")
	if [ "$check" = "" ] ; then
		echo "[!] Wrong signature from libressl source !"
		exit 1
	fi
	tar -xvzf ${LATEST_LIBRESSL_VERSION}

	wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
	tar -xvzf nginx-${NGINX_VERSION}.tar.gz
	cd nginx-${NGINX_VERSION}
	CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')
    CONFARGS=${CONFARGS/-Os -fomit-frame-pointer/-Os}
	./configure $CONFARGS --with-openssl=/tmp/${LATEST_LIBRESSL_VERSION//.tar*}
	
	make -j $NTASK
	make install
	strip /usr/sbin/nginx
fi

# compile and install dynamic modules
cd /tmp
wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz.asc
gpg --import /tmp/nginx-keys/*.key
check=$(gpg --verify /tmp/nginx-${NGINX_VERSION}.tar.gz.asc /tmp/nginx-${NGINX_VERSION}.tar.gz 2>&1 | grep "^gpg: Good signature from ")
if [ "$check" = "" ] ; then
	echo "[!] Wrong signature from nginx source !"
	exit 1
fi
tar -xvzf nginx-${NGINX_VERSION}.tar.gz
cd nginx-$NGINX_VERSION
CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')
CONFARGS=${CONFARGS/-Os -fomit-frame-pointer/-Os}
./configure $CONFARGS --add-dynamic-module=/tmp/ModSecurity-nginx --add-dynamic-module=/tmp/headers-more-nginx-module --add-dynamic-module=/tmp/ngx_http_geoip2_module --add-dynamic-module=/tmp/nginx_cookie_flag_module --add-dynamic-module=/tmp/lua-nginx-module --add-dynamic-module=/tmp/ngx_brotli
nginx -V

make -j $NTASK modules
cp ./objs/*.so /usr/lib/nginx/modules

# remove build dependencies
apk del build
