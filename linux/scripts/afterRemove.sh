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
elif [ "$(grep Fedora /etc/os-release)" != "" ] ; then
	OS="fedora"
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
# echo "ℹ️ Restore old nginx service"
# do_and_check_cmd mv /lib/systemd/system/nginx.service.bak /lib/systemd/system/nginx.service
# do_and_check_cmd systemctl daemon-reload

# Remove UI service
systemctl status bunkerweb-ui > /dev/null 2>&1
if [ $? -eq 0 ] ; then
	echo "ℹ️ Stop bunkerweb-ui service"
	do_and_check_cmd systemctl stop bunkerweb-ui
fi

# echo "ℹ️ Remove bunkerweb-ui service"
if [ -f "/etc/systemd/system/bunkerweb-ui.service" ] ; then
    echo "ℹ️ Remove bunkerweb-ui service"
    do_and_check_cmd systemctl stop bunkerweb-ui
    do_and_check_cmd systemctl disable bunkerweb-ui
    do_and_check_cmd rm -f /etc/systemd/system/bunkerweb-ui.service
    do_and_check_cmd systemctl daemon-reload
    do_and_check_cmd systemctl reset-failed
fi
# do_and_check_cmd systemctl disable bunkerweb-ui
# do_and_check_cmd rm -f /etc/systemd/system/bunkerweb-ui.service
# do_and_check_cmd systemctl daemon-reload
# do_and_check_cmd systemctl reset-failed
# do_and_check_cmd sed -i "s@nginx ALL=(root:root) NOPASSWD: /usr/share/bunkerweb/ui/linux.sh@@" /etc/sudoers

# Remove /usr/share/bunkerweb
if [ -e "/usr/share/bunkerweb" ] ; then
	echo "ℹ️ Remove /usr/share/bunkerweb"
	do_and_check_cmd rm -rf /usr/share/bunkerweb
fi

# Remove /etc/bunkerweb
if [ -e "/etc/bunkerweb" ] ; then
	echo "ℹ️ Remove /etc/bunkerweb"
	do_and_check_cmd rm -rf /etc/bunkerweb
fi

# Remove /var/tmp/bunkerweb
if [ -e "/var/tmp/bunkerweb" ] ; then
	echo "ℹ️ Remove /var/tmp/bunkerweb"
	do_and_check_cmd rm -rf /var/tmp/bunkerweb
fi

# Remove /var/cache/bunkerweb
if [ -e "/var/cache/bunkerweb" ] ; then
	echo "ℹ️ Remove /var/cache/bunkerweb"
	do_and_check_cmd rm -rf /var/cache/bunkerweb
fi

# Remove /var/lib/bunkerweb
if [ -e "/var/lib/bunkerweb" ] ; then
	echo "ℹ️ Remove /var/lib/bunkerweb"
	do_and_check_cmd rm -rf /var/lib/bunkerweb
fi

# Remove /usr/bin/bwcli
if [ -f "/usr/bin/bwcli" ] ; then
	echo "ℹ️ Remove /usr/bin/bwcli"
	do_and_check_cmd rm -f /usr/bin/bwcli
fi

# Remove systemd service
if [ -f "/etc/systemd/system/bunkerweb.service" ] ; then
    echo "ℹ️ Remove bunkerweb service"
    do_and_check_cmd systemctl stop bunkerweb
    do_and_check_cmd systemctl disable bunkerweb
    do_and_check_cmd rm -f /etc/systemd/system/bunkerweb.service
    do_and_check_cmd systemctl daemon-reload
    do_and_check_cmd systemctl reset-failed
fi

# Uninstall nginx
# if [ "$OS" = "debian" ] || [ "$OS" = "ubuntu" ] ; then
#     echo "ℹ️ Uninstall nginx"
#     do_and_check_cmd systemctl stop nginx
#     do_and_check_cmd apt remove nginx -y
#     echo "ℹ️ If you want to reinstall nginx, run the following command:"
#     echo "apt-get install nginx"
# elif [ "$OS" = "centos" ] || [ "$OS" = "fedora" ] ; then
#     echo "ℹ️ Uninstall nginx"
#     do_and_check_cmd systemctl stop nginx
#     do_and_check_cmd yum remove nginx -y 
#     echo "ℹ️ If you want to reinstall nginx, run the following command:"
#     echo "apt-get install nginx"
# fi

# We're done
echo "ℹ️ BunkerWeb successfully uninstalled"
