#!/bin/sh

NTASK=$(nproc)

# install build dependencies
apk add --no-cache --virtual build autoconf libtool automake git geoip-dev yajl-dev g++ curl-dev libxml2-dev pcre-dev make linux-headers libmaxminddb-dev musl-dev lua-dev gd-dev gnupg

# compile and install ModSecurity library
cd /tmp
git clone https://github.com/SpiderLabs/ModSecurity.git
cd ModSecurity
./build.sh
git submodule init
git submodule update
./configure --enable-static=no --disable-doxygen-doc --disable-dependency-tracking
make -j $NTASK
make install-strip

# get nginx modules
cd /tmp
# ModSecurity connector for nginx
git clone https://github.com/SpiderLabs/ModSecurity-nginx.git
# headers more
git clone https://github.com/openresty/headers-more-nginx-module.git
# geoip
git clone https://github.com/leev/ngx_http_geoip2_module.git
# cookie
git clone https://github.com/AirisX/nginx_cookie_flag_module.git

# LUA requirements
git clone https://github.com/openresty/luajit2.git
cd luajit2
make -j $NTASK
make install
cd /tmp
git clone https://github.com/openresty/lua-resty-core.git
cd lua-resty-core
make install
cd /tmp
git clone https://github.com/openresty/lua-resty-lrucache.git
cd lua-resty-lrucache
make install
cd /tmp
git clone https://github.com/openresty/lua-resty-dns.git
cd lua-resty-dns
make install
cd /tmp
git clone https://github.com/bungle/lua-resty-session.git
cd lua-resty-session
cp -r lib/resty/* /usr/local/lib/lua/resty
cd /tmp
git clone https://github.com/bungle/lua-resty-random.git
cd lua-resty-random
make install
cd /tmp
git clone https://github.com/openresty/lua-resty-string.git
cd lua-resty-string
make install
cd /tmp
git clone https://github.com/openresty/lua-cjson.git
cd lua-cjson
make -j $NTASK
make install
make install-extra
cd /tmp
git clone https://github.com/ittner/lua-gd.git
cd lua-gd
make -j $NTASK
make INSTALL_PATH=/usr/local/lib/lua/5.1 install
cd /tmp
git clone https://github.com/ledgetech/lua-resty-http.git
cd lua-resty-http
make install
cd /tmp
git clone https://github.com/openresty/lua-nginx-module.git
export LUAJIT_LIB=/usr/local/lib
export LUAJIT_INC=/usr/local/include/luajit-2.1

# compile and install dynamic modules
cd /tmp
wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
wget https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz.asc
gpg --import /tmp/nginx-keys/*.key
check=$(gpg --verify https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz.asc https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz 2>&1 | grep "^gpg: Good signature from ")
if [ "$check" = "" ] ; then
	echo "[!] Wrong signature from nginx source !"
	exit 1
fi
tar -xvzf nginx-${NGINX_VERSION}.tar.gz
cd nginx-$NGINX_VERSION
CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')
CONFARGS=${CONFARGS/-Os -fomit-frame-pointer/-Os}
./configure $CONFARGS --add-dynamic-module=/tmp/ModSecurity-nginx --add-dynamic-module=/tmp/headers-more-nginx-module --add-dynamic-module=/tmp/ngx_http_geoip2_module --add-dynamic-module=/tmp/nginx_cookie_flag_module --add-dynamic-module=/tmp/lua-nginx-module
make -j $NTASK modules
cp ./objs/*.so /

# remove build dependencies
apk del build
