#!/bin/bash

NGINX_VERSION="${NGINX_VERSION-1.22.0}"
BUILD_MODE="${BUILD_MODE-prod}"

function git_secure_checkout() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	path="$1"
	commit="$2"
	cd "$path"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Commit hash $commit is absent from submodules $path !"
		echo "$output"
		cleanup
		exit 4
	fi
}

function git_secure_clone() {
	cd /tmp/bunkerweb
	repo="$1"
	commit="$2"
	folder="$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")"
	output="$(git clone "$repo" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Error cloning $1"
		echo "$output"
		cleanup
		exit 2
	fi
	cd "$folder"
	output="$(git checkout "${commit}^{commit}" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Commit hash $commit is absent from repository $repo"
		echo "$output"
		cleanup
		exit 3
	fi
}

function secure_download() {
	cd /tmp/bunkerweb
	link="$1"
	file="$2"
	hash="$3"
	output="$(wget -q -O "$file" "$link" 2>&1)"
	if [ $? -ne 0 ] ; then
		echo "❌ Error downloading $link"
		echo "$output"
		cleanup
		exit 5
	fi
	check="$(sha512sum "$file" | cut -d ' ' -f 1)"
	if [ "$check" != "$hash" ] ; then
		echo "❌️ Wrong hash from file $link (expected $hash got $check)"
		cleanup
		exit 6
	fi
}

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		cleanup
		exit $ret
	fi
	#echo $output
	return 0
}

function cleanup() {
	echo "ℹ️ Cleaning /tmp/bunkerweb"
	rm -rf /tmp/bunkerweb
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

# Variables
NTASK=$(nproc)

# Check if we are root
if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
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
elif [ "$(grep Fedora /etc/os-release)" != "" ] ; then
	OS="fedora"
elif [ "$(grep Arch /etc/os-release)" != "" ] ; then
	OS="archlinux"
elif [ "$(grep Alpine /etc/os-release)" != "" ] ; then
	OS="alpine"
fi
if [ "$OS" = "" ] ; then
	echo "❌ Unsupported Operating System"
	exit 1
fi
old_dir="${PWD}"

# Create /tmp/bunkerweb
if [ -e "/tmp/bunkerweb" ] ; then
	echo "ℹ️ Remove existing /tmp/bunkerweb"
	do_and_check_cmd rm -rf /tmp/bunkerweb
fi

# Create /opt/bunkerweb
if [ -d "/opt/bunkerweb" ] ; then
	echo "❌️ Looks like bunkerweb is already installed. Updating is not supported yet, you need to uninstall first and then install it again."
	exit 1
fi
echo "ℹ️ Create /opt/bunkerweb"
do_and_check_cmd mkdir /opt/bunkerweb

# Check nginx version
NGINX_CHECK_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
# Add nginx official repo and install
if [ "$NGINX_CHECK_VERSION" = "" ] ; then
	get_sign_repo_key > /tmp/bunkerweb/nginx_signing.key
	if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
		echo "ℹ️ Add nginx official repository"
		do_and_check_cmd cp /tmp/bunkerweb/nginx_signing.key /etc/apt/trusted.gpg.d/nginx_signing.asc
		do_and_check_cmd apt update
		DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y gnupg2 ca-certificates lsb-release software-properties-common
		do_and_check_cmd add-apt-repository "deb http://nginx.org/packages/${OS} $(lsb_release -cs) nginx"
		do_and_check_cmd apt update
		echo "ℹ️ Install nginx"
		DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y "nginx=$NGINX_VERSION"
	elif [ "$OS" = "centos" ] ; then
		echo "ℹ️ Add nginx official repository"
		do_and_check_cmd yum install -y yum-utils
		do_and_check_cmd cp /tmp/bunkerweb/nginx_signing.key /etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
		do_and_check_cmd rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
		repo="[nginx-stable]
name=nginx stable repo
baseurl=http://nginx.org/packages/centos/\$releasever/\$basearch/
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-nginx
enabled=1
module_hotfixes=true"
		echo "$repo" > /tmp/bunkerweb/nginx.repo
		do_and_check_cmd cp /tmp/bunkerweb/nginx.repo /etc/yum.repos.d/nginx.repo
		echo "ℹ️ Install nginx"
		do_and_check_cmd yum install -y "nginx-$NGINX_VERSION"
	elif [ "$OS" = "fedora" ] ; then
		echo "ℹ️ Install nginx"
		do_and_check_cmd dnf install -y "nginx-$NGINX_VERSION"
	elif [ "$OS" = "archlinux" ] ; then
		echo "ℹ️ Update pacman DB"
		do_and_check_cmd pacman -Sy
		echo "ℹ️ Install nginx"
		do_and_check_cmd pacman -S --noconfirm "nginx=$NGINX_VERSION"
	elif [ "$OS" = "alpine" ] ; then
		echo "ℹ️ Add nginx official repository"
		get_sign_repo_key_rsa > /tmp/bunkerweb/nginx_signing.rsa.pub
		do_and_check_cmd cp /tmp/nginx_signing.rsa.pub /etc/apk/keys/nginx_signing.rsa.pub
		echo "@nginx http://nginx.org/packages/alpine/v$(egrep -o '^[0-9]+\.[0-9]+' /etc/alpine-release)/main" >> /etc/apk/repositories
		echo "ℹ️ Install nginx"
		do_and_check_cmd apk add "nginx@nginx=$NGINX_VERSION"
	fi
	NGINX_CHECK_VERSION="$(nginx -V 2>&1 | sed -rn 's~^nginx version: nginx/(.*)$~\1~p')"
fi
echo "ℹ️ Detected nginx version ${NGINX_CHECK_VERSION}"
if [ "$NGINX_CHECK_VERSION" != "$NGINX_VERSION" ] ; then
	echo "⚠️ Detected nginx version ${NGINX_CHECK_VERSION} but the official nginx version supported is ${NGINX_VERSION}. We recommend you to uninstall nginx and run the installation script again."
	read -p "Abort installation of BunkerWeb (Y/n) ? " -n 1 -r
	echo
	if [ "$REPLY" = "Y" ] || [ "$REPLY" = "y"] || [ "$REPLY" = "" ] ; then
		cleanup
		exit 1
	fi
	NGINX_VERSION="$NGINX_CHECK_VERSION"
fi

# Stop nginx on Linux
if [ "$OS" != "alpine" ] ; then
	systemctl status nginx > /dev/null 2>&1
	if [ $? -eq 0 ] ; then
		echo "ℹ️ Stop nginx service"
		do_and_check_cmd systemctl stop nginx
	fi
fi

# Install dependencies
echo "ℹ️ Update packet list"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	do_and_check_cmd apt update
elif [ "$OS" = "archlinux" ] ; then
	do_and_check_cmd pacman -Sy
fi
echo "ℹ️ Install compilation and runtime dependencies"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	DEBIAN_DEPS="git autoconf pkg-config libpcre++-dev automake libtool g++ make libgd-dev libssl-dev wget libbrotli-dev gnupg patch libreadline-dev certbot python3 python3-pip procps sudo"
	DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y $DEBIAN_DEPS
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd yum install -y epel-release
	CENTOS_DEPS="git autoconf pkg-config pcre-devel automake libtool gcc-c++ make gd-devel openssl-devel wget brotli-devel gnupg patch readline-devel ca-certificates certbot python3 python3-pip procps sudo"
	do_and_check_cmd yum install -y $CENTOS_DEPS
elif [ "$OS" = "fedora" ] ; then
	FEDORA_DEPS="git autoconf pkg-config pcre-devel automake libtool gcc-c++ make gd-devel openssl-devel wget brotli-devel gnupg libxslt-devel perl-ExtUtils-Embed gperftools-devel patch readline-devel certbot python3 python3-pip procps nginx-mod-stream sudo"
	do_and_check_cmd dnf install -y $FEDORA_DEPS
elif [ "$OS" = "archlinux" ] ; then
	ARCHLINUX_DEPS="git autoconf pkgconf pcre2 automake libtool gcc make gd openssl wget brotli gnupg libxslt patch readline certbot python python-pip procps sudo"
	do_and_check_cmd pacman -S --noconfirm $ARCHLINUX_DEPS
elif [ "$OS" = "alpine" ] ; then
	ALPINE_DEPS_COMPILE="git build autoconf libtool automake git geoip-dev yajl-dev g++ gcc curl-dev libxml2-dev pcre-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev"
	do_and_check_cmd apk add --no-cache --virtual build $ALPINE_DEPS_COMPILE
	ALPINE_DEPS_RUNTIME="certbot bash libgcc yajl libstdc++ openssl py3-pip git"
	do_and_check_cmd apk add --no-cache $ALPINE_DEPS_RUNTIME
fi

# Clone the repo
if [ ! -d "/tmp/bunkerweb-data" ] ls; then
	echo "ℹ️ Clone bunkerity/bunkerweb"
	if [ "$BUILD_MODE" = "prod" ] ; then
		CHANGE_DIR="/tmp" do_and_check_cmd git_secure_clone https://github.com/bunkerity/bunkerweb.git 3d2f5e2389e5f75131ae22f822a673b92cb12cca
	else
		CHANGE_DIR="/tmp" do_and_check_cmd git clone https://github.com/bunkerity/bunkerweb.git
		CHANGE_DIR="/tmp/bunkerweb" do_and_check_cmd git checkout dev
	fi
# Or rename the folder
else
	echo "ℹ️ Move /tmp/bunkerweb-data to /tmp/bunkerweb"
	do_and_check_cmd mv /tmp/bunkerweb-data /tmp/bunkerweb
fi

# Create deps folder
echo "ℹ️ Create /opt/bunkerweb/deps"
do_and_check_cmd mkdir /opt/bunkerweb/deps

# Compile and install lua
echo "ℹ️ Compile and install lua-5.1.5"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-5.1.5" do_and_check_cmd make -j $NTASK linux
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-5.1.5" do_and_check_cmd make INSTALL_TOP=/opt/bunkerweb/deps install

# Download, compile and install libmaxminddb
echo "ℹ️ Compile and install libmaxminddb"
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd ./bootstrap
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd ./configure --prefix=/opt/bunkerweb/deps --disable-tests
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/libmaxminddb" do_and_check_cmd make install

# Download, compile and install ModSecurity
echo "ℹ️ Compile and install ModSecurity"
# temp fix : Debian run it twice
# TODO : patch it in clone.sh
cd /tmp/bunkerweb/deps/src/ModSecurity && ./build.sh > /dev/null 2>&1
CHANGE_DIR="/tmp/bunkerweb/deps/src/ModSecurity" do_and_check_cmd sh build.sh
CHANGE_DIR="/tmp/bunkerweb/deps/src/ModSecurity" do_and_check_cmd ./configure --disable-doxygen-doc --disable-dependency-tracking --disable-examples --prefix=/opt/bunkerweb/deps --with-maxmind=/opt/bunkerweb/deps
CHANGE_DIR="/tmp/bunkerweb/deps/src/ModSecurity" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/ModSecurity" do_and_check_cmd make install-strip

# Compile and install luajit2
echo "ℹ️ Compile and install luajit2"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit2" do_and_check_cmd make -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luajit2" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Install lua-resty-core
echo "ℹ️ Install openresty/lua-resty-core"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-core" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Install lua-resty-lrucache
echo "ℹ️ Install lua-resty-lrucache"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-lrucache" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Install lua-resty-dns
echo "ℹ️ Install lua-resty-dns"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-dns" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Install lua-resty-session
echo "ℹ️ Install lua-resty-session"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lua-resty-session/lib/resty/* /opt/bunkerweb/deps/lib/lua/resty

# Install lua-resty-random
echo "ℹ️ Install lua-resty-random"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-random" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Install lua-resty-string
echo "ℹ️ Install lua-resty-string"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-string" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Compile and install lua-cjson
echo "ℹ️ Compile and install lua-cjson"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make LUA_INCLUDE_DIR=/opt/bunkerweb/deps/include -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps LUA_CMODULE_DIR=/opt/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/opt/bunkerweb/deps/lib/lua install
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-cjson" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps LUA_CMODULE_DIR=/opt/bunkerweb/deps/lib/lua LUA_MODULE_DIR=/opt/bunkerweb/deps/lib/lua install-extra

# Compile and install lua-gd
echo "ℹ️ Compile and install lua-gd"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-gd" do_and_check_cmd make "CFLAGS=-O3 -Wall -fPIC -fomit-frame-pointer -I/opt/bunkerweb/deps/include -DVERSION=\\\"2.0.33r3\\\"" "LFLAGS=-shared -L/opt/bunkerweb/deps/lib -llua -lgd -Wl,-rpath=/opt/bunkerweb/deps/lib" LUABIN=/opt/bunkerweb/deps/bin/lua -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-gd" do_and_check_cmd make INSTALL_PATH=/opt/bunkerweb/deps/lib/lua install

# Download and install lua-resty-http
echo "ℹ️ Install lua-resty-http"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-http" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps install

# Download and install lualogging
echo "ℹ️ Install lualogging"
do_and_check_cmd cp -r /tmp/bunkerweb/deps/src/lualogging/src/* /opt/bunkerweb/deps/lib/lua

# Compile and install luasocket
echo "ℹ️ Compile and install luasocket"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasocket" do_and_check_cmd make LUAINC_linux=/opt/bunkerweb/deps/include -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasocket" do_and_check_cmd make prefix=/opt/bunkerweb/deps CDIR_linux=lib/lua LDIR_linux=lib/lua install

# Compile and install luasec
echo "ℹ️ Compile and install luasec"
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasec" do_and_check_cmd make INC_PATH=-I/opt/bunkerweb/deps/include linux -j $NTASK
CHANGE_DIR="/tmp/bunkerweb/deps/src/luasec" do_and_check_cmd make LUACPATH=/opt/bunkerweb/deps/lib/lua LUAPATH=/opt/bunkerweb/deps/lib/lua install

# Install lua-resty-iputils
echo "ℹ️ Install lua-resty-iputils"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-iputils" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps LUA_LIB_DIR=/opt/bunkerweb/deps/lib/lua install

# Install lua-resty-redis
echo "ℹ️ Install lua-resty-redis"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-redis" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps LUA_LIB_DIR=/opt/bunkerweb/deps/lib/lua install

# Install lua-resty-upload
echo "ℹ️ Install lua-resty-upload"
CHANGE_DIR="/tmp/bunkerweb/deps/src/lua-resty-upload" do_and_check_cmd make PREFIX=/opt/bunkerweb/deps LUA_LIB_DIR=/opt/bunkerweb/deps/lib/lua install

# Compile dynamic modules
echo "ℹ️ Compile and install dynamic modules"
CONFARGS="$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p')"
CONFARGS="${CONFARGS/-Os -fomit-frame-pointer -g/-Os}"
if [ "$OS" = "fedora" ] ; then
	CONFARGS="$(echo -n "$CONFARGS" | sed "s/--with-ld-opt='.*'//" | sed "s/--with-cc-opt='.*'//")"
fi
echo "\#!/bin/bash" > "/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}/configure-fix.sh"
echo "./configure $CONFARGS --add-dynamic-module=/tmp/bunkerweb/deps/src/ModSecurity-nginx --add-dynamic-module=/tmp/bunkerweb/deps/src/headers-more-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_http_geoip2_module --add-dynamic-module=/tmp/bunkerweb/deps/src/nginx_cookie_flag_module --add-dynamic-module=/tmp/bunkerweb/deps/src/lua-nginx-module --add-dynamic-module=/tmp/bunkerweb/deps/src/ngx_brotli" >> "/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}/configure-fix.sh"
do_and_check_cmd chmod +x "/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}/configure-fix.sh"
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}" LUAJIT_LIB="/opt/bunkerweb/deps/lib -Wl,-rpath,/opt/bunkerweb/deps/lib" LUAJIT_INC="/opt/bunkerweb/deps/include/luajit-2.1" MODSECURITY_LIB="/opt/bunkerweb/deps/lib" MODSECURITY_INC="/opt/bunkerweb/deps/include" do_and_check_cmd ./configure-fix.sh
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}" do_and_check_cmd make -j $NTASK modules
do_and_check_cmd mkdir /opt/bunkerweb/modules
do_and_check_cmd chown root:nginx /opt/bunkerweb/modules
do_and_check_cmd chmod 750 /opt/bunkerweb/modules
CHANGE_DIR="/tmp/bunkerweb/deps/src/nginx-${NGINX_VERSION}" do_and_check_cmd cp ./objs/*.so /opt/bunkerweb/modules
do_and_check_cmd chmod 740 /opt/bunkerweb/modules/*.so

# TODO : temp fix for fedora
if [ "$OS" = "fedora" ] ; then
	cp /usr/lib64/nginx/modules/ngx_stream_module.so /opt/bunkerweb/modules/ngx_stream_module.so
fi

# Dependencies are installed
echo "ℹ️ Dependencies for bunkerweb successfully compiled and installed !"

# Remove build dependencies in container
if [ "$OS" = "alpine" ] ; then
	echo "ℹ️ Remove build dependencies"
	do_and_check_cmd apk del build
fi

# Install Python dependencies
echo "ℹ️ Install python dependencies"
do_and_check_cmd pip3 install --upgrade pip
do_and_check_cmd pip3 install -r /tmp/bunkerweb/gen/requirements.txt
do_and_check_cmd pip3 install -r /tmp/bunkerweb/job/requirements.txt
if [ "$OS" != "alpine" ] ; then
	do_and_check_cmd pip3 install -r /tmp/bunkerweb/ui/requirements.txt
fi
do_and_check_cmd pip3 install cryptography --upgrade

# Copy generator
echo "ℹ️ Copy generator"
do_and_check_cmd cp -r /tmp/bunkerweb/gen /opt/bunkerweb

# Copy configs
echo "ℹ️ Copy configs"
do_and_check_cmd cp -r /tmp/bunkerweb/confs /opt/bunkerweb

# Copy LUA
echo "ℹ️ Copy lua"
do_and_check_cmd cp -r /tmp/bunkerweb/lua /opt/bunkerweb

# Copy misc
echo "ℹ️ Copy misc"
do_and_check_cmd cp -r /tmp/bunkerweb/misc /opt/bunkerweb

# Copy core
echo "ℹ️ Copy core"
do_and_check_cmd cp -r /tmp/bunkerweb/core /opt/bunkerweb

# Copy job
echo "ℹ️ Copy job"
do_and_check_cmd cp -r /tmp/bunkerweb/job /opt/bunkerweb

# Copy cli
echo "ℹ️ Copy cli"
do_and_check_cmd cp -r /tmp/bunkerweb/cli /opt/bunkerweb

# Copy utils
echo "ℹ️ Copy utils"
do_and_check_cmd cp -r /tmp/bunkerweb/utils /opt/bunkerweb

# Copy helpers
echo "ℹ️ Copy helpers"
do_and_check_cmd cp -r /tmp/bunkerweb/helpers /opt/bunkerweb

# Copy UI
if [ "$OS" != "alpine" ] ; then
	echo "ℹ️ Copy UI"
	do_and_check_cmd cp -r /tmp/bunkerweb/ui /opt/bunkerweb
	do_and_check_cmd cp /tmp/bunkerweb/ui/bunkerweb-ui.service /lib/systemd/system
fi

# Copy settings
echo "ℹ️ Copy settings"
do_and_check_cmd cp /tmp/bunkerweb/settings.json /opt/bunkerweb

# Copy bwcli
echo "ℹ️ Copy bwcli"
do_and_check_cmd cp /tmp/bunkerweb/helpers/bwcli /usr/local/bin

# Copy VERSION
echo "ℹ️ Copy VERSION"
do_and_check_cmd cp /tmp/bunkerweb/VERSION /opt/bunkerweb

# Replace old nginx.service file
if [ "$OS" != "alpine" ] ; then
	do_and_check_cmd mv /lib/systemd/system/nginx.service /lib/systemd/system/nginx.service.bak
	do_and_check_cmd cp /tmp/bunkerweb/misc/nginx.service /lib/systemd/system/
fi

# Create nginx user
if [ "$(grep "nginx:" /etc/passwd)" = "" ] ; then
	echo "ℹ️ Add nginx user"
	do_and_check_cmd useradd -d /opt/bunkerweb -s /usr/sbin/nologin nginx
fi

# Create www folder
if [ ! -d "/opt/bunkerweb/www" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/www folder"
	do_and_check_cmd mkdir /opt/bunkerweb/www
fi

# Create http-confs folder
if [ ! -d "/opt/bunkerweb/http-confs" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/http-confs folder"
	do_and_check_cmd mkdir /opt/bunkerweb/http-confs
fi

# Create stream-confs folder
if [ ! -d "/opt/bunkerweb/stream-confs" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/stream-confs folder"
	do_and_check_cmd mkdir /opt/bunkerweb/stream-confs
fi

# Create server-confs folder
if [ ! -d "/opt/bunkerweb/server-confs" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/server-confs folder"
	do_and_check_cmd mkdir /opt/bunkerweb/server-confs
fi

# Create modsec-confs folder
if [ ! -d "/opt/bunkerweb/modsec-confs" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/modsec-confs folder"
	do_and_check_cmd mkdir /opt/bunkerweb/modsec-confs
fi

# Create modsec-crs-confs folder
if [ ! -d "/opt/bunkerweb/modsec-crs-confs" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/modsec-crs-confs folder"
	do_and_check_cmd mkdir /opt/bunkerweb/modsec-crs-confs
fi

# Create cache folder
if [ ! -d "/opt/bunkerweb/cache" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/cache folder"
	do_and_check_cmd mkdir /opt/bunkerweb/cache
fi

# Create tmp folder
if [ ! -d "/opt/bunkerweb/tmp" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/tmp folder"
	do_and_check_cmd mkdir -p /opt/bunkerweb/tmp
fi

# Create plugins folder
if [ ! -d "/opt/bunkerweb/plugins" ] ; then
	echo "ℹ️ Create /opt/bunkerweb/plugins folder"
	do_and_check_cmd mkdir /opt/bunkerweb/plugins
fi

# Set permissions for /opt/bunkerweb
echo "ℹ️ Set permissions on files and folders"
do_and_check_cmd chown -R root:nginx /opt/bunkerweb
do_and_check_cmd find /opt/bunkerweb -type f -exec chmod 0740 {} \;
do_and_check_cmd find /opt/bunkerweb -type d -exec chmod 0750 {} \;
do_and_check_cmd chmod 770 /opt/bunkerweb/cache
do_and_check_cmd chmod 770 /opt/bunkerweb/tmp
do_and_check_cmd chmod 750 /opt/bunkerweb/gen/main.py
do_and_check_cmd chmod 750 /opt/bunkerweb/job/main.py
do_and_check_cmd chmod 750 /opt/bunkerweb/cli/main.py
do_and_check_cmd chmod 750 /opt/bunkerweb/helpers/*.sh
# Set permissions for /usr/local/bin/bunkerweb
do_and_check_cmd chown root:nginx /usr/local/bin/bwcli
do_and_check_cmd chmod 750 /usr/local/bin/bwcli
# Set permissions for /opt
do_and_check_cmd chmod u+rx /opt
# Set permissions for /etc/nginx
do_and_check_cmd chown -R nginx:nginx /etc/nginx
do_and_check_cmd find /etc/nginx -type f -exec chmod 0774 {} \;
do_and_check_cmd find /etc/nginx -type d -exec chmod 0775 {} \;
# Set permissions for systemd files and reload config
if [ "$OS" != "alpine" ] ; then
	do_and_check_cmd chown root:root /lib/systemd/system/bunkerweb-ui.service
	do_and_check_cmd chmod 744 /lib/systemd/system/bunkerweb-ui.service
	do_and_check_cmd chown root:root /lib/systemd/system/nginx.service
	do_and_check_cmd chmod 744 /lib/systemd/system/nginx.service
	do_and_check_cmd systemctl daemon-reload
fi
# Allow RX access to others on /opt/bunkerweb
do_and_check_cmd chmod 755 /opt/bunkerweb
# Allow nginx group to do nginx reload as root
if [ "$OS" != "alpine" ] ; then
	do_and_check_cmd chown root:nginx /opt/bunkerweb/ui/linux.sh
	do_and_check_cmd chmod 750 /opt/bunkerweb/ui/linux.sh
	echo "nginx ALL=(root:root) NOPASSWD: /opt/bunkerweb/ui/linux.sh" >> /etc/sudoers
fi

# Prepare log files and folders
echo "ℹ️ Prepare log files and folders"
if [ ! -e "/var/log/nginx" ] ; then
	do_and_check_cmd mkdir /var/log/nginx
fi
if [ ! -e "/var/log/nginx/access.log" ] ; then
	do_and_check_cmd touch /var/log/nginx/access.log
fi
if [ ! -e "/var/log/nginx/error.log" ] ; then
	do_and_check_cmd touch /var/log/nginx/error.log
fi
if [ ! -e "/var/log/nginx/modsec_audit.log" ] ; then
	do_and_check_cmd touch /var/log/nginx/modsec_audit.log
fi
if [ ! -e "/var/log/nginx/jobs.log" ] ; then
	do_and_check_cmd touch /var/log/nginx/jobs.log
fi
if [ ! -e "/var/log/nginx/ui.log" ] ; then
	do_and_check_cmd touch /var/log/nginx/ui.log
fi
do_and_check_cmd chown -R root:nginx /var/log/nginx
do_and_check_cmd chmod -R 770 /var/log/nginx/

# Prepare Let's Encrypt files and folders
echo "ℹ️ Prepare Let's Encrypt files and folders"
if [ ! -e "/var/log/letsencrypt" ] ; then
	do_and_check_cmd mkdir /var/log/letsencrypt
fi
do_and_check_cmd chown root:nginx /var/log/letsencrypt
do_and_check_cmd chmod 770 /var/log/letsencrypt
if [ ! -e "/etc/letsencrypt" ] ; then
	do_and_check_cmd mkdir /etc/letsencrypt
fi
do_and_check_cmd chown root:nginx /etc/letsencrypt
do_and_check_cmd chmod 770 /etc/letsencrypt
if [ ! -e "/var/lib/letsencrypt" ] ; then
	do_and_check_cmd mkdir /var/lib/letsencrypt
fi
do_and_check_cmd chown root:nginx /var/lib/letsencrypt
do_and_check_cmd chmod 770 /var/lib/letsencrypt

# Docker specific
if [ "$OS" = "alpine" ] ; then
	echo "ℹ️ Preparing Docker image"
	# prepare folders
	folders="www http-confs server-confs stream-confs modsec-confs modsec-crs-confs cache plugins"
	for folder in $folders ; do
		if [ -e "/opt/bunkerweb/${folder}" ] ; then
			do_and_check_cmd rm -rf "/opt/bunkerweb/${folder}"
		fi
		do_and_check_cmd mkdir "/${folder}"
		do_and_check_cmd chown root:nginx "/${folder}"
		do_and_check_cmd chmod 770 "/${folder}"
		do_and_check_cmd ln -s "/$folder" "/opt/bunkerweb/$folder"
	done

	# prepare /var/log
	rm -f /var/log/nginx/*
	ln -s /proc/1/fd/2 /var/log/nginx/error.log
	ln -s /proc/1/fd/2 /var/log/nginx/modsec_audit.log
	ln -s /proc/1/fd/1 /var/log/nginx/access.log
	ln -s /proc/1/fd/1 /var/log/nginx/jobs.log
fi

# We're done
cd "$old_dir"
cleanup
echo "ℹ️ bunkerweb successfully installed !"