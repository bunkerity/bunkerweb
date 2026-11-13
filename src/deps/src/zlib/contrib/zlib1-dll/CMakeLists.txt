cmake_minimum_required(VERSION 3.20...3.31)

project(
    zlib1-dll
    LANGUAGES C
    VERSION 1.4
    HOMEPAGE_URL "https://zlib.net/"
    DESCRIPTION "zlib1.dll is the legacy DLL with zlib and minizip")

# ============================================================================
# configuration
# ============================================================================

if(WIN32)
    set(CMAKE_DEBUG_POSTFIX "d")
else(WIN32)
    message(FATAL_ERROR "This creates zlib1.<DLL>, Nothing else")
endif(WIN32)

if(ZLIB_BUILD_ZLIB1_DLL)
    set(ZLIB1_DLL_BUILD_TESTING ${ZLIB_BUILD_TESTING} CACHE BOOL "")
    set(ZLIB1_DLL_ENABLE_BZIP2 ${MINIZIP_ENABLE_BZIP2} CACHE BOOL "")
    set(ZLIB1_DLL_INSTALL ${ZLIB_INSTALL} CACHE BOOL "")
    set(ZLIB1_DLL_PREFIX "${ZLIB_PREFIX}" CACHE STRING
    "prefix for all types and library functions, see zconf.h.in")
endif(ZLIB_BUILD_ZLIB1_DLL)

option(ZLIB1_DLL_ENABLE_BZIP2 "Build with bzip2 support" OFF)
option(ZLIB1_DLL_INSTALL "Install zlib1.dll" ON)
option(ZLIB1_DLL_BUILD_TESTING "Build and run tests for zlib1.dll" ON)
set(ZLIB1_DLL_PREFIX "" CACHE STRING
    "prefix for all types and library functions, see zconf.h.in")
set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

include(CheckCSourceCompiles)
include(CheckSymbolExists)
include(CheckIncludeFile)
include(CMakePackageConfigHelpers)
include(CheckTypeSize)
include(GNUInstallDirs)

if(NOT CPACK_INCLUDED)
    include(CPack)
endif(NOT CPACK_INCLUDED)

if(NOT ZLIB_CONF_WRITTEN)
    set(CONF_OUT_FILE ${zlib1-dll_BINARY_DIR}/zconf.h.cmakein)
    file(READ ../../zconf.h ZCONF_CONTENT LIMIT 245)
    file(WRITE ${CONF_OUT_FILE} ${ZCONF_CONTENT})
    file(APPEND ${CONF_OUT_FILE} "#cmakedefine Z_PREFIX @Z_PREFIX@\n")
    file(APPEND ${CONF_OUT_FILE} "#cmakedefine HAVE_STDARG_H 1\n")
    file(APPEND ${CONF_OUT_FILE} "#cmakedefine HAVE_UNISTD_H 1\n")
    file(READ ../../zconf.h ZCONF_CONTENT OFFSET 244)
    set(FIRST_ITEM TRUE)

    foreach(item IN LISTS ZCONF_CONTENT)
        if(FIRST_ITEM)
            string(APPEND OUT_CONTENT ${item})
            set(FIRST_ITEM FALSE)
        else(FIRST_ITEM)
            string(APPEND OUT_CONTENT "\;" ${item})
        endif(FIRST_ITEM)
    endforeach(item IN LISTS ${ZCONF_CONTENT})

    file(APPEND ${CONF_OUT_FILE} ${OUT_CONTENT})
    set(ZLIB_CONF_WRITTEN
        TRUE
        CACHE BOOL "zconf.h.cmakein was created")
    mark_as_advanced(ZLIB_CONF_WRITTEN)

    set(ZCONF_IN_ZLIB1 True CACHE INTERNAL "find zconf.h in zlib1-dll")
endif(NOT ZLIB_CONF_WRITTEN)

set(Z_PREFIX "${ZLIB1_DLL_PREFIX}")

if(ZLIB1_DLL_ENABLE_BZIP2)
    find_package(BZip2 REQUIRED)
endif(ZLIB1_DLL_ENABLE_BZIP2)

#
# Check for fopen64
#
check_symbol_exists(fopen64 stdio.h HAVE_FOPEN64)

#
# Check to see if we have large file support
#
set(CMAKE_REQUIRED_DEFINITIONS -D_LARGEFILE64_SOURCE=1)
check_type_size(off64_t OFF64_T)
unset(CMAKE_REQUIRED_DEFINITIONS) # clear variable

#
# Check for fseeko
#
check_symbol_exists(fseeko stdio.h HAVE_FSEEKO)

#
# Check for stdarg.h
#
check_include_file(stdarg.h HAVE_STDARG_H)

#
# Check for unistd.h
#
check_include_file(unistd.h HAVE_UNISTD_H)

#
# Check visibility attribute is supported
#
if(MSVC)
    set(CMAKE_REQUIRED_FLAGS "-WX")
else(MSVC)
    set(CMAKE_REQUIRED_FLAGS "-Werror")
endif(MSVC)

check_c_source_compiles(
    "
        #include <stdlib.h>
        static void f(void) __attribute__ ((visibility(\"hidden\")));
        int main(void) {return 0;}
    "
    HAVE___ATTR__VIS_HIDDEN)

unset(CMAKE_COMPILE_FLAGS)

if(ZCONF_IN_ZLIB1)
    configure_file(${zlib1-dll_BINARY_DIR}/zconf.h.cmakein
                   ${zlib1-dll_BINARY_DIR}/zconf.h)
    set(ZCONF_H "${zlib1-dll_BINARY_DIR}/zconf.h")
else(ZCONF_IN_ZLIB1)
    set(ZCONF_H "${zlib1-dll_BINARY_DIR}/../../zconf.h")
endif(ZCONF_IN_ZLIB1)

# ============================================================================
# zlib1-dll
# ============================================================================
set(ZLIB1-DLL_PUBLIC_HDRS
    ${ZCONF_H}
    ../../zlib.h
    ../minizip/crypt.h
    ../minizip/ints.h
    ../minizip/ioapi.h
    ../minizip/mztools.h
    ../minizip/unzip.h
    ../minizip/zip.h)

set(ZLIB1-DLL_PRIVATE_HDRS
    ../../crc32.h
    ../../deflate.h
    ../../gzguts.h
    ../../inffast.h
    ../../inffixed.h
    ../../inflate.h
    ../../inftrees.h
    ../../trees.h
    ../../zutil.h)

set(ZLIB1-DLL_SRCS
    ../../adler32.c
    ../../compress.c
    ../../crc32.c
    ../../deflate.c
    ../../gzclose.c
    ../../gzlib.c
    ../../gzread.c
    ../../gzwrite.c
    ../../inflate.c
    ../../infback.c
    ../../inftrees.c
    ../../inffast.c
    ../../trees.c
    ../../uncompr.c
    ../../zutil.c
    ../minizip/ioapi.c
    ../minizip/mztools.c
    ../minizip/unzip.c
    ../minizip/zip.c)

cmake_path(SET p1 "../../")
cmake_path(SET p2 "../../")
cmake_path(ABSOLUTE_PATH "p1" OUTPUT_VARIABLE DOTDOT)
cmake_path(ABSOLUTE_PATH "p2" OUTPUT_VARIABLE DOTMINIZIP)

add_library(${ZLIB_CONTRIB_PREFIX}zlib1 SHARED
    ${ZLIB1-DLL_SRCS}
    ${ZLIB1-DLL_PUBLIC_HDRS}
    ${ZLIB1-DLL_PRIVATE_HDRS}
    zlib1.rc)

add_library(ZLIB1DLL::ZLIB1DLL ALIAS ${ZLIB_CONTRIB_PREFIX}zlib1)

set_target_properties(${ZLIB_CONTRIB_PREFIX}zlib1
    PROPERTIES
        OUTPUT_NAME zlib1)

target_compile_definitions(${ZLIB_CONTRIB_PREFIX}zlib1
    PRIVATE ZLIB_BUILD
            $<$<BOOL:NOT:${HAVE_FSEEKO}>:NO_FSEEKO>
            $<$<BOOL:${HAVE_UNISTD_H}>:HAVE_UNISTD_H=1>
            $<$<BOOL:${HAVE___ATTR__VIS_HIDDEN}>:HAVE_HIDDEN>
            $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_DEPRECATE>
            $<$<BOOL:${MSVC}>:_CRT_NONSTDC_NO_DEPRECATE>
            $<$<BOOL:${ZLIB1_DLL_PREFIX}>:Z_PREFIX=${ZLIB1_DLL_PREFIX}>
    PUBLIC $<$<BOOL:${HAVE_OFF64_T}>:_LARGEFILE64_SOURCE=1>
           $<$<BOOL:${BZIP2_FOUND}>:HAVE_BZIP2=1>
           $<$<BOOL:NOT:${HAVE_FOPEN64}>:USE_FILE32API=1>)

target_include_directories(${ZLIB_CONTRIB_PREFIX}zlib1
    PUBLIC $<BUILD_INTERFACE:${DOTDOT}>
           $<BUILD_INTERFACE:${DOTMINIZIP}>
           $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
           $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

target_link_libraries(${ZLIB_CONTRIB_PREFIX}zlib1
    PUBLIC $<$<BOOL:${BZIP2_FOUND}>:BZip2::BZip2>)

set_target_properties(${ZLIB_CONTRIB_PREFIX}zlib1 PROPERTIES
    DEFINE_SYMBOL ZLIB_DLL
    EXPORT_NAME ZLIB1DLL)

add_library(${ZLIB_CONTRIB_PREFIX}zlibwapi SHARED
    ${ZLIB1-DLL_SRCS}
    ${ZLIB1-DLL_PUBLIC_HDRS}
    ${ZLIB1-DLL_PRIVATE_HDRS}
    zlibwapi.rc)

add_library(ZLIB1DLL::ZLIBWAPI ALIAS ${ZLIB_CONTRIB_PREFIX}zlibwapi)

set_target_properties(${ZLIB_CONTRIB_PREFIX}zlibwapi
    PROPERTIES
        OUTPUT_NAME zlibwapi)

target_include_directories(${ZLIB_CONTRIB_PREFIX}zlibwapi
    PUBLIC $<BUILD_INTERFACE:${DOTDOT}>
           $<BUILD_INTERFACE:${DOTMINIZIP}>
           $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
           $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

target_compile_definitions(${ZLIB_CONTRIB_PREFIX}zlibwapi
    PRIVATE ZLIB_BUILD
            $<$<BOOL:NOT:${HAVE_FSEEKO}>:NO_FSEEKO>
            $<$<BOOL:${HAVE_UNISTD_H}>:HAVE_UNISTD_H=1>
            $<$<BOOL:${HAVE___ATTR__VIS_HIDDEN}>:HAVE_HIDDEN>
            $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_DEPRECATE>
            $<$<BOOL:${MSVC}>:_CRT_NONSTDC_NO_DEPRECATE>
    PUBLIC $<$<BOOL:${HAVE_OFF64_T}>:_LARGEFILE64_SOURCE=1>
           $<$<BOOL:${BZIP2_FOUND}>:HAVE_BZIP2=1>
           $<$<BOOL:NOT:${HAVE_FOPEN64}>:USE_FILE32API=1>
           ZLIB_WINAPI)

target_link_libraries(${ZLIB_CONTRIB_PREFIX}zlibwapi
    PUBLIC $<$<BOOL:${BZIP2_FOUND}>:BZip2::BZip2>)

if(NOT CYGWIN)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}zlib1
        PROPERTIES
            SOVERSION ${zlib1-dll_VERSION_MAJOR}
            VERSION ${zlib1-dll_VERSION})
    set_target_properties(${ZLIB_CONTRIB_PREFIX}zlibwapi
        PROPERTIES
            SOVERSION ${zlib1-dll_VERSION_MAJOR}
            VERSION ${zlib1-dll_VERSION})
endif(NOT CYGWIN)

set_target_properties(${ZLIB_CONTRIB_PREFIX}zlibwapi PROPERTIES
    DEFINE_SYMBOL ZLIB_DLL
    EXPORT_NAME ZLIBWAPI)

if(ZLIB1_DLL_INSTALL)
    install(
        TARGETS ${ZLIB_CONTRIB_PREFIX}zlib1 ${ZLIB_CONTRIB_PREFIX}zlibwapi
        COMPONENT Runtime
        EXPORT zlibDllExport
        ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
        RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
        LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}")

    install(
        EXPORT zlibDllExport
        FILE ZLIB1DLLTargets.cmake
        NAMESPACE ZLIB1DLL::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/zlib1dll)

    install(
        FILES $<TARGET_PDB_FILE:${ZLIB_CONTRIB_PREFIX}zlib1>
              $<TARGET_PDB_FILE:${ZLIB_CONTRIB_PREFIX}zlibwapi>
        COMPONENT Runtime
        DESTINATION ${CMAKE_INSTALL_BINDIR}
        CONFIGURATIONS Debug OR RelWithDebInfo
        OPTIONAL)

    configure_package_config_file(
        ${zlib1-dll_SOURCE_DIR}/zlib1dllConfig.cmake.in
        ${zlib1-dll_BINARY_DIR}/ZLIB1DLLConfig.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/zlib)

    write_basic_package_version_file(
        "${zlib1-dll_BINARY_DIR}/ZLIB1DLLConfigVersion.cmake"
        VERSION "${zlib1-dll_VERSION}"
        COMPATIBILITY AnyNewerVersion)

    install(FILES ${zlib1-dll_BINARY_DIR}/ZLIB1DLLConfig.cmake
                  ${zlib1-dll_BINARY_DIR}/ZLIB1DLLConfigVersion.cmake
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/zlib1dll)

    install(
        FILES ${ZLIB1-DLL_PUBLIC_HDRS}
        DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")

    install(
        FILES ../../LICENSE
        DESTINATION "${CMAKE_INSTALL_DOCDIR}/zlib1-dll")
endif(ZLIB1_DLL_INSTALL)

if(ZLIB1_DLL_BUILD_TESTING)
    enable_testing()
    add_subdirectory(test)
endif(ZLIB1_DLL_BUILD_TESTING)
