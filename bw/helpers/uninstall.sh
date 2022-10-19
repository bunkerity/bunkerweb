#!/bin/bash

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	#echo $output
	return 0
}


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
fi
if [ "$OS" = "" ] ; then
	echo "❌ Unsupported Operating System"
	exit 1
fi

# Stop nginx
systemctl status nginx > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	echo "ℹ️ Stop nginx service"
	do_and_check_cmd systemctl stop nginx
fi

# Reload old nginx.service file
echo "ℹ️ Restore old nginx service"
do_and_check_cmd mv /lib/systemd/system/nginx.service.bak /lib/systemd/system/nginx.service
do_and_check_cmd systemctl daemon-reload

# Remove UI service
systemctl status bunkerweb-ui > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	echo "ℹ️ Stop bunkerweb-ui service"
	do_and_check_cmd systemctl stop bunkerweb-ui
fi
echo "ℹ️ Remove bunkerweb-ui service"
do_and_check_cmd systemctl disable bunkerweb-ui
do_and_check_cmd rm -f /lib/systemd/system/bunkerweb-ui.service
do_and_check_cmd systemctl daemon-reload
do_and_check_cmd systemctl reset-failed
do_and_check_cmd sed -i "s@nginx ALL=(root:root) NOPASSWD: /opt/bunkerweb/ui/linux.sh@@" /etc/sudoers

# Remove /opt/bunkerweb
if [ -e "/opt/bunkerweb" ] ; then
	echo "ℹ️ Remove /opt/bunkerweb"
	do_and_check_cmd rm -rf /opt/bunkerweb
fi

# We're done
echo "ℹ️ BunkerWeb successfully uninstalled"
