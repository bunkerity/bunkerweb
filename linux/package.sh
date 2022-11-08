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

# Check arg
if [ "$1" = "" ] ; then
	echo "❌ Missing distro arg"
	exit 1
fi
linux="$1"

# Create empty directory
package_dir="./package-$linux"
if [ -d "$package_dir" ] ; then
	do_and_check_cmd rm -rf "$package_dir"
fi
do_and_check_cmd mkdir "$package_dir"

# Generate package
version="$(cat VERSION | tr -d '\n')"
type="deb"
if [ "$linux" = "fedora" ] || [ "$linux" = "centos" ] ; then
	type="rpm"
fi
do_and_check_cmd docker run --rm -v "${package_dir}:/data" "local/bunkerweb-${linux}:latest" "$type"
name="bunkerweb_${version}-1_amd64"
if [ "$type" = "rpm" ] ; then
	name="bunkerweb-${version}-1.x86_64"
fi
do_and_check_cmd mv "${package_dir}/bunkerweb.$type" "${package_dir}/${name}.${type}"

exit 0
