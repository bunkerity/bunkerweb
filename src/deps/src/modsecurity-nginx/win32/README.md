# ModSecurity-nginx Windows build information <!-- omit from toc -->

## Contents <!-- omit from toc -->

- [References](#references)
- [Prerequisites](#prerequisites)
- [Build](#build)
  - [Docker container](#docker-container)
- [Tests](#tests)
- [Miscellaneous](#miscellaneous)

## References

 * [Building nginx on the Win32 platform with Visual C](https://nginx.org/en/docs/howto_build_on_win32.html)
 * [libModSecurity Windows build information](https://github.com/owasp-modsecurity/ModSecurity/blob/v3/master/build/win32/README.md)
 * [ModSecurity-nginx - Compilation](https://github.com/owasp-modsecurity/ModSecurity-nginx#compilation)

## Prerequisites

 * [Build Tools for Visual Studio 2022](https://aka.ms/vs/17/release/vs_buildtools.exe)
   * Install *Desktop development with C++* workload, which includes:
     * MSVC C++ compiler
     * Windows SDK
     * CMake
   * NOTE: The build steps assume this has been installed in `C:\BuildTools`.
 * [MSYS2](https://www.msys2.org/)
   * For nginx build on Windows
   * NOTE: The build steps assume this has been installed in `C:\msys64`.
 * [Conan package manager 2.2.2](https://github.com/conan-io/conan/releases/download/2.2.2/conan-2.2.2-windows-x86_64-installer.exe)
   * Required to build libModSecurity v3 on Windows.
   * Install and then setup the default Conan profile to use the MSVC C++ compiler:
     1. Open a command-prompt and set the MSVC C++ compiler environment by executing: `C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat`
     2. Execute: `conan profile detect --force`
 * [Git for Windows 2.44.0](https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe)
 * [Strawberry Perl for Windows](https://strawberryperl.com/)
   * nginx build on Windows requires a native Perl build. The one included in MSYS2 triggers the following error:
        ```
        This perl implementation doesn't produce Windows like paths (with backward slash directory separators).  Please use an implementation that matches your building platform.
        ```
   * NOTE: The build steps assume this has been installed in `C:\Strawberry\perl`.

## Build

 1. Open a command prompt
 2. Set up MSVC C++ compiler environment by executing:
    ```shell
    C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat
    ```
 3. From this command prompt, launch a `MSYS2 UCRT64 Shell` (to inherit MSVC C++ compiler environment)
    ```shell
    c:\msys64\ucrt64.exe
    ```
 4. Checkout nginx source code
    ```shell
    git clone -c advice.detachedHead=false --depth 1 https://github.com/nginx/nginx.git
    cd nginx
    ```
 5. Download third-party libraries
    ```shell
    mkdir objs
    mkdir objs/lib
    cd objs/lib

    echo Downloading PCRE2
    wget -q -O - https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.39/pcre2-10.39.tar.gz | tar -xzf -

    echo Downloading zlib
    wget -q -O - https://www.zlib.net/fossils/zlib-1.3.tar.gz | tar -xzf -

    echo Downloading OpenSSL
    wget -q -O - https://www.openssl.org/source/openssl-3.0.13.tar.gz | tar -xzf -
    ```
 6. Checkout and build libModSecurity v3
    * For more information on libModSecurity v3 build options, see [libModSecurity Windows build information](https://github.com/owasp-modsecurity/ModSecurity/blob/v3/master/build/win32/README.md).
    ```shell
    git clone -c advice.detachedHead=false --depth 1 https://github.com/owasp-modsecurity/ModSecurity.git

    cd ModSecurity

    git submodule init
    git submodule update

    vcbuild.bat

    cd ..
    ```
 7. Checkout ModSecurity-nginx
    ```shell
    git clone -c advice.detachedHead=false --depth 1 https://github.com/owasp-modsecurity/ModSecurity-nginx.git

    cd ../..
    ```
 8. Setup environment variables for nginx build
    ```shell
    # remove (or move) /usr/bin/link conflicting with MSVC link.exe
    rm /usr/bin/link

    # nginx build on windows requires a native perl build (see prerequisites)
    export PATH=/c/Strawberry/perl/bin:$PATH
    # avoid perl 'Setting locale failed.' warnings
    export LC_ALL=C

    # provide location of libModsecurity headers & libraries for
    # the ModSecurity-nginx module build
    export MODSECURITY_INC=objs/lib/ModSecurity/headers
    export MODSECURITY_LIB=objs/lib/ModSecurity/build/win32/build/Release
    ```
 9. Configure nginx build
    ```shell
    auto/configure \
        --with-cc=cl \
        --with-debug \
        --prefix= \
        --conf-path=conf/nginx.conf \
        --pid-path=logs/nginx.pid \
        --http-log-path=logs/access.log \
        --error-log-path=logs/error.log \
        --sbin-path=nginx.exe \
        --http-client-body-temp-path=temp/client_body_temp \
        --http-proxy-temp-path=temp/proxy_temp \
        --http-fastcgi-temp-path=temp/fastcgi_temp \
        --http-scgi-temp-path=temp/scgi_temp \
        --http-uwsgi-temp-path=temp/uwsgi_temp \
        --with-cc-opt=-DFD_SETSIZE=1024 \
        --with-pcre=objs/lib/pcre2-10.39 \
        --with-zlib=objs/lib/zlib-1.3 \
        --with-openssl=objs/lib/openssl-3.0.13 \
        --with-openssl-opt=no-asm \
        --with-http_ssl_module \
        --with-http_v2_module \
        --with-http_auth_request_module \
        --add-module=objs/lib/ModSecurity-nginx
    ```
 10. Build nginx
        ```shell
        nmake
        ```

### Docker container

A `Dockerfile` configuration file is provided in the `docker` subdir that creates a Windows container image which installs the [prerequisites](#prerequisites) and builds libModSecurity v3 and nginx w/ModSecurity-nginx.

NOTE: Windows containers are supported in Docker Desktop for Windows, using the *Switch to Windows containers...* option on the context menu of the system tray icon.

To build the docker image, execute the following command (from the `win32\docker` directory):

 * `docker build -t modsecurity_nginx:latest -m 4GB .`

Once the image is generated, the built binaries are located in the `C:\src\nginx\objs` directory.

To extract the built binaries from the image, you can execute the following commands:

 * `docker container create --name [container_name] modsecurity_nginx`
 * `docker cp [container_name]:C:\src\nginx\objs\nginx.exe .`
 * `docker cp [container_name]:C:\src\nginx\objs\libModSecurity.dll .`

Additionally, the image can be used interactively for additional development work by executing:

 * `docker run -it modsecurity_nginx`

## Tests

In order to validate the nginx w/ModSecurity-nginx binary it's recommended that you set up and run ModSecurity-nginx tests following these steps:

 1. Open a command prompt and go to the directory where `nginx` was built.
 2. Clone nginx-tests
    ```shell
    git clone -c advice.detachedHead=false --depth 1 https://github.com/nginx/nginx-tests.git test
    ```
 3. Copy `libModSecurity.dll` to the directory where `nginx.exe` is located.
    ```shell
    cd objs
    copy objs\lib\ModSecurity\build\win32\Release\build\libModSecurity.dll
    ```
 4. Copy ModSecurity-nginx tests to the nginx tests directory.
    ```shell
    cd ..\test
    copy ..\objs\lib\ModSecurity-nginx\tests\*.*
    ```
 5. Run ModSecurity-nginx tests
    ```shell
    set TEST_NGINX_BINARY=..\objs\nginx.exe
    prove modsecurity*.t
    ```

NOTES

 * `TEST_NGINX_BINARY` requires path with backslashes. nginx won't work with path with slashes.
 * The tests generate nginx configuration and associated files (such as log files) on the temp directory indicated by the `TEMP` environment variable. nginx won't work if the path contains spaces or short path names with the `~`  character. You may need to set the `TEMP` environment variable to a path that respects these limitations (such as `C:\TEMP`).

## Miscellaneous

The ModSecurity-nginx connector is built as a static nginx module. It looks as if there's currently no support for dynamic modules on nginx for Windows using MSVC.

It may be possible to cross-compile for Windows using gcc/clang, which may enable building using dynamic modules too.