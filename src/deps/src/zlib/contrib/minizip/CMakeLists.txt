cmake_minimum_required(VERSION 3.15...3.31)

project(
    minizip
    VERSION 1.0.0
    LANGUAGES C
    DESCRIPTION "A library for creating zipfiles based in zlib"
    HOMEPAGE_URL "https://www.winimage.com/zLibDll/minizip.html")

# ============================================================================
# CPack
# ============================================================================
set(CPACK_PACKAGE_VENDOR "zlib-Project")
set(CPACK_PACKAGE_DESCRIPTION_FILE ${minizip_SOURCE_DIR}/MiniZip64_info.txt)
set(CPACK_RESOURCE_FILE_LICENSE ${minizip_SOURCE_DIR}/../../LICENSE)
set(CPACK_RESOURCE_FILE_README ${minizip_SOURCE_DIR}/MiniZip64_info.txt)

# ============================================================================
# set options if build from zlib
# ============================================================================
if(ZLIB_BUILD_MINIZIP)
    set(MINIZIP_BUILD_SHARED ${ZLIB_MINIZIP_BUILD_SHARED} CACHE BOOL "")
    set(MINIZIP_BUILD_STATIC ${ZLIB_MINIZIP_BUILD_STATIC} CACHE BOOL "")
    set(MINIZIP_BUILD_TESTING ${ZLIB_MINIZIP_BUILD_TESTING} CACHE BOOL "")
    set(MINIZIP_INSTALL ${ZLIB_MINIZIP_INSTALL} CACHE BOOL "")
endif(ZLIB_BUILD_MINIZIP)

# ============================================================================
# configuration
# ============================================================================
option(MINIZIP_BUILD_SHARED "Enable building minizip shared library" ON)
option(MINIZIP_BUILD_STATIC "Enable building minizip static library" ON)
option(MINIZIP_BUILD_TESTING "Enable testing of minizip" ON)
option(MINIZIP_ENABLE_BZIP2 "Build minizip with bzip2 support" OFF)
option(MINIZIP_INSTALL "Enable installation of minizip" ON)

include(CheckCSourceCompiles)
include(CheckSymbolExists)
include(CheckIncludeFile)
include(CMakePackageConfigHelpers)
include(CheckTypeSize)
include(GNUInstallDirs)

if(NOT CPACK_INCLUDED)
    include(CPack)
endif(NOT CPACK_INCLUDED)

if(NOT DEFINED ZLIB_BUILD_MINIZIP)
    if(MINIZIP_BUILD_SHARED)
        list(APPEND REQUIRED_COMPONENTS "shared")
    endif(MINIZIP_BUILD_SHARED)

    if(MINIZIP_BUILD_STATIC)
        list(APPEND REQUIRED_COMPONENTS "static")
    endif(MINIZIP_BUILD_STATIC)

    find_package(ZLIB REQUIRED COMPONENTS ${REQUIRED_COMPONENTS} CONFIG)
endif(NOT DEFINED ZLIB_BUILD_MINIZIP)

if(MINIZIP_ENABLE_BZIP2)
    find_package(BZip2 REQUIRED)
endif(MINIZIP_ENABLE_BZIP2)

#
# Check for fopen64
#
check_symbol_exists(fopen64 stdio.h HAVE_FOPEN64)

#
# Check for fseeko
#
check_symbol_exists(fseeko stdio.h HAVE_FSEEKO)

#
# Check for unistd.h
#
check_include_file(unistd.h HAVE_UNISTD_H)

#
# Check to see if we have large file support
#
set(CMAKE_REQUIRED_DEFINITIONS -D_LARGEFILE64_SOURCE=1)
check_type_size(off64_t OFF64_T)
unset(CMAKE_REQUIRED_DEFINITIONS) # clear variable

#
# Check visibility attribute is supported
#
if(MSVC)
    set(CMAKE_REQUIRED_FLAGS "-WX")
else(MSVC)
    set(CMAKE_REQUIRED_FLAGS "-WError")
endif(MSVC)

check_c_source_compiles(
    "
        #include <stdlib.h>
        static void f(void) __attribute__ ((visibility(\"hidden\")));
        int main(void) {return 0;}
    "
    HAVE___ATTR__VIS_HIDDEN)

unset(CMAKE_REQUIRED_FLAGS)

set(LIBMINIZIP_SRCS
    ioapi.c
    mztools.c
    unzip.c
    zip.c
    $<$<BOOL:${WIN32}>:iowin32.c>)

set(LIBMINIZIP_HDRS
    crypt.h
    ints.h
    ioapi.h
    mztools.h
    unzip.h
    zip.h
    $<$<BOOL:${WIN32}>:${minizip_SOURCE_DIR}/iowin32.h>)

set(MINIZIP_SRCS
    ioapi.c
    minizip.c
    zip.c)

set(MINIZIP_HDRS
    crypt.h
    ints.h
    ioapi.h
    skipset.h
    zip.h)

set(MINIUNZIP_SRCS
    ioapi.c
    miniunz.c
    unzip.c
    zip.c)

set(MINIUNZIP_HDRS
    crypt.h
    ints.h
    ioapi.h
    skipset.h
    unzip.h
    zip.h)

set(LIBMINIZIP_PC ${minizip_BINARY_DIR}/minizip.pc)
configure_file(${minizip_SOURCE_DIR}/minizip.pc.txt ${LIBMINIZIP_PC} @ONLY)

if(WIN32 OR CYGWIN)
    set(minizip_static_suffix "s")
    set(CMAKE_DEBUG_POSTFIX "d")
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS TRUE)
endif(WIN32 OR CYGWIN)

if(MINIZIP_BUILD_SHARED)
    add_library(${ZLIB_CONTRIB_PREFIX}libminizip SHARED
        ${LIBMINIZIP_SRCS}
        ${LIBMINIZIP_HDRS})
    add_library(MINIZIP::minizip ALIAS ${ZLIB_CONTRIB_PREFIX}libminizip)
    target_include_directories(${ZLIB_CONTRIB_PREFIX}libminizip
        PUBLIC
            $<BUILD_INTERFACE:${minizip_SOURCE_DIR}>
            $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}libminizip
        PRIVATE
            $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>
            $<$<BOOL:${HAVE___ATTR__VIS_HIDDEN}>:HAVE_HIDDEN>
            $<$<BOOL:${HAVE_UNISTD_H}>:HAVE_UNISTD_H=1>
        PUBLIC
            $<$<BOOL:${HAVE_OFF64_T}>:_LARGEFILE64_SOURCE=1>
            $<$<BOOL:${BZIP2_FOUND}>:HAVE_BZIP2=1>
            $<$<AND:$<NOT:$<BOOL:${HAVE_FOPEN64}>>,$<NOT:$<BOOL:${MSVC}>>>:USE_FILE32API=1>)

    if(CYGWIN)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizip
            PROPERTIES
                PREFIX "lib")
    else(CYGWIN)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizip
            PROPERTIES
                SOVERSION ${zlib_VERSION_MAJOR}
                VERSION ${INSTALL_VERSION})
    endif(CYGWIN)

    set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizip
        PROPERTIES
            EXPORT_NAME minizip
            PUBLIC_HEADER "${LIBMINIZIP_HDRS}")

    if(MSVC)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizip
            PROPERTIES
                OUTPUT_NAME libminizip)
    else(MSVC)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizip
            PROPERTIES
                OUTPUT_NAME minizip)
    endif(MSVC)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}libminizip
        PUBLIC
            ZLIB::ZLIB
            $<$<BOOL:${BZIP2_FOUND}>:BZip2::BZip2>)

    add_executable(${ZLIB_CONTRIB_PREFIX}minizip
        ${MINIZIP_SRCS}
        ${MINIZIP_HDRS}
        $<$<BOOL:${WIN32}>:iowin32.h>)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}minizip
        PROPERTIES
            EXPORT_NAME minizip_executable
            OUTPUT_NAME minizip)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}minizip
        PRIVATE $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}minizip
        PRIVATE MINIZIP::minizip)
    add_executable(${ZLIB_CONTRIB_PREFIX}miniunzip
        ${MINIUNZIP_SRCS}
        ${MINIUNZIP_HDRS}
        $<$<BOOL:${WIN32}>:iowin32.c>
        $<$<BOOL:${WIN32}>:iowin32.h>)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}miniunzip
        PROPERTIES
            EXPORT_NAME miniunzip_executable
            OUTPUT_NAME miniunzip)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}miniunzip
        PRIVATE $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}miniunzip
        PRIVATE MINIZIP::minizip)
endif(MINIZIP_BUILD_SHARED)

if(MINIZIP_BUILD_STATIC)
    add_library(${ZLIB_CONTRIB_PREFIX}libminizipstatic
        STATIC
        ${LIBMINIZIP_SRCS}
        ${LIBMINIZIP_HDRS})
    add_library(MINIZIP::minizipstatic ALIAS
        ${ZLIB_CONTRIB_PREFIX}libminizipstatic)
    target_include_directories(${ZLIB_CONTRIB_PREFIX}libminizipstatic
        PUBLIC
            $<BUILD_INTERFACE:${minizip_SOURCE_DIR}>
           $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}libminizipstatic
        PRIVATE
            $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>
            $<$<BOOL:${HAVE___ATTR__VIS_HIDDEN}>:HAVE_HIDDEN>
            $<$<BOOL:${HAVE_UNISTD_H}>:HAVE_UNISTD_H=1>
        PUBLIC
            $<$<BOOL:${HAVE_OFF64_T}>:_LARGEFILE64_SOURCE=1>
            $<$<BOOL:${BZIP2_FOUND}>:HAVE_BZIP2=1>
            $<$<AND:$<NOT:$<BOOL:${HAVE_FOPEN64}>>,$<NOT:$<BOOL:${MSVC}>>>:USE_FILE32API=1>)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizipstatic
        PROPERTIES
            EXPORT_NAME minizipstatic
            PUBLIC_HEADER "${LIBMINIZIP_HDRS}")

    if(CYGWIN)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizipstatic
            PROPERTIES
                PREFIX "lib")
    endif(CYGWIN)

    if(MSVC)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizipstatic
            PROPERTIES
                ARCHIVE_OUTPUT_NAME libminizip${minizip_static_suffix})
    else(MSVC)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizipstatic
            PROPERTIES
                ARCHIVE_OUTPUT_NAME minizip${minizip_static_suffix})
    endif(MSVC)

    if(CYGWIN)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}libminizipstatic
            PROPERTIES
                SUFFIX ".dll.a")
    endif(CYGWIN)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}libminizipstatic
        PUBLIC
            ZLIB::ZLIBSTATIC
            $<$<BOOL:${BZIP2_FOUND}>:BZip2::BZip2>)

    add_executable(${ZLIB_CONTRIB_PREFIX}minizipstatic
        ${MINIZIP_SRCS}
        ${MINIZIP_HDRS}
        $<$<BOOL:${WIN32}>:iowin32.h>)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}minizipstatic
        PROPERTIES
            EXPORT_NAME minizip_static_executable
            OUTPUT_NAME minizipstatic)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}minizipstatic
        PRIVATE $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}minizipstatic
        PRIVATE MINIZIP::minizipstatic)
    add_executable(${ZLIB_CONTRIB_PREFIX}miniunzipstatic
        ${MINIUNZIP_SRCS}
        ${MINIUNZIP_HDRS}
        $<$<BOOL:${WIN32}>:iowin32.c>
        $<$<BOOL:${WIN32}>:iowin32.h>)
    set_target_properties(${ZLIB_CONTRIB_PREFIX}miniunzipstatic
        PROPERTIES
            EXPORT_NAME miniunzip_static_executable
            OUTPUT_NAME miniunzipstatic)
    target_compile_definitions(${ZLIB_CONTRIB_PREFIX}miniunzipstatic
        PRIVATE $<$<BOOL:${MSVC}>:_CRT_SECURE_NO_WARNINGS>)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}miniunzipstatic
        PRIVATE MINIZIP::minizipstatic)
endif(MINIZIP_BUILD_STATIC)

if(MINIZIP_INSTALL)
    if(MINIZIP_BUILD_SHARED)
        install(
            TARGETS
                ${ZLIB_CONTRIB_PREFIX}libminizip
                ${ZLIB_CONTRIB_PREFIX}minizip
                ${ZLIB_CONTRIB_PREFIX}miniunzip
            COMPONENT Runtime
            EXPORT minizipSharedExport
            RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
            ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
            LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
            PUBLIC_HEADER
                COMPONENT Development
                DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/minizip")
        install(
            EXPORT minizipSharedExport
            FILE minizip-shared.cmake
            NAMESPACE MINIZIP::
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/minizip)

        if(MSVC)
            install(
                FILES $<TARGET_PDB_FILE:${ZLIB_CONTRIB_PREFIX}libminizip>
                COMPONENT Runtime
                DESTINATION ${CMAKE_INSTALL_BINDIR}
                CONFIGURATIONS Debug OR RelWithDebInfo
                OPTIONAL)
        endif(MSVC)
    endif(MINIZIP_BUILD_SHARED)

    if(MINIZIP_BUILD_STATIC)
        install(
            TARGETS
                ${ZLIB_CONTRIB_PREFIX}libminizipstatic
                ${ZLIB_CONTRIB_PREFIX}minizipstatic
                ${ZLIB_CONTRIB_PREFIX}miniunzipstatic
            COMPONENT Development
            EXPORT minizipStaticExport
            RUNTIME
                DESTINATION "${CMAKE_INSTALL_BINDIR}"
                COMPONENT Runtime
            ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
            LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
            PUBLIC_HEADER DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/minizip")
        install(
            EXPORT minizipStaticExport
            FILE minizip-static.cmake
            NAMESPACE MINIZIP::
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/minizip)
    endif(MINIZIP_BUILD_STATIC)

    configure_package_config_file(
        ${minizip_SOURCE_DIR}/minizipConfig.cmake.in
        ${minizip_BINARY_DIR}/minizipConfig.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/minizip)
    write_basic_package_version_file(
        "${minizip_BINARY_DIR}/minizipConfigVersion.cmake"
        VERSION "${minizip_VERSION}"
        COMPATIBILITY AnyNewerVersion)
    install(FILES ${minizip_BINARY_DIR}/minizipConfig.cmake
                  ${minizip_BINARY_DIR}/minizipConfigVersion.cmake
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/minizip)
    install(
        FILES ${LIBMINIZIP_PC}
        COMPONENT Development
        DESTINATION "${CMAKE_INSTALL_LIBDIR}/pkgconfig")
endif(MINIZIP_INSTALL)

if(MINIZIP_BUILD_TESTING)
    enable_testing()
    add_subdirectory(test)
endif(MINIZIP_BUILD_TESTING)
