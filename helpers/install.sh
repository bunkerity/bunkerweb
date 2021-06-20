#!/bin/bash

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

# Remove /tmp/bunkerized-nginx
if [ -e "/tmp/bunkerized-nginx" ] ; then
	do_and_check_cmd rm -rf /tmp/bunkerized-nginx
fi

# Check /opt/bunkerized-nginx
if [ ! -d "/opt/bunkerized-nginx" ] ; then
	echo "[!] Missing /opt/bunkerized-nginx directory, did you run the dependencies script ?"
	exit 1
fi

# Install dependencies
echo "[*] Update packet list"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	do_and_check_cmd apt update
fi
echo "[*] Install dependencies"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	DEBIAN_DEPS="git cron curl"
	DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y $DEBIAN_DEPS
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd yum install -y epel-release
	CENTOS_DEPS="git crontabs curl"
	do_and_check_cmd yum install -y $CENTOS_DEPS
fi

# Clone the repo
echo "[*] Clone bunkerity/bunkerized-nginx"
CHANGE_DIR="/tmp" do_and_check_cmd git_secure_clone https://github.com/bunkerity/bunkerized-nginx.git 93543d3962473af42eb0295868f8ac4184d8eeca

# Copy generator
echo "[*] Copy generator"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/gen /opt/bunkerized-nginx

# Copy configs
echo "[*] Copy configs"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/confs /opt/bunkerized-nginx

# Copy scripts
echo "[*] Copy scripts"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/scripts /opt/bunkerized-nginx

# Copy LUA
echo "[*] Copy LUA"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/lua/* /usr/local/lib/lua

# Copy antibot
echo "[*] Copy antibot"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/antibot /opt/bunkerized-nginx

# Copy antibot
echo "[*] Copy defaults"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/defaults /opt/bunkerized-nginx

# Copy settings
echo "[*] Copy settings"
do_and_check_cmd cp /tmp/bunkerized-nginx/settings.json /opt/bunkerized-nginx

# Create nginx user
if [ "$(grep "nginx:" /etc/passwd)" = "" ] ; then
	echo "[*] Add nginx user"
	do_and_check_cmd useradd -d /opt/bunkerized-nginx -s /usr/sbin/nologin nginx
fi

# Install cron
echo "[*] Add jobs to crontab"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	do_and_check_cmd cp /tmp/bunkerized-nginx/misc/cron /var/spool/cron/crontabs/nginx
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd cp /tmp/bunkerized-nginx/misc/cron /var/spool/cron/nginx
fi

# Download abusers list
echo "[*] Download abusers list"
# TODO : call external script

# Download TOR exit nodes list
echo "[*] Download TOR exit nodes list"
# TODO : call external script

# Download proxies list
echo "[*] Download proxies list"
# TODO : call external script

# Download referrers list
echo "[*] Download referrers list"
# TODO : call external script

# Download user agents list
echo "[*] Download user agents list"
# TODO : call external script

# Download geoip database
echo "[*] Download proxies list"
# TODO : call external script

# We're done
echo "[*] bunkerized-nginx successfully installed !"
