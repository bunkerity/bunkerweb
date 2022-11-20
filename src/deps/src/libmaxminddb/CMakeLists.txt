cmake_minimum_required (VERSION 3.9)

project(maxminddb
  LANGUAGES C
  VERSION 1.7.1
)
set(MAXMINDDB_SOVERSION 0.0.7)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_EXTENSIONS OFF)

if (WIN32)
  option(MSVC_STATIC_RUNTIME "When ON the library will be built by using MT/MTd run-time libraries" OFF)
endif()
option(BUILD_SHARED_LIBS "Build shared libraries (.dll/.so) instead of static ones (.lib/.a)" OFF)
option(BUILD_TESTING "Build test programs" ON)

include(GNUInstallDirs)

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
  if(MSVC_STATIC_RUNTIME)
    # On MSVC, when MSVC_STATIC_RUNTIME is ON, MT (Release) and MTd (Debug)
    # run-time libraries will be used instead of MD/MDd. The default is OFF so
    # MD/MDd are used when nothing related is passed.
    #
    # Adapted from https://gitlab.kitware.com/cmake/community/-/wikis/FAQ#make-override-files
    set(CMAKE_USER_MAKE_RULES_OVERRIDE
        ${CMAKE_CURRENT_SOURCE_DIR}/c_flag_overrides.cmake)
    set(CMAKE_USER_MAKE_RULES_OVERRIDE_CXX
        ${CMAKE_CURRENT_SOURCE_DIR}/cxx_flag_overrides.cmake)
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
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/maxminddb)

# We always want to build mmdblookup
add_subdirectory(bin)

if (BUILD_TESTING)
  enable_testing()
  add_subdirectory(t)
endif()

# Generate libmaxminddb.pc file for pkg-config
# Set the required variables as same with autotools
set(prefix ${CMAKE_INSTALL_PREFIX})
set(exec_prefix \${prefix})
set(libdir \${exec_prefix}/lib)
set(includedir \${prefix}/include)
set(PACKAGE_VERSION ${maxminddb_VERSION})

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/src/libmaxminddb.pc.in
  ${CMAKE_CURRENT_BINARY_DIR}/src/libmaxminddb.pc
  @ONLY)

install(FILES ${CMAKE_CURRENT_BINARY_DIR}/src/libmaxminddb.pc
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)
