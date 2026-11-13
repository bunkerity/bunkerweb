cmake_minimum_required(VERSION 3.15...3.31)

project(
    iostreamV3
    VERSION 1.0.0
    LANGUAGES CXX
    DESCRIPTION "A library for using C++ IOStreams with zlib V3"
    HOMEPAGE_URL "https://www.zlib.net")

if(ZLIB_BUILD_IOSTREAM3)
    set(ZLIB_IOSTREAM3_BUILD_SHARED ${ZLIB_BUILD_SHARED} CACHE BOOL "")
    set(ZLIB_IOSTREAM3_BUILD_STATIC ${ZLIB_BUILD_STATIC} CACHE BOOL "")
    set(ZLIB_IOSTREAM3_BUILD_TESTING ${ZLIB_BUILD_TESTING} CACHE BOOL "")
    set(ZLIB_IOSTREAM3_INSTALL ${ZLIB_INSTALL} CACHE BOOL "")
endif(ZLIB_BUILD_IOSTREAM3)

option(ZLIB_IOSTREAM3_BUILD_SHARED "Enable building blast shared library" ON)
option(ZLIB_IOSTREAM3_BUILD_STATIC "Enable building blast static library" ON)
option(ZLIB_IOSTREAM3_BUILD_TESTING "Enable building tests for blast" ON)
option(ZLIB_IOSTREAM3_INSTALL "Enable installation of iostream" ON)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

if(NOT DEFINED ZLIB_BUILD_IOSTREAM3)
    if(ZLIB_IOSTREAM3_BUILD_SHARED)
        list(APPEND REQUIRED_COMPONENTS "shared")
    endif(ZLIB_IOSTREAM3_BUILD_SHARED)

    if(ZLIB_IOSTREAM3_BUILD_STATIC)
        list(APPEND REQUIRED_COMPONENTS "static")
    endif(ZLIB_IOSTREAM3_BUILD_STATIC)

    find_package(ZLIB REQUIRED COMPONENTS ${REQUIRED_COMPONENTS} CONFIG)
endif(NOT DEFINED ZLIB_BUILD_IOSTREAM3)

if(WIN32 OR CYGWIN)
    set(${ZLIB_CONTRIB_PREFIX}IOStream3_static_suffix "s")
    set(CMAKE_DEBUG_POSTFIX "d")
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS TRUE)
endif(WIN32 OR CYGWIN)

if(ZLIB_IOSTREAM3_BUILD_SHARED)
    add_library(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3 SHARED
                zfstream.cc
                zfstream.h)

    add_library(IOSTREAMV3::IOSTREAMV3 ALIAS
        ${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3)

    if(NOT CYGWIN)
        set_target_properties(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3
            PROPERTIES
                SOVERSION ${iostreamV3_VERSION_MAJOR}
                VERSION ${iostreamV3_VERSION})
    endif(NOT CYGWIN)

    set_target_properties(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3
        PROPERTIES
            EXPORT_NAME IOSTREAMV3
            OUTPUT_NAME iostream3)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3
        PUBLIC ZLIB::ZLIB)
endif(ZLIB_IOSTREAM3_BUILD_SHARED)

if(ZLIB_IOSTREAM3_BUILD_STATIC)
    add_library(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3Static STATIC
                zfstream.cc
                zfstream.h)

    add_library(IOSTREAMV3::IOSTREAMV3STATIC
        ALIAS ${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3Static)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3Static
        PUBLIC ZLIB::ZLIBSTATIC)

    set_target_properties(${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3Static
        PROPERTIES
            EXPORT_NAME IOSTREAMV3STATIC
            OUTPUT_NAME
                iostream3${${ZLIB_CONTRIB_PREFIX}IOStream3_static_suffix})
endif(ZLIB_IOSTREAM3_BUILD_STATIC)
if(ZLIB_IOSTREAM3_INSTALL)
    if(ZLIB_IOSTREAM3_BUILD_SHARED)
        install(
            TARGETS ${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3
            COMPONENT Runtime
            EXPORT iostream3SharedExport
            RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
            ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}")
        install(
            EXPORT iostream3SharedExport
            FILE iostreamv3-shared.cmake
            NAMESPACE IOSTREAMV3::
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/iostreamv3)

        if(MSVC)
            install(
                FILES
                    $<TARGET_PDB_FILE:${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3>
                COMPONENT Development
                DESTINATION ${CMAKE_INSTALL_BINDIR}
                CONFIGURATIONS Debug OR RelWithDebInfo
                OPTIONAL)
        endif(MSVC)
    endif(ZLIB_IOSTREAM3_BUILD_SHARED)

    if(ZLIB_IOSTREAM3_BUILD_STATIC)
        install(
            TARGETS ${ZLIB_CONTRIB_PREFIX}iostream3_iostreamv3Static
            COMPONENT Development
            EXPORT iostream3StaticExport
            ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}")
        install(
            EXPORT iostream3StaticExport
            FILE iostreamv3-static.cmake
            NAMESPACE IOSTREAMV3::
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/iostreamv3)
    endif(ZLIB_IOSTREAM3_BUILD_STATIC)

    configure_package_config_file(
        ${iostreamV3_SOURCE_DIR}/iostream3Config.cmake.in
        ${iostreamV3_BINARY_DIR}/iostreamv3Config.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/iostreamv3)

    write_basic_package_version_file(
        "${iostreamV3_BINARY_DIR}/iostreamv3ConfigVersion.cmake"
        VERSION "${iostream3_VERSION}"
        COMPATIBILITY AnyNewerVersion)

    install(FILES ${iostreamV3_BINARY_DIR}/iostreamv3Config.cmake
                  ${iostreamV3_BINARY_DIR}/iostreamv3ConfigVersion.cmake
            DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/iostreamv3)
    install(
        FILES zfstream.h
        COMPONENT Development
        DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
endif(ZLIB_IOSTREAM3_INSTALL)

if(ZLIB_IOSTREAM3_BUILD_TESTING)
    enable_testing()
    add_subdirectory(test/)
endif(ZLIB_IOSTREAM3_BUILD_TESTING)
