@echo off
rem Bootstrap to setup MSVC compiler environment and inherit it into bash
call "C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
set MSYSTEM=UCRT64
set MSYS2_PATH_TYPE=inherit
C:\msys64\usr\bin\bash.exe -lc 'cd /c/src/nginx ; ./build-nginx.sh'
