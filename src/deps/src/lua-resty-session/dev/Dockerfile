FROM openresty/openresty:1.27.1.2-0-noble

ENV DEBIAN_FRONTEND noninteractive
ENV TEST_NGINX_BINARY openresty

USER root
RUN apt-get update && apt-get install -y gcc git cpanminus lua5.1 liblua5.1-dev luarocks

RUN luarocks --lua-version 5.1 install busted
RUN luarocks --lua-version 5.1 install pgmoon
RUN luarocks --lua-version 5.1 install lua-resty-rsa
RUN luarocks --lua-version 5.1 install lua-resty-redis-connector 
RUN luarocks --lua-version 5.1 install lua-resty-redis-cluster
RUN luarocks --lua-version 5.1 install inspect
RUN luarocks --lua-version 5.1 install LuaCov

RUN cpanm --notest Test::Nginx
