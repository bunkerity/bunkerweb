#!/bin/bash

function git_secure_checkout() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	path="$1"
	commit="$2"
	cd "$path"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from submodules $path !"
		echo "$output"
		exit 4
	fi
}

function git_secure_clone() {
	cd /tmp/bunkerized-nginx
	repo="$1"
	commit="$2"
	folder="$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")"
	output="$(git clone "$repo" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "[!] Error cloning $1"
		echo "$output"
		exit 2
	fi
	cd "$folder"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from repository $repo"
		echo "$output"
		exit 3
	fi
}

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "[!] Error from command : $*"
		echo "$output"
		exit $ret
	fi
	#echo $output
	return 0
}

function get_nginx_signing_key() {
	key="-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v2.0.22 (GNU/Linux)

mQENBE5OMmIBCAD+FPYKGriGGf7NqwKfWC83cBV01gabgVWQmZbMcFzeW+hMsgxH
W6iimD0RsfZ9oEbfJCPG0CRSZ7ppq5pKamYs2+EJ8Q2ysOFHHwpGrA2C8zyNAs4I
QxnZZIbETgcSwFtDun0XiqPwPZgyuXVm9PAbLZRbfBzm8wR/3SWygqZBBLdQk5TE
fDR+Eny/M1RVR4xClECONF9UBB2ejFdI1LD45APbP2hsN/piFByU1t7yK2gpFyRt
97WzGHn9MV5/TL7AmRPM4pcr3JacmtCnxXeCZ8nLqedoSuHFuhwyDnlAbu8I16O5
XRrfzhrHRJFM1JnIiGmzZi6zBvH0ItfyX6ttABEBAAG0KW5naW54IHNpZ25pbmcg
a2V5IDxzaWduaW5nLWtleUBuZ2lueC5jb20+iQE+BBMBAgAoAhsDBgsJCAcDAgYV
CAIJCgsEFgIDAQIeAQIXgAUCV2K1+AUJGB4fQQAKCRCr9b2Ce9m/YloaB/9XGrol
kocm7l/tsVjaBQCteXKuwsm4XhCuAQ6YAwA1L1UheGOG/aa2xJvrXE8X32tgcTjr
KoYoXWcdxaFjlXGTt6jV85qRguUzvMOxxSEM2Dn115etN9piPl0Zz+4rkx8+2vJG
F+eMlruPXg/zd88NvyLq5gGHEsFRBMVufYmHtNfcp4okC1klWiRIRSdp4QY1wdrN
1O+/oCTl8Bzy6hcHjLIq3aoumcLxMjtBoclc/5OTioLDwSDfVx7rWyfRhcBzVbwD
oe/PD08AoAA6fxXvWjSxy+dGhEaXoTHjkCbz/l6NxrK3JFyauDgU4K4MytsZ1HDi
MgMW8hZXxszoICTTiQEcBBABAgAGBQJOTkelAAoJEKZP1bF62zmo79oH/1XDb29S
YtWp+MTJTPFEwlWRiyRuDXy3wBd/BpwBRIWfWzMs1gnCjNjk0EVBVGa2grvy9Jtx
JKMd6l/PWXVucSt+U/+GO8rBkw14SdhqxaS2l14v6gyMeUrSbY3XfToGfwHC4sa/
Thn8X4jFaQ2XN5dAIzJGU1s5JA0tjEzUwCnmrKmyMlXZaoQVrmORGjCuH0I0aAFk
RS0UtnB9HPpxhGVbs24xXZQnZDNbUQeulFxS4uP3OLDBAeCHl+v4t/uotIad8v6J
SO93vc1evIje6lguE81HHmJn9noxPItvOvSMb2yPsE8mH4cJHRTFNSEhPW6ghmlf
Wa9ZwiVX5igxcvaIRgQQEQIABgUCTk5b0gAKCRDs8OkLLBcgg1G+AKCnacLb/+W6
cflirUIExgZdUJqoogCeNPVwXiHEIVqithAM1pdY/gcaQZmIRgQQEQIABgUCTk5f
YQAKCRCpN2E5pSTFPnNWAJ9gUozyiS+9jf2rJvqmJSeWuCgVRwCcCUFhXRCpQO2Y
Va3l3WuB+rgKjsQ=
=EWWI
-----END PGP PUBLIC KEY BLOCK-----"
	echo "$key"
}

# Variables
NTASK=$(nproc)

# Check if we are root
if [ $(id -u) -ne 0 ] ; then
	echo "[!] Run me as root"
	exit 1
fi

# Create /tmp/bunkerized-nginx
echo "[*] Prepare /tmp/bunkerized-nginx"
if [ -e "/tmp/bunkerized-nginx" ] ; then
	do_and_check_cmd rm -rf /tmp/bunkerized-nginx
fi
do_and_check_cmd mkdir /tmp/bunkerized-nginx

# Create /opt/bunkerized-nginx
echo "[*] Prepare /opt/bunkerized-nginx"
if [ -e "/opt/bunkerized-nginx" ] ; then
	do_and_check_cmd rm -rf /opt/bunkerized-nginx
fi
do_and_check_cmd mkdir /opt/bunkerized-nginx

# TODO : detect OS
OS="debian"

# Check nginx version
NGINX_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
# Add nginx official repo and install
if [ "$NGINX_VERSION" = "" ] ; then
	if [ "$OS" = "debian" ] ; then
		echo "[*] Add nginx official repository"
		do_and_check_cmd apt update
		do_and_check_cmd apt install -y curl gnupg2 ca-certificates lsb-release software-properties-common
		get_nginx_signing_key > /tmp/bunkerized-nginx/nginx_signing.key
		do_and_check_cmd cp /tmp/bunkerized-nginx/nginx_signing.key /etc/apt/trusted.gpg.d/nginx_signing.asc
		do_and_check_cmd add-apt-repository "deb http://nginx.org/packages/debian $(lsb_release -cs) nginx"
		do_and_check_cmd apt update
		echo "[*] Install nginx"
		do_and_check_cmd apt install -y nginx
	fi
	NGINX_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
fi
echo "[*] Detected nginx version ${NGINX_VERSION}"
if [ "$NGINX_VERSION" != "1.20.1" ] ; then
	echo "/!\\ Warning : we recommend you to use nginx v1.20.1, you should uninstall your nginx version and run this script again ! /!\\"
fi

# Install dependencies
# TODO : detect Linux flavor
echo "[*] Update packet list"
do_and_check_cmd apt update
echo "[*] Install dependencies"
DEBIAN_DEPS="git autoconf pkg-config libpcre++-dev automake libtool g++ make liblua5.1-0-dev libgd-dev lua5.1 libssl-dev wget libmaxminddb-dev libbrotli-dev gnupg"
do_and_check_cmd apt install -y $DEBIAN_DEPS
# TODO : is it the same for other distro ?
cp -r /usr/include/lua5.1/* /usr/include

# Download, compile and install ModSecurity
echo "[*] Clone SpiderLabs/ModSecurity"
git_secure_clone https://github.com/SpiderLabs/ModSecurity.git 753145fbd1d6751a6b14fdd700921eb3cc3a1d35
echo "[*] Compile and install ModSecurity"
# temp fix : Debian run it twice
cd /tmp/bunkerized-nginx/ModSecurity && ./build.sh > /dev/null 2>&1
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd sh build.sh
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd git submodule init
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd git submodule update
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" git_secure_checkout bindings/python 47a6925df187f96e4593afab18dc92d5f22bd4d5
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" git_secure_checkout others/libinjection bf234eb2f385b969c4f803b35fda53cffdd93922
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" git_secure_checkout test/test-cases/secrules-language-tests d03f4c1e930440df46c1faa37d820a919704d9da
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd ./configure --enable-static=no --disable-doxygen-doc --disable-dependency-tracking --disable-examples
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd make install-strip

# Download and install OWASP Core Rule Set
echo "[*] Clone coreruleset/coreruleset"
git_secure_clone https://github.com/coreruleset/coreruleset.git 7776fe23f127fd2315bad0e400bdceb2cabb97dc
echo "[*] Install coreruleset"
do_and_check_cmd mkdir /opt/bunkerized-nginx/crs
do_and_check_cmd cp -r /tmp/bunkerized-nginx/coreruleset/rules /opt/bunkerized-nginx/crs/
do_and_check_cmd cp /tmp/bunkerized-nginx/coreruleset/crs-setup.conf.example /opt/bunkerized-nginx/crs.conf

# Download ModSecurity-nginx module
echo "[*] Clone SpiderLabs/ModSecurity-nginx"
git_secure_clone https://github.com/SpiderLabs/ModSecurity-nginx.git 2497e6ac654d0b117b9534aa735b757c6b11c84f

# Download headers more module
echo "[*] Clone openresty/headers-more-nginx-module"
git_secure_clone https://github.com/openresty/headers-more-nginx-module.git d6d7ebab3c0c5b32ab421ba186783d3e5d2c6a17

# Download GeoIP moduke
echo "[*] Clone leev/ngx_http_geoip2_module"
git_secure_clone https://github.com/leev/ngx_http_geoip2_module.git 1cabd8a1f68ea3998f94e9f3504431970f848fbf

# Download cookie flag module
echo "[*] Clone AirisX/nginx_cookie_flag_module"
git_secure_clone https://github.com/AirisX/nginx_cookie_flag_module.git c4ff449318474fbbb4ba5f40cb67ccd54dc595d4

# Download brotli module
echo "[*] Clone google/ngx_brotli"
git_secure_clone https://github.com/google/ngx_brotli.git 9aec15e2aa6feea2113119ba06460af70ab3ea62

# Download lua-nginx module
git_secure_clone https://github.com/openresty/lua-nginx-module.git 2d23bc4f0a29ed79aaaa754c11bffb1080aa44ba

# Download, compile and install luajit2
echo "[*] Clone openresty/luajit2"
git_secure_clone https://github.com/openresty/luajit2.git fe32831adcb3f5fe9259a9ce404fc54e1399bba3
echo "[*] Compile luajit2"
CHANGE_DIR="/tmp/bunkerized-nginx/luajit2" do_and_check_cmd make -j $NTASK
echo "[*] Install luajit2"
CHANGE_DIR="/tmp/bunkerized-nginx/luajit2" do_and_check_cmd make install

# Download and install lua-resty-core
echo "[*] Clone openresty/lua-resty-core"
git_secure_clone https://github.com/openresty/lua-resty-core.git b7d0a681bb41e6e3f29e8ddc438ef26fd819bb19
echo "[*] Install lua-resty-core"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-core" do_and_check_cmd make install

# Download and install lua-resty-lrucache
echo "[*] Clone openresty/lua-resty-lrucache"
git_secure_clone https://github.com/openresty/lua-resty-lrucache.git b2035269ac353444ac65af3969692bcae4fc1605
echo "[*] Install lua-resty-lrucache"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-lrucache" do_and_check_cmd make install

# Download and install lua-resty-dns
echo "[*] Clone openresty/lua-resty-dns"
git_secure_clone https://github.com/openresty/lua-resty-dns.git 24c9a69808aedfaf029ae57707cdef75d83e2d19
echo "[*] Install lua-resty-dns"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-dns" do_and_check_cmd make install

# Download and install lua-resty-session
echo "[*] Clone bungle/lua-resty-session"
git_secure_clone https://github.com/bungle/lua-resty-session.git f300870ce4eee3f4903e0565c589f1faf0c1c5aa
echo "[*] Install lua-resty-session"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/lua-resty-session/lib/resty/* /usr/local/lib/lua/resty

# Download and install lua-resty-random
echo "[*] Clone bungle/lua-resty-random"
git_secure_clone https://github.com/bungle/lua-resty-random.git 17b604f7f7dd217557ca548fc1a9a0d373386480
echo "[*] Install lua-resty-random"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-random" do_and_check_cmd make install

# Download and install lua-resty-string
echo "[*] Clone openresty/lua-resty-string"
git_secure_clone https://github.com/openresty/lua-resty-string.git 9a543f8531241745f8814e8e02475351042774ec
echo "[*] Install lua-resty-string"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-string" do_and_check_cmd make install

# Download, compile and install lua-cjson
echo "[*] Clone openresty/lua-cjson"
git_secure_clone https://github.com/openresty/lua-cjson.git 0df488874f52a881d14b5876babaa780bb6200ee
echo "[*] Compile lua-cjson"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-cjson" do_and_check_cmd make -j $NTASK
echo "[*] Install lua-cjson"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-cjson" do_and_check_cmd make install
CHANGE_DIR="/tmp/bunkerized-nginx/lua-cjson" do_and_check_cmd make install-extra

# Download, compile and install lua-gd
echo "[*] Clone ittner/lua-gd"
git_secure_clone https://github.com/ittner/lua-gd.git 2ce8e478a8591afd71e607506bc8c64b161bbd30
echo "[*] Compile lua-gd"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-gd" do_and_check_cmd make -j $NTASK
echo "[*] Install lua-gd"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-gd" do_and_check_cmd make INSTALL_PATH=/usr/local/lib/lua/5.1 install

# Download and install lua-resty-http
echo "[*] Clone ledgetech/lua-resty-http"
git_secure_clone https://github.com/ledgetech/lua-resty-http.git 984fdc26054376384e3df238fb0f7dfde01cacf1
echo "[*] Install lua-resty-http"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-http" do_and_check_cmd make install

# Download and install lualogging
echo "[*] Clone Neopallium/lualogging"
git_secure_clone https://github.com/Neopallium/lualogging.git cadc4e8fd652be07a65b121a3e024838db330c15
echo "[*] Install lualogging"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/lualogging/src/* /usr/local/lib/lua

# Download, compile and install luasocket
echo "[*] Clone diegonehab/luasocket"
git_secure_clone https://github.com/diegonehab/luasocket.git 5b18e475f38fcf28429b1cc4b17baee3b9793a62
echo "[*] Compile luasocket"
CHANGE_DIR="/tmp/bunkerized-nginx/luasocket" do_and_check_cmd make -j $NTASK
echo "[*] Install luasocket"
CHANGE_DIR="/tmp/bunkerized-nginx/luasocket" do_and_check_cmd make CDIR_linux=lib/lua/5.1 LDIR_linux=lib/lua install

# Download, compile and install luasec
echo "[*] Clone brunoos/luasec"
git_secure_clone https://github.com/brunoos/luasec.git c6704919bdc85f3324340bdb35c2795a02f7d625
echo "[*] Compile luasec"
CHANGE_DIR="/tmp/bunkerized-nginx/luasec" do_and_check_cmd make linux -j $NTASK
echo "[*] Install luasec"
CHANGE_DIR="/tmp/bunkerized-nginx/luasec" do_and_check_cmd make LUACPATH=/usr/local/lib/lua/5.1 LUAPATH=/usr/local/lib/lua install

# Download and install lua-cs-bouncer
echo "[*] Clone crowdsecurity/lua-cs-bouncer"
git_secure_clone https://github.com/crowdsecurity/lua-cs-bouncer.git 3c235c813fc453dcf51a391bc9e9a36ca77958b0
echo "[*] Install lua-cs-bouncer"
if [ ! -d /usr/local/lib/lua/crowdsec ] ; then
	do_and_check_cmd mkdir /usr/local/lib/lua/crowdsec
fi
do_and_check_cmd cp -r /tmp/bunkerized-nginx/lua-cs-bouncer/lib/* /usr/local/lib/lua/crowdsec
do_and_check_cmd sed -i 's/require "lrucache"/require "resty.lrucache"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua
do_and_check_cmd sed -i 's/require "config"/require "crowdsec.config"/' /usr/local/lib/lua/crowdsec/CrowdSec.lua

# Download and install lua-resty-iputils
echo "[*] Clone hamishforbes/lua-resty-iputils"
git_secure_clone https://github.com/hamishforbes/lua-resty-iputils.git 3151d6485e830421266eee5c0f386c32c835dba4
echo "[*] Install lua-resty-iputils"
CHANGE_DIR="/tmp/bunkerized-nginx/lua-resty-iputils" do_and_check_cmd make LUA_LIB_DIR=/usr/local/lib/lua install

# Download nginx and decompress sources
# TODO : check GPG signature
echo "[*] Download nginx-${NGINX_VERSION}.tar.gz"
do_and_check_cmd wget -O "/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz" "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz"
do_and_check_cmd wget -O "/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz.asc" "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz.asc"
get_nginx_signing_key > /tmp/bunkerized-nginx/nginx_signing.key
gpg --import /tmp/bunkerized-nginx/nginx_signing.key
check=$(gpg --verify /tmp/nginx-${NGINX_VERSION}.tar.gz.asc /tmp/nginx-${NGINX_VERSION}.tar.gz 2>&1 | grep "^gpg: Good signature from ")
if [ "$check" = "" ] ; then
	echo "[!] Wrong signature from nginx source !!!"
	exit 1
fi
CHANGE_DIR="/tmp/bunkerized-nginx" do_and_check_cmd tar -xvzf nginx-${NGINX_VERSION}.tar.gz

# Compile dynamic modules
echo "[*] Compile dynamic modules"
CONFARGS="$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')"
CONFARGS="${CONFARGS/-Os -fomit-frame-pointer -g/-Os}"
cd /tmp/bunkerized-nginx/nginx-${NGINX_VERSION}
output="$(./configure "$CONFARGS" --add-dynamic-module=/tmp/bunkerized-nginx/ModSecurity-nginx --add-dynamic-module=/tmp/bunkerized-nginx/headers-more-nginx-module --add-dynamic-module=/tmp/bunkerized-nginx/ngx_http_geoip2_module --add-dynamic-module=/tmp/bunkerized-nginx/nginx_cookie_flag_module --add-dynamic-module=/tmp/bunkerized-nginx/lua-nginx-module --add-dynamic-module=/tmp/bunkerized-nginx/ngx_brotli 2>&1)"
if [ $? -ne 0 ] ; then
	echo "configure failed"
	exit 1
fi
CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" LUAJIT_LIB="/usr/local/lib/" LUAJIT_INC="/usr/local/include/luajit-2.1" do_and_check_cmd make -j $NTASK modules
CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" do_and_check_cmd cp ./objs/*.so /usr/lib/nginx/modules

# We're done
echo "[*] Dependencies for bunkerized-nginx successfully installed !"
exit 0
