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
		cleanup
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
		cleanup
		exit 2
	fi
	cd "$folder"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "[!] Commit hash $commit is absent from repository $repo"
		echo "$output"
		cleanup
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
		cleanup
		exit $ret
	fi
	#echo $output
	return 0
}

function cleanup() {
	echo "[*] Cleaning /tmp/bunkerized-nginx"
	rm -rf /tmp/bunkerized-nginx
}

function get_sign_repo_key() {
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

function get_sign_repo_key_rsa() {
	key="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA/hT2Chq4hhn+zasCn1gv
N3AVdNYGm4FVkJmWzHBc3lvoTLIMR1uoopg9EbH2faBG3yQjxtAkUme6aauaSmpm
LNvhCfENsrDhRx8KRqwNgvM8jQLOCEMZ2WSGxE4HEsBbQ7p9F4qj8D2YMrl1ZvTw
Gy2UW3wc5vMEf90lsoKmQQS3UJOUxHw0fhJ8vzNUVUeMQpRAjjRfVAQdnoxXSNSw
+OQD2z9obDf6YhQclNbe8itoKRckbfe1sxh5/TFef0y+wJkTzOKXK9yWnJrQp8V3
gmfJy6nnaErhxbocMg55QG7vCNejuV0a384ax0SRTNSZyIhps2Yuswbx9CLX8l+r
bQIDAQAB
-----END PUBLIC KEY-----"
	echo "$key"
}

function get_sign_source_keys() {
	keys="-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.11 (FreeBSD)

mQENBE7SKu8BCADQo6x4ZQfAcPlJMLmL8zBEBUS6GyKMMMDtrTh3Yaq481HB54oR
0cpKL05Ff9upjrIzLD5TJUCzYYM9GQOhguDUP8+ZU9JpSz3yO2TvH7WBbUZ8FADf
hblmmUBLNgOWgLo3W+FYhl3mz1GFS2Fvid6Tfn02L8CBAj7jxbjL1Qj/OA/WmLLc
m6BMTqI7IBlYW2vyIOIHasISGiAwZfp0ucMeXXvTtt14LGa8qXVcFnJTdwbf03AS
ljhYrQnKnpl3VpDAoQt8C68YCwjaNJW59hKqWB+XeIJ9CW98+EOAxLAFszSyGanp
rCqPd0numj9TIddjcRkTA/ZbmCWK+xjpVBGXABEBAAG0IU1heGltIERvdW5pbiA8
bWRvdW5pbkBtZG91bmluLnJ1PokBOAQTAQIAIgUCTtIq7wIbAwYLCQgHAwIGFQgC
CQoLBBYCAwECHgECF4AACgkQUgqZk6HAUvj+iwf/b4FS6zVzJ5T0v1vcQGD4ZzXe
D5xMC4BJW414wVMU15rfX7aCdtoCYBNiApPxEd7SwiyxWRhRA9bikUq87JEgmnyV
0iYbHZvCvc1jOkx4WR7E45t1Mi29KBoPaFXA9X5adZkYcOQLDxa2Z8m6LGXnlF6N
tJkxQ8APrjZsdrbDvo3HxU9muPcq49ydzhgwfLwpUs11LYkwB0An9WRPuv3jporZ
/XgI6RfPMZ5NIx+FRRCjn6DnfHboY9rNF6NzrOReJRBhXCi6I+KkHHEnMoyg8XET
9lVkfHTOl81aIZqrAloX3/00TkYWyM2zO9oYpOg6eUFCX/Lw4MJZsTcT5EKVxIhG
BBARAgAGBQJO01Y/AAoJEOzw6QssFyCDVyQAn3qwTZlcZgyyzWu9Cs8gJ0CXREaS
AJ92QjGLT9DijTcbB+q9OS/nl16Z/IhGBBARAgAGBQJO02JDAAoJEKk3YTmlJMU+
P64AnjCKEXFelSVMtgefJk3+vpyt3QX1AKCH9M3MbTWPeDUL+MpULlfdyfvjj7kB
DQRO0irvAQgA0LjCc8S6oZzjiap2MjRNhRFA5BYjXZRZBdKF2VP74avt2/RELq8G
W0n7JWmKn6vvrXabEGLyfkCngAhTq9tJ/K7LPx/bmlO5+jboO/1inH2BTtLiHjAX
vicXZk3oaZt2Sotx5mMI3yzpFQRVqZXsi0LpUTPJEh3oS8IdYRjslQh1A7P5hfCZ
wtzwb/hKm8upODe/ITUMuXeWfLuQj/uEU6wMzmfMHb+jlYMWtb+v98aJa2FODeKP
mWCXLa7bliXp1SSeBOEfIgEAmjM6QGlDx5sZhr2Ss2xSPRdZ8DqD7oiRVzmstX1Y
oxEzC0yXfaefC7SgM0nMnaTvYEOYJ9CH3wARAQABiQEfBBgBAgAJBQJO0irvAhsM
AAoJEFIKmZOhwFL4844H/jo8icCcS6eOWvnen7lg0FcCo1fIm4wW3tEmkQdchSHE
CJDq7pgTloN65pwB5tBoT47cyYNZA9eTfJVgRc74q5cexKOYrMC3KuAqWbwqXhkV
s0nkWxnOIidTHSXvBZfDFA4Idwte94Thrzf8Pn8UESudTiqrWoCBXk2UyVsl03gJ
blSJAeJGYPPeo+Yj6m63OWe2+/S2VTgmbPS/RObn0Aeg7yuff0n5+ytEt2KL51gO
QE2uIxTCawHr12PsllPkbqPk/PagIttfEJqn9b0CrqPC3HREePb2aMJ/Ctw/76CO
wn0mtXeIXLCTvBmznXfaMKllsqbsy2nCJ2P2uJjOntw=
=Tavt
-----END PGP PUBLIC KEY BLOCK-----
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
yh4LsaVRdhbFe9aNd/O5iNgDcQtCUg==
=/pFc
-----END PGP PUBLIC KEY BLOCK-----
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.11 (FreeBSD)

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
CoHAyoqJeb/xLBwuKWg0/4U=
=iFlP
-----END PGP PUBLIC KEY BLOCK-----"
	echo "$keys"
}

# Variables
NTASK=$(nproc)

# Check if we are root
if [ $(id -u) -ne 0 ] ; then
	echo "[!] Run me as root"
	exit 1
fi

# Detect OS
OS=""
if [ "$(grep Debian /etc/os-release)" != "" ] ; then
	OS="debian"
elif [ "$(grep Ubuntu /etc/os-release)" != "" ] ; then
	OS="ubuntu"
elif [ "$(grep CentOS /etc/os-release)" != "" ] ; then
	OS="centos"
elif [ "$(grep Alpine /etc/os-release)" != "" ] ; then
	OS="alpine"
fi
if [ "$OS" = "" ] ; then
	echo "[!] Unsupported Operating System"
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

# Check nginx version
NGINX_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
# Add nginx official repo and install
if [ "$NGINX_VERSION" = "" ] ; then
	get_sign_repo_key > /tmp/bunkerized-nginx/nginx_signing.key
	if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
		echo "[*] Add nginx official repository"
		do_and_check_cmd cp /tmp/bunkerized-nginx/nginx_signing.key /etc/apt/trusted.gpg.d/nginx_signing.asc
		do_and_check_cmd apt update
		DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y gnupg2 ca-certificates lsb-release software-properties-common
		do_and_check_cmd add-apt-repository "deb http://nginx.org/packages/${OS} $(lsb_release -cs) nginx"
		do_and_check_cmd apt update
		echo "[*] Install nginx"
		DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y nginx
	elif [ "$OS" = "centos" ] ; then
		echo "[*] Add nginx official repository"
		do_and_check_cmd yum install -y yum-utils
		cp /tmp/bunkerized-nginx/nginx_signing.key /etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
		do_and_check_cmd rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
		repo="[nginx-stable]
name=nginx stable repo
baseurl=http://nginx.org/packages/centos/\$releasever/\$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
enabled=1
module_hotfixes=true"
		echo "$repo" > /etc/yum.repos.d/nginx.repo
		echo "[*] Install nginx"
		do_and_check_cmd yum install -y nginx
	elif [ "$OS" = "alpine" ] ; then
		echo "[*] Add nginx official repository"
		get_sign_repo_key_rsa > /etc/apk/keys/nginx_signing.rsa.pub
		echo "@nginx http://nginx.org/packages/alpine/v$(egrep -o '^[0-9]+\.[0-9]+' /etc/alpine-release)/main" >> /etc/apk/repositories
		echo "[*] Install nginx"
		do_and_check_cmd apk add nginx@nginx
	fi
	NGINX_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
fi
echo "[*] Detected nginx version ${NGINX_VERSION}"
if [ "$NGINX_VERSION" != "1.20.1" ] ; then
	echo "/!\\ Warning : we recommend you to use nginx v1.20.1, you should uninstall your nginx version and run this script again ! /!\\"
fi

# Install dependencies
echo "[*] Update packet list"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	do_and_check_cmd apt update
fi
echo "[*] Install dependencies"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	DEBIAN_DEPS="git autoconf pkg-config libpcre++-dev automake libtool g++ make liblua5.1-0-dev libgd-dev lua5.1 libssl-dev wget libmaxminddb-dev libbrotli-dev gnupg"
	DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y $DEBIAN_DEPS
	do_and_check_cmd cp -r /usr/include/lua5.1/* /usr/include
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd yum install -y epel-release
	CENTOS_DEPS="git autoconf pkg-config pcre-devel automake libtool gcc-c++ make lua-devel gd-devel lua openssl-devel wget libmaxminddb-devel brotli-devel gnupg"
	do_and_check_cmd yum install -y $CENTOS_DEPS
elif [ "$OS" = "alpine" ] ; then
	ALPINE_DEPS="git build autoconf libtool automake git geoip-dev yajl-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers libmaxminddb-dev musl-dev lua-dev gd-dev gnupg brotli-dev openssl-dev"
	do_and_check_cmd apk add --no-cache --virtual build $ALPINE_DEPS
fi

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
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd ./configure --disable-doxygen-doc --disable-dependency-tracking --disable-examples
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerized-nginx/ModSecurity" do_and_check_cmd make install-strip

# Download and install OWASP Core Rule Set
echo "[*] Clone coreruleset/coreruleset"
git_secure_clone https://github.com/coreruleset/coreruleset.git 7776fe23f127fd2315bad0e400bdceb2cabb97dc
echo "[*] Install coreruleset"
do_and_check_cmd mkdir /opt/bunkerized-nginx/crs
do_and_check_cmd cp -r /tmp/bunkerized-nginx/coreruleset/rules/* /opt/bunkerized-nginx/crs
do_and_check_cmd cp /tmp/bunkerized-nginx/coreruleset/crs-setup.conf.example /opt/bunkerized-nginx/crs-setup.conf

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
if [ "$OS" = "centos" ] ; then
	CHANGE_DIR="/tmp/bunkerized-nginx/lua-gd" do_and_check_cmd make LUAPKG=lua LUABIN=lua -j $NTASK
else
	CHANGE_DIR="/tmp/bunkerized-nginx/lua-gd" do_and_check_cmd make -j $NTASK
fi
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
echo "[*] Download nginx-${NGINX_VERSION}.tar.gz"
do_and_check_cmd wget -O "/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz" "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz"
do_and_check_cmd wget -O "/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz.asc" "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz.asc"
get_sign_source_keys > /tmp/bunkerized-nginx/nginx.key
do_and_check_cmd gpg --import /tmp/bunkerized-nginx/nginx.key
check=$(gpg --verify /tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz.asc /tmp/bunkerized-nginx/nginx-${NGINX_VERSION}.tar.gz 2>&1 | grep "^gpg: Good signature from ")
if [ "$check" = "" ] ; then
	echo "[!] Wrong signature from nginx source !!!"
	cleanup
	exit 1
fi
CHANGE_DIR="/tmp/bunkerized-nginx" do_and_check_cmd tar -xvzf nginx-${NGINX_VERSION}.tar.gz

# Compile dynamic modules
echo "[*] Compile dynamic modules"
CONFARGS="$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')"
CONFARGS="${CONFARGS/-Os -fomit-frame-pointer -g/-Os}"
CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" LUAJIT_LIB="/usr/local/lib/" LUAJIT_INC="/usr/local/include/luajit-2.1" do_and_check_cmd ./configure $CONFARGS --add-dynamic-module=/tmp/bunkerized-nginx/ModSecurity-nginx --add-dynamic-module=/tmp/bunkerized-nginx/headers-more-nginx-module --add-dynamic-module=/tmp/bunkerized-nginx/ngx_http_geoip2_module --add-dynamic-module=/tmp/bunkerized-nginx/nginx_cookie_flag_module --add-dynamic-module=/tmp/bunkerized-nginx/lua-nginx-module --add-dynamic-module=/tmp/bunkerized-nginx/ngx_brotli
CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" do_and_check_cmd make -j $NTASK modules
if [ "$OS" = "centos" ] ; then
	CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" do_and_check_cmd cp ./objs/*.so /usr/lib64/nginx/modules
else
	CHANGE_DIR="/tmp/bunkerized-nginx/nginx-${NGINX_VERSION}" do_and_check_cmd cp ./objs/*.so /usr/lib/nginx/modules
fi

# We're done
if [ "$OS" = "alpine" ] ; then
	apk del build > /dev/null 2>&1
fi
cleanup
echo "[*] Dependencies for bunkerized-nginx successfully installed !"
exit 0
