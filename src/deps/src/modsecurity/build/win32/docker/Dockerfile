# escape=`

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

# download & install GIT
ARG GIT_VERSION=2.44.0
ARG GIT_BINARY=Git-${GIT_VERSION}-64-bit.exe
ARG GIT_URL=https://github.com/git-for-windows/git/releases/download/v${GIT_VERSION}.windows.1/${GIT_BINARY}

COPY git.inf C:\TEMP\
ARG INSTALLER=C:\TEMP\${GIT_BINARY}
ADD ${GIT_URL} ${INSTALLER}
RUN %INSTALLER% /SP- /VERYSILENT /SUPPRESSMSGBOXES /NOCANCEL `
    /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /LOADINF=git.inf

# download & setup conan
ARG CONAN_VERSION=2.10.2
ARG CONAN_BINARY=conan-${CONAN_VERSION}-windows-x86_64-installer.exe
ARG CONAN_URL=https://github.com/conan-io/conan/releases/download/${CONAN_VERSION}/${CONAN_BINARY}

ARG INSTALLER=C:\TEMP\${CONAN_BINARY}
ADD ${CONAN_URL} ${INSTALLER}
RUN %INSTALLER% /SP- /VERYSILENT /SUPPRESSMSGBOXES

# setup conan profile
RUN C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat && conan profile detect --force

# download libModSecurity
#

# create src dir
ARG SRC_DIR=C:\src

WORKDIR C:\
RUN cmd.exe /C md %SRC_DIR%

# libModSecurity
WORKDIR ${SRC_DIR}

ARG MOD_SECURITY_TAG=v3/master
RUN git clone -c advice.detachedHead=false --depth 1 --branch %MOD_SECURITY_TAG% https://github.com/owasp-modsecurity/ModSecurity.git

ARG MOD_SECURITY_DIR=${SRC_DIR}\ModSecurity
WORKDIR ${MOD_SECURITY_DIR}

# fetch submodules (bindings/python, others/libinjection, test/test-cases/secrules-language-tests)
RUN git submodule init
RUN git submodule update

# build libraries
#

ARG BUILD_TYPE=Release
ARG ARCH=x86_64
ARG USE_ASAN=

RUN C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat && vcbuild.bat %BUILD_TYPE% %ARCH% %USE_ASAN%

# test suite
#

# setup test environment
RUN cmd.exe /C md \tmp
RUN cmd.exe /C md \bin
RUN cmd.exe /C copy "C:\Program Files\GIT\usr\bin" \bin > NUL
RUN cmd.exe /C copy "C:\Program Files\GIT\usr\bin\echo.exe" \bin\echo > NUL

# disable tests that don't work on windows
ARG JQ_VERSION=1.7.1
ARG JQ_BINARY=jq-windows-amd64.exe
ARG JQ_URL=https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/${JQ_BINARY}

ARG JQ_BIN=C:\TEMP\jq.exe
ADD ${JQ_URL} ${JQ_BIN}

WORKDIR ${MOD_SECURITY_DIR}\test\test-cases\regression

RUN %JQ_BIN% "map(if .title == \"Test match variable (1/n)\" then .enabled = 0 else . end)" issue-2423-msg-in-chain.json > tmp.json && move /Y tmp.json issue-2423-msg-in-chain.json
RUN %JQ_BIN% "map(if .title == \"Test match variable (2/n)\" then .enabled = 0 else . end)" issue-2423-msg-in-chain.json > tmp.json && move /Y tmp.json issue-2423-msg-in-chain.json
RUN %JQ_BIN% "map(if .title == \"Test match variable (3/n)\" then .enabled = 0 else . end)" issue-2423-msg-in-chain.json > tmp.json && move /Y tmp.json issue-2423-msg-in-chain.json
RUN %JQ_BIN% "map(if .title == \"Variable offset - FILES_NAMES\" then .enabled = 0 else . end)" offset-variable.json > tmp.json && move /Y tmp.json offset-variable.json

# run tests
WORKDIR ${MOD_SECURITY_DIR}\build\win32\build

RUN C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat && ctest -C %BUILD_TYPE% --output-on-failure

# setup container's entrypoint
#

WORKDIR C:\

# Use developer command prompt and start PowerShell if no other command specified.
ENTRYPOINT ["C:\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat", "&&", "powershell.exe", "-NoLogo", "-ExecutionPolicy", "Bypass"]
