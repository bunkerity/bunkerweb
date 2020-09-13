#!/bin/sh

NTASK=$(($(nproc)*2))

# install build dependencies
apk add --no-cache --virtual build autoconf libtool automake git geoip-dev yajl-dev g++ curl-dev libxml2-dev pcre-dev make linux-headers libmaxminddb-dev

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

# compile and install nginx
cd /tmp
VERSION="1.18.0"
wget https://nginx.org/download/nginx-${VERSION}.tar.gz
tar -xvzf nginx-${VERSION}.tar.gz
cd nginx-${VERSION}
./configure --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx --conf-path=/etc/nginx/nginx.conf --pid-path=/run/nginx/nginx.pid --modules-path=/usr/lib/nginx/modules --with-file-aio --with-http_ssl_module --with-http_v2_module --with-http_realip_module --add-module=/tmp/ModSecurity-nginx --add-module=/tmp/headers-more-nginx-module --add-module=/tmp/ngx_http_geoip2_module --add-module=/tmp/nginx_cookie_flag_module
make -j $NTASK
make install
strip /usr/sbin/nginx

# remove build dependencies
apk del build
