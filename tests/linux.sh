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
    if [ "$linux" = "fedora" ] || [ "$linux" = "centos" ] || [[ "$linux" = rhel* ]] ; then
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
    do_and_check_cmd sudo mkdir -p /opt/packages/{dev,prod}/{ubuntu,debian,fedora,centos}
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
echo "Building fedora package ..."
gen_package "$1" "fedora"
echo "Building rhel package ..."
gen_package "$1" "rhel"
echo "Building rhel9 package ..."
gen_package "$1" "rhel9"

# Copy packages in the Docker context
do_and_check_cmd cp -r "/opt/packages/$1" ./packages

# Build test images
# echo "Building ubuntu test image ..."
# build_image "ubuntu"
# echo "Building debian test image ..."
# build_image "debian"
# echo "Building centos test image ..."
# build_image "centos"
echo "Building fedora test image ..."
build_image "fedora"
echo "Building rhel test image ..."
build_image "rhel"
echo "Building rhel9 test image ..."
build_image "rhel9"

exit 0
