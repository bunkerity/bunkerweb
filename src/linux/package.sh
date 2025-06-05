#!/bin/bash

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR" || return 1
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
}

# Check args
if [ "$1" = "" ] ; then
	echo "❌ Missing distro arg"
	exit 1
fi
linux="$1"
if [ "$2" = "" ] ; then
	echo "❌ Missing arch arg"
	exit 1
fi
arch="$2"

# Create empty directory
package_dir="${PWD}/package-$linux"
if [ -d "$package_dir" ] ; then
	do_and_check_cmd rm -rf "$package_dir"
fi
do_and_check_cmd mkdir "$package_dir"

# Generate package
version="$3"
if [ -f "src/VERSION" ] ; then
	version="$(tr -d '\n' < src/VERSION)"
fi
type="deb"
if [[ "$linux" = fedora* ]] || [ "$linux" = "centos" ] || [[ "$linux" = rhel* ]] ; then
	type="rpm"
fi
do_and_check_cmd docker run --rm -e FPM_SKIP_COMPRESSION=yes -v "${package_dir}:/data" "local/bunkerweb-${linux}:latest" "$type"
name="bunkerweb_${version}-1_${arch}"
if [ "$type" = "rpm" ] ; then
	name="bunkerweb-${version}-1.${arch}"
fi
do_and_check_cmd mv "${package_dir}/bunkerweb.$type" "${package_dir}/${name}.${type}"

exit 0
