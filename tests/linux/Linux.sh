#!/bin/bash
# Small code to build and run the tests on Linux with docker

# Check if the package already exists in /tmp/$DISTRO/bunkerweb.deb or /tmp/$DISTRO/bunkerweb.rpm
# Always remove the package before building it

function checkPackage() {
  if [ -n "$DISTRO" ]; then
    if [ -f "/tmp/$DISTRO/bunkerweb.deb" ]; then
      sudo rm -rf /tmp/"$DISTRO"/bunkerweb.deb
    fi
    if [ -f "/tmp/$DISTRO/bunkerweb.rpm" ]; then
      sudo rm -rf /tmp/"$DISTRO"/bunkerweb.rpm
    fi
  fi
}

# Build the package using the dockerfile

function buildPackage() {
  if [ -n "$DISTRO" ]; then
    if [ "$DISTRO" = "ubuntu" ]; then
      sudo docker build -t linux-ubuntu -f src/linux/Dockerfile-ubuntu .
    fi
    if [ "$DISTRO" = "debian" ]; then
      sudo docker build -t linux-debian -f src/linux/Dockerfile-debian .
    fi
    if [ "$DISTRO" = "centos" ]; then
      sudo docker build -t linux-centos -f src/linux/Dockerfile-centos .
    fi
    if [ "$DISTRO" = "fedora" ]; then
      sudo docker build -t linux-fedora -f src/linux/Dockerfile-fedora .
    fi
    if [ "$DISTRO" = "rhel" ]; then
      sudo docker build -t linux-rhel -f src/linux/Dockerfile-rhel .
    fi
    if [ "$DISTRO" = "rhel9" ]; then
      sudo docker build -t linux-rhel9 -f src/linux/Dockerfile-rhel9 .
    fi
    if [ "$DISTRO" = "ubuntu-jammy" ]; then
      sudo docker build -t linux-ubuntu-jammy -f src/linux/Dockerfile-ubuntu-jammy .
    fi
  fi
}

# Create the container and copy the package to the host

function createContainer() {
  if [ -n "$DISTRO" ]; then
    if [ "$DISTRO" = "ubuntu" ]; then
      sudo docker run -v /tmp/ubuntu:/data linux-ubuntu
    fi
    if [ "$DISTRO" = "debian" ]; then
      sudo docker run -v /tmp/debian:/data linux-debian
    fi
    if [ "$DISTRO" = "centos" ]; then
      sudo docker run -v /tmp/centos:/data linux-centos
    fi
    if [ "$DISTRO" = "fedora" ]; then
      sudo docker run -v /tmp/fedora:/data linux-fedora
    fi
    if [ "$DISTRO" = "rhel" ]; then
      sudo docker run -v /tmp/rhel:/data linux-rhel
    fi
    if [ "$DISTRO" = "rhel9" ]; then
      sudo docker run -v /tmp/rhel9:/data linux-rhel9
    fi
    if [ "$DISTRO" = "ubuntu-jammy" ]; then
      sudo docker run -v /tmp/ubuntu-jammy:/data linux-ubuntu-jammy
    fi
  fi
}

# Retrieve $DISTRO from the user

function retrieveDistro() {
  echo "Which distro do you want to use? (ubuntu, debian, centos, fedora, rhel, rhel9)"
  read -r DISTRO
}

# Main function

function main() {
  retrieveDistro
  checkPackage
  buildPackage
  createContainer
}

main
