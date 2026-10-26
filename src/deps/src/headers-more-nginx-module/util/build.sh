#!/bin/bash

# this file is mostly meant to be used by the author himself.

root=`pwd`
version=$1
home=~
force=$2

ld_opts="${OPENSSL_LIB:+-L$OPENSSL_LIB }${PCRE_LIB:+-L$PCRE_LIB }"
rpath="${OPENSSL_LIB:+$OPENSSL_LIB:}${PCRE_LIB:+$PCRE_LIB:}"
rpath="${rpath}${LIBDRIZZLE_LIB:+$LIBDRIZZLE_LIB:}/usr/local/lib"
cc_opts="-DDEBUG_MALLOC${OPENSSL_INC:+ -I$OPENSSL_INC}"
cc_opts="${cc_opts}${PCRE_INC:+ -I$PCRE_INC}"

        #--with-cc=gcc46 \

ngx-build $force $version \
      --with-ld-opt="${ld_opts}-Wl,-rpath,$rpath" \
      --with-cc-opt="$cc_opts" \
      --with-http_ssl_module \
      --without-mail_pop3_module \
      --without-mail_imap_module \
      --without-mail_smtp_module \
      --without-http_upstream_ip_hash_module \
      --without-http_empty_gif_module \
      --without-http_memcached_module \
      --without-http_referer_module \
      --without-http_autoindex_module \
      --without-http_auth_basic_module \
      --without-http_userid_module \
      --with-http_realip_module \
      --with-http_dav_module \
      --add-module=$root/../eval-nginx-module \
      --add-module=$root/../lua-nginx-module \
      --add-module=$root/../echo-nginx-module \
      --add-module=$root $opts \
      --with-debug
      #--add-module=$root/../ndk-nginx-module \
  #--without-http_ssi_module  # we cannot disable ssi because echo_location_async depends on it (i dunno why?!)

