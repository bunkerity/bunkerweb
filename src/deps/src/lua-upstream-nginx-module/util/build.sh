#!/bin/bash

# this file is mostly meant to be used by the author himself.

#set -x

root=`pwd`
version=$1
home=~
force=$2

cd $root || exit 1

            #--without-http_memcached_module \
ngx-build $force $version \
            --with-cc-opt="-O0" \
            --with-ld-opt="-Wl,-rpath,/opt/postgres/lib:/opt/drizzle/lib:/usr/local/lib" \
            --without-mail_pop3_module \
            --without-mail_imap_module \
            --without-mail_smtp_module \
            --without-http_upstream_ip_hash_module \
            --without-http_empty_gif_module \
            --without-http_referer_module \
            --without-http_autoindex_module \
            --without-http_auth_basic_module \
            --without-http_userid_module \
            --add-module=$root/../ndk-nginx-module \
            --add-module=$root/../set-misc-nginx-module \
          --add-module=$root/../ngx_http_redis \
          --add-module=$root/../echo-nginx-module \
          --add-module=$root $opts \
          --add-module=$root/../lua-nginx-module \
          --with-select_module \
          --with-poll_module \
          --with-debug
          #--add-module=/home/agentz/git/dodo/utils/dodo-hook \
          #--add-module=$home/work/ngx_http_auth_request-0.1 #\
          #--with-rtsig_module
          #--with-cc-opt="-g3 -O0"
          #--add-module=$root/../echo-nginx-module \
  #--without-http_ssi_module  # we cannot disable ssi because echo_location_async depends on it (i dunno why?!)

