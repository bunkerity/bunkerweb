cmake_minimum_required(VERSION 3.15...3.31)

project(
    testzlib
    VERSION 1.0.0
    LANGUAGES C
    DESCRIPTION "A little program to test zlib"
    HOMEPAGE_URL "https://www.zlib.net")

# ============================================================================
# set options if build from zlib
# ============================================================================
if(ZLIB_BUILD_TESTZLIB)
    set(ZLIB_TESTZLIB_BUILD_SHARED ${ZLIB_BUILD_SHARED} CACHE BOOL "")
    set(ZLIB_TESTZLIB_BUILD_STATIC ${ZLIB_BUILD_STATIC} CACHE BOOL "")
endif(ZLIB_BUILD_TESTZLIB)

option(ZLIB_TESTZLIB_BUILD_SHARED "Enable building testzlib" ON)
option(ZLIB_TESTZLIB_BUILD_STATIC "Enable building static linked testzlib" ON)
option(ZLIB_TESTZLIB_INSTALL "Enable installation of testzlib" ON)

if(ZLIB_TESTZLIB_BUILD_SHARED)
    list(APPEND REQUIRED_COMPONENTS "shared")
endif(ZLIB_TESTZLIB_BUILD_SHARED)

if(ZLIB_TESTZLIB_BUILD_STATIC)
    list(APPEND REQUIRED_COMPONENTS "static")
endif(ZLIB_TESTZLIB_BUILD_STATIC)

if(NOT ZLIB_BUILD_TESTZLIB)
    find_package(ZLIB REQUIRED COMPONENTS ${REQUIRED_COMPONENTS} CONFIG)
endif(NOT ZLIB_BUILD_TESTZLIB)

if(ZLIB_TESTZLIB_BUILD_SHARED)
    add_executable(${ZLIB_CONTRIB_PREFIX}testzlib testzlib.c)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}testzlib PRIVATE ZLIB::ZLIB)

    set_target_properties(${ZLIB_CONTRIB_PREFIX}testzlib
        PROPERTIES
            OUTPUT_NAME testzlib)

    if(ZLIB_TESTZLIB_INSTALL)
        install(
            TARGETS ${ZLIB_CONTRIB_PREFIX}testzlib
            COMPONENT Runtime
            RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
    endif(ZLIB_TESTZLIB_INSTALL)
endif(ZLIB_TESTZLIB_BUILD_SHARED)

if(ZLIB_TESTZLIB_BUILD_STATIC)
    add_executable(${ZLIB_CONTRIB_PREFIX}testzlibStatic testzlib.c)
    target_link_libraries(${ZLIB_CONTRIB_PREFIX}testzlibStatic
        PRIVATE ZLIB::ZLIBSTATIC)

    set_target_properties(${ZLIB_CONTRIB_PREFIX}testzlibStatic
        PROPERTIES
            OUTPUT_NAME testzlibStatic)

    if(ZLIB_TESTZLIB_INSTALL)
        install(
            TARGETS ${ZLIB_CONTRIB_PREFIX}testzlibStatic
            COMPONENT Runtime
            RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
    endif(ZLIB_TESTZLIB_INSTALL)
endif(ZLIB_TESTZLIB_BUILD_STATIC)
