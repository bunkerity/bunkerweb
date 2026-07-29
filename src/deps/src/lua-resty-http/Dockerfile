FROM openresty/openresty:1.31.1.1-alpine-fat

RUN apk add --no-cache curl perl bash wget git perl-dev libarchive-tools nodejs; \
    ln -s /usr/bin/bsdtar /usr/bin/tar

RUN curl -s -L https://cpanmin.us | perl - App::cpanminus > /bin/cpanm && chmod +x /bin/cpanm

RUN cpanm -q -n Test::Nginx

RUN /usr/local/openresty/luajit/bin/luarocks install luacov && \
    /usr/local/openresty/luajit/bin/luarocks install lua-resty-openssl && \
    /usr/local/openresty/luajit/bin/luarocks install luacheck
