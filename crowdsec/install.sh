#!/bin/sh

function git_secure_clone() {
	repo="$1"
	commit="$2"
	folder=$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")
	git clone "$repo"
	cd "$folder"
	git checkout "${commit}^{commit}"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from repository $repo !"
		exit 1
	fi
	cd ..
}

NTASK=$(nproc)

# install build dependencies
apk add --no-cache --virtual build git bash lua-dev mariadb-dev sqlite-dev gettext make go jq

# build and install crowdsec
cd /tmp
git_secure_clone https://github.com/crowdsecurity/crowdsec.git 2fdf7624da381af605baa46f319f2ed3015807e4
cd crowdsec
make -j $NTASK build
./wizard.sh --bininstall
sed -i 's/^machine_id:.*//' /etc/crowdsec/config/api.yaml
sed -i 's/^password:.*//' /etc/crowdsec/config/api.yaml

# install nginx collection
cscli update
cscli install collection crowdsecurity/nginx
sed -i "s/^filter:.*$/filter: \"evt.Line.Labels.type == 'nginx'\"/" /etc/crowdsec/config/parsers/s01-parse/nginx-logs.yaml
sed -i 's/apply_on: message/apply_on: Line.Raw/g' /etc/crowdsec/config/parsers/s01-parse/nginx-logs.yaml

# build and install luasql
cd /tmp
git_secure_clone https://github.com/keplerproject/luasql.git 22d4a911f35cf851af9db71124e3998d96fb3fa1
cd luasql
make -j $NTASK sqlite3 mysql
mkdir /usr/local/lib/lua/5.1/luasql
cp src/*.so /usr/local/lib/lua/5.1/luasql

# install lualogging
cd /tmp
git_secure_clone https://github.com/Neopallium/lualogging.git cadc4e8fd652be07a65b121a3e024838db330c15
cd lualogging
cp -r src/* /usr/local/lib/lua

# install cs-lua-lib
cd /tmp
git_secure_clone https://github.com/crowdsecurity/cs-lua-lib.git 97e55a555a8f6d46c1c2032825a4578090283301
cd cs-lua-lib
mkdir /usr/local/lib/lua/crowdsec
cp lib/*.lua /usr/local/lib/lua/crowdsec
cp template.conf /usr/local/lib/lua/crowdsec/crowdsec.conf
rm /usr/local/lib/lua/crowdsec/lrucache.lua
sed -i 's/require "lrucache"/require "resty.lrucache"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua
sed -i 's/require "config"/require "crowdsec.config"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua

# remove build dependencies
apk del build
