#!/bin/bash

. ./tests/utils/utils.sh

function gen_package() {
    mode="$1"
    linux="$2"
    version="$(cat VERSION | tr -d '\n')"
    if [ "$linux" = "fedora" ] || [ "$linux" = "centos" ] ; then
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
	mode="$1"
	linux="$2"
	do_and_check_cmd docker build -t "bw-${linux}" --build-arg "target=${mode}" -f "./Dockerfile-${linux}" .
}

echo "Linux tests"

if [ ! -d /opt/packages ] ; then
    do_and_check_cmd sudo mkdir -p /opt/packages/{dev,prod}/{ubuntu,debian,fedora,centos}
    do_and_check_cmd sudo chmod -R 777 /opt/packages/
fi

if [ -d /tmp/packages ] ; then
    do_and_check_cmd sudo rm -rf /tmp/packages
fi
do_and_check_cmd mkdir /tmp/packages

# Generate packages
gen_package "$1" "ubuntu"
gen_package "$1" "debian"
gen_package "$1" "centos"
gen_package "$1" "fedora"

# Build test images
build_image "$1" "ubuntu"
build_image "$1" "debian"
build_image "$1" "centos"
build_image "$1" "fedora"

exit 0
