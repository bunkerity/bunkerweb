# About

The libmaxminddb library provides a C library for reading MaxMind DB files,
including the GeoIP2 databases from MaxMind. This is a custom binary format
designed to facilitate fast lookups of IP addresses while allowing for great
flexibility in the type of data associated with an address.

The MaxMind DB format is an open format. The spec is available at
https://maxmind.github.io/MaxMind-DB/. This spec is licensed under the
Creative Commons Attribution-ShareAlike 3.0 Unported License.

See https://dev.maxmind.com/ for more details about MaxMind's GeoIP2 products.

# License

This library is licensed under the Apache License, Version 2.

# Installation

## From a Named Release Tarball

**NOTE:** These instructions are for installation from the _named_ `.tar.gz`
tarballs on the [Releases](https://github.com/maxmind/libmaxminddb/releases)
page (e.g. `libmaxminddb-*.tar.gz`).

This code is known to work with GCC 4.4+ and clang 3.2+. It should also work
on other compilers that supports C99, POSIX.1-2001, and the `-fms-extensions
flag` (or equivalent). The latter is needed to allow an anonymous union in a
structure.

To install this code, run the following commands:

    $ ./configure
    $ make
    $ make check
    $ sudo make install
    $ sudo ldconfig

You can skip the `make check` step but it's always good to know that tests are
passing on your platform.

The `configure` script takes the standard options to set where files are
installed such as `--prefix`, etc. See `./configure --help` for details.

If after installing, you receive an error that `libmaxminddb.so.0` is missing
you may need to add the `lib` directory in your `prefix` to your library path.
On most Linux distributions when using the default prefix (`/usr/local`), you
can do this by running the following commands:

    $ sudo sh -c "echo /usr/local/lib  >> /etc/ld.so.conf.d/local.conf"
    $ ldconfig

## From a GitHub "Source Code" Archive / Git Repo Clone (Achtung!)

**NOTE:** These instructions are for installation from the GitHub "Source
Code" archives also available on the
[Releases](https://github.com/maxmind/libmaxminddb/releases) page (e.g.
`X.Y.Z.zip` or `X.Y.Z.tar.gz`), as well as installation directly from a clone
of the [Git repo](https://github.com/maxmind/libmaxminddb). Installation from
these sources are possible but will present challenges to users not
comfortable with manual dependency resolution.

You will need `automake`, `autoconf`, and `libtool` installed
in addition to `make` and a compiler.

You can clone this repository and build it by running:

    $ git clone --recursive https://github.com/maxmind/libmaxminddb

After cloning, run `./bootstrap` from the `libmaxminddb` directory and then
follow the instructions for installing from a named release tarball as
described above.

## Using CMake

We provide a CMake build script. This is primarily targeted at Windows users,
but it can be used in other circumstances where the Autotools script does not
work.
    
    $ mkdir build && cd build
    $ cmake ..
    $ cmake --build .
    $ ctest -V .
    $ cmake --build . --target install

When building with Visual Studio, you may build a multithreaded (MT/MTd)
runtime library, using the `MSVC_STATIC_RUNTIME` setting:

    $ cmake -DMSVC_STATIC_RUNTIME=ON -DBUILD_SHARED_LIBS=OFF ..

## On Ubuntu via PPA

MaxMind provides a PPA for recent version of Ubuntu. To add the PPA to your
APT sources, run:

    $ sudo add-apt-repository ppa:maxmind/ppa

Then install the packages by running:

    $ sudo apt update
    $ sudo apt install libmaxminddb0 libmaxminddb-dev mmdb-bin

## On macOS via Homebrew or MacPorts

You can install libmaxminddb on macOS using [Homebrew](https://brew.sh):

    $ brew install libmaxminddb

Or with [MacPorts](https://ports.macports.org/port/libmaxminddb):

    $ sudo port install libmaxminddb

# Bug Reports

Please report bugs by filing an issue with our GitHub issue tracker at
https://github.com/maxmind/libmaxminddb/issues

# Creating a Release Tarball

Use `make safedist` to check the resulting tarball.

# Copyright and License

Copyright 2013-2022 MaxMind, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
