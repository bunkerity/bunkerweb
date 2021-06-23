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
	DEBIAN_DEPS="git cron curl python3 python3-pip"
	DEBIAN_FRONTEND=noninteractive do_and_check_cmd apt install -y $DEBIAN_DEPS
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd yum install -y epel-release
	CENTOS_DEPS="git crontabs curl python3 python3-pip"
	do_and_check_cmd yum install -y $CENTOS_DEPS
fi
do_and_check_cmd pip3 install jinja2

# Clone the repo
echo "[*] Clone bunkerity/bunkerized-nginx"
#CHANGE_DIR="/tmp" do_and_check_cmd git_secure_clone https://github.com/bunkerity/bunkerized-nginx.git 09a2a4f9e531b93684b0916a5146091a818501d3
# TODO : do a secure clone
CHANGE_DIR="/tmp" do_and_check_cmd git clone https://github.com/bunkerity/bunkerized-nginx.git
CHANGE_DIR="/tmp/bunkerized-nginx" do_and_check_cmd git checkout dev

# Copy generator
echo "[*] Copy generator"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/gen /opt/bunkerized-nginx

# Copy entrypoint
echo "[*] Copy entrypoint"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/entrypoint /opt/bunkerized-nginx

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

# Copy defaults
echo "[*] Copy defaults"
do_and_check_cmd cp -r /tmp/bunkerized-nginx/defaults /opt/bunkerized-nginx

# Copy settings
echo "[*] Copy settings"
do_and_check_cmd cp /tmp/bunkerized-nginx/settings.json /opt/bunkerized-nginx

# Copy bunkerized-nginx
echo "[*] Copy bunkerized-nginx"
do_and_check_cmd cp /tmp/bunkerized-nginx/helpers/bunkerized-nginx /usr/local/bin

# Create nginx user
if [ "$(grep "nginx:" /etc/passwd)" = "" ] ; then
	echo "[*] Add nginx user"
	do_and_check_cmd useradd -d /opt/bunkerized-nginx -s /usr/sbin/nologin nginx
fi

# Create www folder
if [ ! -d "/opt/bunkerized-nginx/www" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/www folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/www
fi

# Create http-confs folder
if [ ! -d "/opt/bunkerized-nginx/http-confs" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/http-confs folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/http-confs
fi

# Create server-confs folder
if [ ! -d "/opt/bunkerized-nginx/server-confs" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/server-confs folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/server-confs
fi

# Create modsec-confs folder
if [ ! -d "/opt/bunkerized-nginx/modsec-confs" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/modsec-confs folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/modsec-confs
fi

# Create modsec-crs-confs folder
if [ ! -d "/opt/bunkerized-nginx/modsec-crs-confs" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/modsec-crs-confs folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/modsec-crs-confs
fi

# Create cache folder
if [ ! -d "/opt/bunkerized-nginx/cache" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/cache folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/cache
fi

# Create pre-server-confs folder
if [ ! -d "/opt/bunkerized-nginx/pre-server-confs" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/pre-server-confs folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/pre-server-confs
fi

# Create acme-challenge folder
if [ ! -d "/opt/bunkerized-nginx/acme-challenge" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/acme-challenge folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/acme-challenge
fi

# Create plugins folder
if [ ! -d "/opt/bunkerized-nginx/plugins" ] ; then
	echo "[*] Create /opt/bunkerized-nginx/plugins folder"
	do_and_check_cmd mkdir /opt/bunkerized-nginx/plugins
fi

# Set permissions for /opt/bunkerized-nginx
echo "[*] Set permissions for /opt/bunkerized-nginx files and folders"
do_and_check_cmd chown -R root:nginx /opt/bunkerized-nginx
do_and_check_cmd find /opt -type f -exec chmod 0740 {} \;
do_and_check_cmd find /opt -type d -exec chmod 0750 {} \;
do_and_check_cmd chmod 770 /opt/bunkerized-nginx/cache
do_and_check_cmd chmod 770 /opt/bunkerized-nginx/acme-challenge
do_and_check_cmd chmod 750 /opt/bunkerized-nginx/scripts/*
do_and_check_cmd chmod 750 /opt/bunkerized-nginx/entrypoint/*
do_and_check_cmd chmod 750 /opt/bunkerized-nginx/gen/main.py

# Set permissions for /usr/local/bin/bunkerized-nginx
do_and_check_cmd chown root:root /usr/local/bin/bunkerized-nginx
do_and_check_cmd chmod 750 /usr/local/bin/bunkerized-nginx

# Set permissions for /opt
do_and_check_cmd chmod u+rx /opt

# Install cron
echo "[*] Add jobs to crontab"
if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
	do_and_check_cmd cp /tmp/bunkerized-nginx/misc/cron /var/spool/cron/crontabs/nginx
elif [ "$OS" = "centos" ] ; then
	do_and_check_cmd cp /tmp/bunkerized-nginx/misc/cron /var/spool/cron/nginx
fi

# Download abusers list
echo "[*] Download abusers list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/abusers.sh

# Download TOR exit nodes list
echo "[*] Download TOR exit nodes list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/exit-nodes.sh

# Download proxies list
echo "[*] Download proxies list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/proxies.sh

# Download referrers list
echo "[*] Download referrers list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/referrers.sh

# Download user agents list
echo "[*] Download user agents list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/user-agents.sh

# Download geoip database
echo "[*] Download proxies list"
do_and_check_cmd /opt/bunkerized-nginx/scripts/geoip.sh

# We're done
echo "[*] bunkerized-nginx successfully installed !"
