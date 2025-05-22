#!/bin/sh

cd objs/lib

echo Downloading PCRE2
wget -q -O - https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.39/pcre2-10.39.tar.gz | tar -xzf -

echo Downloading zlib
wget -q -O - https://www.zlib.net/fossils/zlib-1.3.tar.gz | tar -xzf -

echo Downloading OpenSSL
wget -q -O - https://www.openssl.org/source/openssl-3.0.13.tar.gz | tar -xzf -

cd ../..

# remove /usr/bin/link conflicting with MSVC link.exe
rm /usr/bin/link

# nginx build on windows requires a native perl build
export PATH=/c/Strawberry/perl/bin:$PATH
# avoid perl 'Setting locale failed.' warnings
export LC_ALL=C

export MODSECURITY_INC=objs/lib/ModSecurity/headers
export MODSECURITY_LIB=objs/lib/ModSecurity/build/win32/build/Release

auto/configure \
    --with-cc=cl \
    --with-debug \
    --prefix= \
    --conf-path=conf/nginx.conf \
    --pid-path=logs/nginx.pid \
    --http-log-path=logs/access.log \
    --error-log-path=logs/error.log \
    --sbin-path=nginx.exe \
    --http-client-body-temp-path=temp/client_body_temp \
    --http-proxy-temp-path=temp/proxy_temp \
    --http-fastcgi-temp-path=temp/fastcgi_temp \
    --http-scgi-temp-path=temp/scgi_temp \
    --http-uwsgi-temp-path=temp/uwsgi_temp \
    --with-cc-opt=-DFD_SETSIZE=1024 \
    --with-pcre=objs/lib/pcre2-10.39 \
    --with-zlib=objs/lib/zlib-1.3 \
    --with-openssl=objs/lib/openssl-3.0.13 \
    --with-openssl-opt=no-asm \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_auth_request_module \
    --add-module=objs/lib/ModSecurity-nginx

nmake
