# escape=`

# References
#
#  * Building nginx on the Win32 platform with Visual C
#    * https://nginx.org/en/docs/howto_build_on_win32.html
#  * libModSecurity Windows build information
#    * https://github.com/eduar-hte/ModSecurity/blob/windows-port/build/win32/README.md
#  * ModSecurity-nginx - Compilation
#    * https://github.com/owasp-modsecurity/ModSecurity-nginx#compilation

ARG FROM_IMAGE=mcr.microsoft.com/windows/servercore:ltsc2022
FROM ${FROM_IMAGE}

# reset the shell.
SHELL ["cmd", "/S", "/C"]

# set up environment to collect install errors.
COPY InstallBuildTools.cmd C:\TEMP\
ADD https://aka.ms/vscollect.exe C:\TEMP\collect.exe

# download channel for fixed install.
ARG CHANNEL_URL=https://aka.ms/vs/17/release/channel
ADD ${CHANNEL_URL} C:\TEMP\VisualStudio.chman

# download and install Build Tools for Visual Studio 2022 for native desktop workload.
ADD https://aka.ms/vs/17/release/vs_buildtools.exe C:\TEMP\vs_buildtools.exe
RUN C:\TEMP\InstallBuildTools.cmd C:\TEMP\vs_buildtools.exe --quiet --wait --norestart --nocache `
    --channelUri C:\TEMP\VisualStudio.chman `
    --installChannelUri C:\TEMP\VisualStudio.chman `
    --add Microsoft.VisualStudio.Workload.VCTools  `
    --includeRecommended `
    --installPath C:\BuildTools

# download & install git
ARG GIT_VERSION=2.44.0
ARG GIT_BINARY=Git-${GIT_VERSION}-64-bit.exe
ARG GIT_URL=https://github.com/git-for-windows/git/releases/download/v${GIT_VERSION}.windows.1/${GIT_BINARY}

COPY git.inf C:\TEMP\
ARG INSTALLER=C:\TEMP\${GIT_BINARY}
ADD ${GIT_URL} ${INSTALLER}
RUN %INSTALLER% /SP- /VERYSILENT /SUPPRESSMSGBOXES /NOCANCEL `
    /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /LOADINF=git.inf

# download & setup conan (for libModSecurity build)
ARG CONAN_VERSION=2.2.2
ARG CONAN_BINARY=conan-${CONAN_VERSION}-windows-x86_64-installer.exe
ARG CONAN_URL=https://github.com/conan-io/conan/releases/download/${CONAN_VERSION}/${CONAN_BINARY}

ARG INSTALLER=C:\TEMP\${CONAN_BINARY}
ADD ${CONAN_URL} ${INSTALLER}
RUN %INSTALLER% /SP- /VERYSILENT /SUPPRESSMSGBOXES

# setup conan profile
RUN C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat && conan profile detect --force

# download & setup Strawberry Perl (nginx requires a native Windows perl version to build)
ARG PERL_VERSION=5.38.2.2
ARG PERL_BINARY=strawberry-perl-${PERL_VERSION}-64bit.msi
ARG PERL_URL=https://github.com/StrawberryPerl/Perl-Dist-Strawberry/releases/download/SP_53822_64bit/${PERL_BINARY}

ARG INSTALLER=C:\TEMP\${PERL_BINARY}
ADD ${PERL_URL} ${INSTALLER}
RUN msiexec /i %INSTALLER% /quiet /qn /norestart

# msys2 (to build nginx)
#
# References
#
#  * Using MSYS2 in CI
#    * https://www.msys2.org/docs/ci/

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

RUN [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; `
  Invoke-WebRequest -UseBasicParsing -uri "https://github.com/msys2/msys2-installer/releases/download/nightly-x86_64/msys2-base-x86_64-latest.sfx.exe" -OutFile msys2.exe; `
  .\msys2.exe -y -oC:\; `
  Remove-Item msys2.exe ; `
  function msys() { C:\msys64\usr\bin\bash.exe @('-lc') + @Args; } `
  msys ' '; `
  msys 'pacman --noconfirm -Syuu'; `
  msys 'pacman --noconfirm -Syuu'; `
  msys 'pacman --noconfirm -Scc';

# revert back to the default shell (cmd.exe)
SHELL ["cmd", "/S", "/C"]

# create src dir
ARG SRC_DIR=C:\src

WORKDIR C:\
RUN cmd.exe /C md %SRC_DIR%

WORKDIR ${SRC_DIR}

# nginx
#

RUN git clone -c advice.detachedHead=false --depth 1 https://github.com/nginx/nginx.git

ARG NGINX_DIR=${SRC_DIR}\nginx
WORKDIR ${NGINX_DIR}

# nginx/tests
RUN git clone -c advice.detachedHead=false --depth 1 https://github.com/nginx/nginx-tests.git test

ARG NGINX_LIBS_DIR=${NGINX_DIR}\objs\lib

# libModSecurity
#

WORKDIR ${NGINX_LIBS_DIR}

ARG MOD_SECURITY_TAG=v3/master
RUN git clone -c advice.detachedHead=false --depth 1 https://github.com/owasp-modsecurity/ModSecurity.git

ARG MOD_SECURITY_DIR=${NGINX_LIBS_DIR}\ModSecurity
WORKDIR ${MOD_SECURITY_DIR}

# fetch submodules (bindings/python, others/libinjection, test/test-cases/secrules-language-tests)
RUN git submodule init
RUN git submodule update

# build
RUN C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat && vcbuild.bat

RUN cmd.exe /C copy build\win32\build\Release\libModSecurity.dll ..\..

# ModSecurity-nginx
#

WORKDIR ${NGINX_LIBS_DIR}

ARG MOD_SECURITY_NGINX_TAG=master
RUN git clone -c advice.detachedHead=false --depth 1 --branch %MOD_SECURITY_NGINX_TAG% https://github.com/owasp-modsecurity/ModSecurity-nginx.git

RUN cmd.exe /C copy ModSecurity-nginx\tests\*.* ..\..\test

# nginx w/ModSecurity-nginx
#

WORKDIR ${NGINX_DIR}

COPY build-nginx.sh ${NGINX_DIR}
COPY build-nginx-bootstrap.bat ${NGINX_DIR}

RUN cmd.exe /C build-nginx-bootstrap.bat

# execute ModSecurity-nginx tests
WORKDIR ${NGINX_DIR}\test

RUN set TEST_NGINX_BINARY=..\objs\nginx.exe && prove modsecurity*.t

# setup container's entrypoint
#

WORKDIR ${NGINX_DIR}

# Use developer command prompt and start PowerShell if no other command specified.
ENTRYPOINT ["C:\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat", "&&", "powershell.exe", "-NoLogo", "-ExecutionPolicy", "Bypass"]
