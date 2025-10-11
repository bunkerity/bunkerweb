@rem Script to build LuaJIT with MSVC.
@rem Copyright (C) 2005-2025 Mike Pall. See Copyright Notice in luajit.h
@rem
@rem Open a "Visual Studio Command Prompt" (either x86 or x64).
@rem Then cd to this directory and run this script. Use the following
@rem options (in order), if needed. The default is a dynamic release build.
@rem
@rem   nogc64        disable LJ_GC64 mode for x64
@rem   debug         emit debug symbols
@rem   lua52compat   enable extra Lua 5.2 extensions
@rem   amalg         amalgamated build
@rem   static        create static lib to statically link into your project
@rem   mixed         create static lib to build a DLL in your project

@if not defined INCLUDE goto :FAIL

@setlocal
@rem Add more debug flags here, e.g. DEBUGCFLAGS=/DLUA_USE_ASSERT
@set DEBUGCFLAGS=
@set LJCOMPILE=cl /nologo /c /O2 /W3 /D_CRT_SECURE_NO_DEPRECATE /D_CRT_STDIO_INLINE=__declspec(dllexport)__inline
@set LJDYNBUILD=/DLUA_BUILD_AS_DLL /MD
@set LJDYNBUILD_DEBUG=/DLUA_BUILD_AS_DLL /MDd 
@set LJCOMPILETARGET=/Zi
@set LJLINKTYPE=/DEBUG /RELEASE
@set LJLINKTYPE_DEBUG=/DEBUG
@set LJLINKTARGET=/OPT:REF /OPT:ICF /INCREMENTAL:NO
@set LJLINK=link /nologo
@set LJMT=mt /nologo
@set LJLIB=lib /nologo /nodefaultlib
@set DASMDIR=..\dynasm
@set DASM=%DASMDIR%\dynasm.lua
@set DASC=vm_x64.dasc
@set LJDLLNAME=lua51.dll
@set LJLIBNAME=lua51.lib
@set ALL_LIB=lib_base.c lib_math.c lib_bit.c lib_string.c lib_table.c lib_io.c lib_os.c lib_package.c lib_debug.c lib_jit.c lib_ffi.c lib_buffer.c

@setlocal
@call :SETHOSTVARS
%LJCOMPILE% host\minilua.c
@if errorlevel 1 goto :BAD
%LJLINK% /out:minilua.exe minilua.obj
@if errorlevel 1 goto :BAD
if exist minilua.exe.manifest^
  %LJMT% -manifest minilua.exe.manifest -outputresource:minilua.exe
@endlocal

@set DASMFLAGS=-D WIN -D JIT -D FFI -D ENDIAN_LE -D FPU -D P64
@set LJARCH=x64
@minilua
@if errorlevel 8 goto :NO32
@set DASC=vm_x86.dasc
@set DASMFLAGS=-D WIN -D JIT -D FFI -D ENDIAN_LE -D FPU
@set LJARCH=x86
@set LJCOMPILE=%LJCOMPILE% /arch:SSE2
@goto :DA
:NO32
@if "%VSCMD_ARG_TGT_ARCH%" neq "arm64" goto :X64
@set DASC=vm_arm64.dasc
@set DASMTARGET=-D LUAJIT_TARGET=LUAJIT_ARCH_ARM64
@set LJARCH=arm64
@goto :DA
:X64
@if "%1" neq "nogc64" goto :DA
@shift
@set DASC=vm_x86.dasc
@set LJCOMPILE=%LJCOMPILE% /DLUAJIT_DISABLE_GC64
:DA
minilua %DASM% -LN %DASMFLAGS% -o host\buildvm_arch.h %DASC%
@if errorlevel 1 goto :BAD

if exist ..\.git ( git show -s --format=%%ct >luajit_relver.txt ) else ( type ..\.relver >luajit_relver.txt )
minilua host\genversion.lua

@setlocal
@call :SETHOSTVARS
%LJCOMPILE% /I "." /I %DASMDIR% %DASMTARGET% host\buildvm*.c
@if errorlevel 1 goto :BAD
%LJLINK% /out:buildvm.exe buildvm*.obj
@if errorlevel 1 goto :BAD
if exist buildvm.exe.manifest^
  %LJMT% -manifest buildvm.exe.manifest -outputresource:buildvm.exe
@endlocal

buildvm -m peobj -o lj_vm.obj
@if errorlevel 1 goto :BAD
buildvm -m bcdef -o lj_bcdef.h %ALL_LIB%
@if errorlevel 1 goto :BAD
buildvm -m ffdef -o lj_ffdef.h %ALL_LIB%
@if errorlevel 1 goto :BAD
buildvm -m libdef -o lj_libdef.h %ALL_LIB%
@if errorlevel 1 goto :BAD
buildvm -m recdef -o lj_recdef.h %ALL_LIB%
@if errorlevel 1 goto :BAD
buildvm -m vmdef -o jit\vmdef.lua %ALL_LIB%
@if errorlevel 1 goto :BAD
buildvm -m folddef -o lj_folddef.h lj_opt_fold.c
@if errorlevel 1 goto :BAD

@if "%1" neq "debug" goto :NODEBUG
@shift
@set LJCOMPILE=%LJCOMPILE% %DEBUGCFLAGS%
@set LJDYNBUILD=%LJDYNBUILD_DEBUG%
@set LJLINKTYPE=%LJLINKTYPE_DEBUG%
:NODEBUG
@if "%1" neq "lua52compat" goto :NOLUA52COMPAT
@shift
@set LJCOMPILE=%LJCOMPILE% /DLUAJIT_ENABLE_LUA52COMPAT
:NOLUA52COMPAT
@set LJCOMPILE=%LJCOMPILE% %LJCOMPILETARGET%
@set LJLINK=%LJLINK% %LJLINKTYPE% %LJLINKTARGET%
@if "%1"=="amalg" goto :AMALGDLL
@if "%1"=="static" goto :STATIC
%LJCOMPILE% %LJDYNBUILD% lj_*.c lib_*.c
@if errorlevel 1 goto :BAD
@if "%1"=="mixed" goto :STATICLIB
%LJLINK% /DLL /OUT:%LJDLLNAME% lj_*.obj lib_*.obj
@if errorlevel 1 goto :BAD
@goto :MTDLL
:STATIC
%LJCOMPILE% lj_*.c lib_*.c
@if errorlevel 1 goto :BAD
:STATICLIB
%LJLIB% /OUT:%LJLIBNAME% lj_*.obj lib_*.obj
@if errorlevel 1 goto :BAD
@goto :MTDLL
:AMALGDLL
@if "%2"=="static" goto :AMALGSTATIC
%LJCOMPILE% %LJDYNBUILD% ljamalg.c
@if errorlevel 1 goto :BAD
@if "%2"=="mixed" goto :AMALGSTATICLIB
%LJLINK% /DLL /OUT:%LJDLLNAME% ljamalg.obj lj_vm.obj
@if errorlevel 1 goto :BAD
@goto :MTDLL
:AMALGSTATIC
%LJCOMPILE% ljamalg.c
@if errorlevel 1 goto :BAD
:AMALGSTATICLIB
%LJLIB% /OUT:%LJLIBNAME% ljamalg.obj lj_vm.obj
@if errorlevel 1 goto :BAD
:MTDLL
if exist %LJDLLNAME%.manifest^
  %LJMT% -manifest %LJDLLNAME%.manifest -outputresource:%LJDLLNAME%;2

%LJCOMPILE% luajit.c
@if errorlevel 1 goto :BAD
%LJLINK% /OUT:luajit.exe luajit.obj %LJLIBNAME%
@if errorlevel 1 goto :BAD
if exist luajit.exe.manifest^
  %LJMT% -manifest luajit.exe.manifest -outputresource:luajit.exe

@del *.obj *.manifest minilua.exe buildvm.exe
@del host\buildvm_arch.h
@del lj_bcdef.h lj_ffdef.h lj_libdef.h lj_recdef.h lj_folddef.h
@echo.
@echo === Successfully built LuaJIT for Windows/%LJARCH% ===

@goto :END
:SETHOSTVARS
@if "%VSCMD_ARG_HOST_ARCH%_%VSCMD_ARG_TGT_ARCH%" equ "x64_arm64" (
  call "%VSINSTALLDIR%Common7\Tools\VsDevCmd.bat" -arch=%VSCMD_ARG_HOST_ARCH% -no_logo
  echo on
)
@goto :END
:BAD
@echo.
@echo *******************************************************
@echo *** Build FAILED -- Please check the error messages ***
@echo *******************************************************
@goto :END
:FAIL
@echo You must open a "Visual Studio Command Prompt" to run this script
:END
