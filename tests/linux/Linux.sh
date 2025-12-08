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
    if [ "$DISTRO" = "debian-bookworm" ]; then
      sudo docker build -t linux-debian-bookworm -f src/linux/Dockerfile-debian-bookworm .
    fi
    if [ "$DISTRO" = "debian-trixie" ]; then
      sudo docker build -t linux-debian-trixie -f src/linux/Dockerfile-debian-trixie .
    fi
    if [ "$DISTRO" = "fedora-41" ]; then
      sudo docker build -t linux-fedora-41 -f src/linux/Dockerfile-fedora-41 .
    fi
    if [ "$DISTRO" = "fedora-42" ]; then
      sudo docker build -t linux-fedora-42 -f src/linux/Dockerfile-fedora-42 .
    fi
    if [ "$DISTRO" = "fedora-43" ]; then
      sudo docker build -t linux-fedora-43 -f src/linux/Dockerfile-fedora-43 .
    fi
    if [ "$DISTRO" = "rhel-8" ]; then
      sudo docker build -t linux-rhel-8 -f src/linux/Dockerfile-rhel-8 .
    fi
    if [ "$DISTRO" = "rhel-9" ]; then
      sudo docker build -t linux-rhel-9 -f src/linux/Dockerfile-rhel-9 .
    fi
    if [ "$DISTRO" = "rhel-10" ]; then
      sudo docker build -t linux-rhel-10 -f src/linux/Dockerfile-rhel-10 .
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
    if [ "$DISTRO" = "debian-bookworm" ]; then
      sudo docker run -v /tmp/debian-bookworm:/data linux-debian-bookworm
    fi
    if [ "$DISTRO" = "debian-trixie" ]; then
      sudo docker run -v /tmp/debian-trixie:/data linux-debian-trixie
    fi
    if [ "$DISTRO" = "fedora-41" ]; then
      sudo docker run -v /tmp/fedora-41:/data linux-fedora-41
    fi
    if [ "$DISTRO" = "fedora-42" ]; then
      sudo docker run -v /tmp/fedora-42:/data linux-fedora-42
    fi
    if [ "$DISTRO" = "fedora-43" ]; then
      sudo docker run -v /tmp/fedora-43:/data linux-fedora-43
    fi
    if [ "$DISTRO" = "rhel-8" ]; then
      sudo docker run -v /tmp/rhel-8:/data linux-rhel-8
    fi
    if [ "$DISTRO" = "rhel-9" ]; then
      sudo docker run -v /tmp/rhel-9:/data linux-rhel-9
    fi
    if [ "$DISTRO" = "rhel-10" ]; then
      sudo docker run -v /tmp/rhel-10:/data linux-rhel-10
    fi
    if [ "$DISTRO" = "ubuntu-jammy" ]; then
      sudo docker run -v /tmp/ubuntu-jammy:/data linux-ubuntu-jammy
    fi
  fi
}

# Retrieve $DISTRO from the user

function retrieveDistro() {
  echo "Which distro do you want to use? (ubuntu, debian-bookworm, debian-trixie, fedora-41, fedora-42, fedora-43, rhel-8, rhel-9, rhel-10)"
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
