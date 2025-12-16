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

function gen_package() {
    mode="$1"
    linux="$2"
    version="$(tr -d '\n' < VERSION)"
    if [[ "$linux" = fedora* ]] || [[ "$linux" = rhel* ]] ; then
        type="rpm"
    else
        type="deb"
    fi
    do_and_check_cmd docker run --rm -v "/tmp/packages/${linux}:/data" "bw-${linux}-tests:latest" "$type"
    name="bunkerweb_${version}-1_amd64"
    if [ "$type" = "rpm" ] ; then
        name="bunkerweb-${version}-1.x86_64"
    fi
    do_and_check_cmd cp "/tmp/packages/${linux}/bunkerweb.$type" "/opt/packages/${mode}/${linux}/${name}.${type}"
}

function build_image() {
	linux="$1"
	do_and_check_cmd docker build -t "bw-${linux}" -f "./tests/Dockerfile-${linux}" .
}

if [ ! -d /opt/packages ] ; then
    do_and_check_cmd sudo mkdir -p /opt/packages/{dev,prod}/{ubuntu,debian-bookworm,debian-trixie,fedora-41,fedora-42,fedora-43,rhel-8,rhel-9,rhel-10}
    do_and_check_cmd sudo chmod -R 777 /opt/packages/
fi

if [ -d /tmp/packages ] ; then
    do_and_check_cmd sudo rm -rf /tmp/packages
fi
do_and_check_cmd mkdir /tmp/packages

# Remove old packages
find /opt/packages/ -type f -exec rm -f {} \;

# Generate packages
# echo "Building ubuntu package ..."
# gen_package "$1" "ubuntu"
# echo "Building debian package ..."
# gen_package "$1" "debian"
# echo "Building centos package ..."
# gen_package "$1" "centos"
echo "Building fedora 41 package ..."
gen_package "$1" "fedora-41"
echo "Building fedora 42 package ..."
gen_package "$1" "fedora-42"
echo "Building fedora 43 package ..."
gen_package "$1" "fedora-43"
echo "Building rhel-8 package ..."
gen_package "$1" "rhel-8"
echo "Building rhel-9 package ..."
gen_package "$1" "rhel-9"
echo "Building rhel-10 package ..."
gen_package "$1" "rhel-10"

# Copy packages in the Docker context
do_and_check_cmd cp -r "/opt/packages/$1" ./packages

# Build test images
# echo "Building ubuntu test image ..."
# build_image "ubuntu"
# echo "Building debian test image ..."
# build_image "debian"
# echo "Building centos test image ..."
# build_image "centos"
echo "Building fedora 41 test image ..."
build_image "fedora-41"
echo "Building fedora 42 test image ..."
build_image "fedora-42"
echo "Building fedora 43 test image ..."
build_image "fedora-43"
echo "Building rhel-8 test image ..."
build_image "rhel-8"
echo "Building rhel-9 test image ..."
build_image "rhel-9"
echo "Building rhel-10 test image ..."
build_image "rhel-10"

exit 0
