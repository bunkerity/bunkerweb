cmake_minimum_required(VERSION 3.15...3.31)

set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake/Modules")

project(
    zlibAda
    VERSION 1.0.0
    LANGUAGES C ADA
    DESCRIPTION "A library for creating zipfiles based in zlib"
    HOMEPAGE_URL "https://www.zlib.net")

if(ZLIB_BUILD_ADA)
    set(ZLIB_ADA_BUILD_SHARED ${ZLIB_BUILD_SHARED} CACHE BOOL "")
    set(ZLIB_ADA_BUILD_STATIC ${ZLIB_BUILD_STATIC} CACHE BOOL "")
    set(ZLIB_ADA_BUILD_TESTING ${ZLIB_BUILD_TESTING} CACHE BOOL "")
    set(ZLIB_ADA_INSTALL ${ZLIB_INSTALL} CACHE BOOL "")
endif(ZLIB_BUILD_ADA)

option(ZLIB_ADA_BUILD_SHARED "Enable building ada bindings shared library" ON)
option(ZLIB_ADA_BUILD_STATIC "Enable building ada bindings static library" ON)
option(ZLIB_ADA_BUILD_TESTING "Enable building tests for ada bindings library" ON)

if(WIN32 OR CYGWIN)
    set(zlib_Ada_static_suffix "s")
    set(CMAKE_DEBUG_POSTFIX "d")
endif(WIN32 OR CYGWIN)

if(NOT DEFINED ZLIB_BUILD_ADA)
    if(ZLIB_ADA_BUILD_SHARED)
        list(APPEND REQUIRED_COMPONENTS "shared")
    endif(ZLIB_ADA_BUILD_SHARED)

    if(ZLIB_ADA_BUILD_STATIC)
        list(APPEND REQUIRED_COMPONENTS "static")
    endif(ZLIB_ADA_BUILD_STATIC)

    find_package(ZLIB REQUIRED COMPONENTS ${REQUIRED_COMPONENTS} CONFIG)
endif(NOT DEFINED ZLIB_BUILD_ADA)

if(ZLIB_ADA_BUILD_SHARED)
    ada_add_library(zlib_ada_Ada SHARED
        zlib-thin.adb
        zlib.adb)

    set_target_properties(zlib_ada_Ada
        PROPERTIES OUTPUT_NAME zlib-ada)

    target_link_libraries(zlib_ada_Ada
        INTERFACE ZLIB::ZLIB)

    ada_add_library(zlib_ada_streams SHARED
        zlib-streams.adb)

    target_link_libraries(zlib_ada_streams
        PUBLIC
            zlib_ada_Ada)

    ada_find_ali(zlib_ada_streams)
endif(ZLIB_ADA_BUILD_SHARED)

if(ZLIB_ADA_BUILD_STATIC)
    ada_add_library(zlib_ada_AdaStatic STATIC
        zlib-thin.adb
        zlib.adb)

    target_link_libraries(zlib_ada_AdaStatic
        INTERFACE ZLIB::ZLIBSTATIC)

    set_target_properties(zlib_ada_AdaStatic
        PROPERTIES OUTPUT_NAME zlib-ada${zlib_Ada_static_suffix})

    ada_add_library(zlib_ada_streamsStatic STATIC
        zlib-streams.adb)

    target_link_libraries(zlib_ada_streamsStatic
        PUBLIC
            zlib_ada_AdaStatic)

    ada_find_ali(zlib_ada_streamsStatic)
endif(ZLIB_ADA_BUILD_STATIC)

if(ZLIB_ADA_BUILD_TESTING)
    enable_testing()
    add_subdirectory(test)
endif(ZLIB_ADA_BUILD_TESTING)
