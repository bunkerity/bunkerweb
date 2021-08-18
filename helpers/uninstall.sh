#!/bin/bash

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
fi
if [ "$OS" = "" ] ; then
	echo "[!] Unsupported Operating System"
	exit 1
fi

# Stop nginx
systemctl status nginx > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	echo "[*] Stop nginx service"
	do_and_check_cmd systemctl stop nginx
fi

# Reload old nginx.service file
echo "[*] Restore old nginx service"
do_and_check_cmd mv /lib/systemd/system/nginx.service.bak /lib/systemd/system/nginx.service
do_and_check_cmd systemctl daemon-reload

# Remove UI service
systemctl status bunkerized-nginx-ui > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	echo "[*] Stop bunkerized-nginx-ui service"
	systemctl status nginx > /dev/null 2>&1
	do_and_check_cmd systemctl stop bunkerized-nginx-ui
fi
echo "[*] Remove bunkerized-nginx-ui service"
do_and_check_cmd systemctl disable bunkerized-nginx-ui
do_and_check_cmd rm -f /lib/systemd/system/bunkerized-nginx-ui.service
do_and_check_cmd systemctl daemon-reload
do_and_check_cmd systemctl reset-failed
sed -i "s@nginx ALL=(root:root) NOPASSWD: /opt/bunkerized-nginx/ui/linux.sh@@" /etc/sudoers

# Remove cron
echo "[*] Remove cron"
do_and_check_cmd rm -f /etc/crond.d/bunkerized-nginx

# Remove /opt/bunkerized-nginx
if [ -e "/opt/bunkerized-nginx" ] ; then
	echo "[*] Remove /opt/bunkerized-nginx"
	do_and_check_cmd rm -rf /opt/bunkerized-nginx
fi

# We're done
echo "[*] bunkerized-nginx successfully uninstalled"
