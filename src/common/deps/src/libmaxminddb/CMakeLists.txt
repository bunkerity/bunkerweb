cmake_minimum_required (VERSION 3.9)
project(maxminddb
  LANGUAGES C
  VERSION 1.5.2
)
set(MAXMINDDB_SOVERSION 0.0.7)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_EXTENSIONS OFF)

option(BUILD_SHARED_LIBS "Build shared libraries (.dll/.so) instead of static ones (.lib/.a)" OFF)
option(BUILD_TESTING "Build test programs" ON)

include(CheckTypeSize)
check_type_size("unsigned __int128" UINT128)
check_type_size("unsigned int __attribute__((mode(TI)))" UINT128_USING_MODE)
if(HAVE_UINT128)
  set(MMDB_UINT128_USING_MODE 0)
  set(MMDB_UINT128_IS_BYTE_ARRAY 0)
elseif(HAVE_UINT128_USING_MODE)
  set(MMDB_UINT128_USING_MODE 1)
  set(MMDB_UINT128_IS_BYTE_ARRAY 0)
else()
  set(MMDB_UINT128_USING_MODE 0)
  set(MMDB_UINT128_IS_BYTE_ARRAY 1)
endif()

include (TestBigEndian)
TEST_BIG_ENDIAN(IS_BIG_ENDIAN)

if (${CMAKE_SYSTEM_NAME} MATCHES "Linux")
  set(CMAKE_POSITION_INDEPENDENT_CODE ON)
endif()

configure_file(${PROJECT_SOURCE_DIR}/include/maxminddb_config.h.cmake.in 
               ${PROJECT_SOURCE_DIR}/include/maxminddb_config.h)

add_library(maxminddb
  src/maxminddb.c
  src/data-pool.c
)
add_library(maxminddb::maxminddb ALIAS maxminddb)

set_target_properties(maxminddb PROPERTIES VERSION ${MAXMINDDB_SOVERSION})

target_compile_definitions(maxminddb PUBLIC PACKAGE_VERSION="${PROJECT_VERSION}")

if(NOT IS_BIG_ENDIAN)
  target_compile_definitions(maxminddb PRIVATE MMDB_LITTLE_ENDIAN=1)
endif()

if(MSVC)
  target_compile_definitions(maxminddb PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

if(WIN32)
  target_link_libraries(maxminddb ws2_32)
  if(BUILD_SHARED_LIBS)
    set_target_properties(maxminddb PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
  endif()
endif()

target_include_directories(maxminddb PUBLIC
  $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}>
  $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

set(MAXMINDB_HEADERS
  include/maxminddb.h
  include/maxminddb_config.h
)
set_target_properties(maxminddb PROPERTIES PUBLIC_HEADER "${MAXMINDB_HEADERS}")

install(TARGETS maxminddb
	EXPORT maxminddb)

# This is required to work with FetchContent
install(EXPORT maxminddb
        FILE maxminddb-config.cmake
        NAMESPACE maxminddb::
        DESTINATION lib/cmake/maxminddb)

# We always want to build mmdblookup
add_subdirectory(bin)

if (BUILD_TESTING)
  enable_testing()
  add_subdirectory(t)
endif()

