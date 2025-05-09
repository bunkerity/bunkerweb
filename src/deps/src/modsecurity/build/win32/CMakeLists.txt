cmake_minimum_required(VERSION 3.24)

set(BASE_DIR ${CMAKE_CURRENT_LIST_DIR}/../..)

option(WITH_LMDB    "Include LMDB support"    OFF)
option(WITH_LUA     "Include LUA support"     ON)
option(WITH_LIBXML2 "Include LibXML2 support" ON)
option(WITH_MAXMIND "Include MaxMind support" ON)
option(WITH_CURL    "Include CURL support"    ON)

option(USE_ASAN     "Build with Address Sanitizer" OFF)

# common compiler settings

# NOTE: MBEDTLS_CONFIG_FILE is not only required to compile the mbedtls subset in others, but also
# when their headers are included while compiling libModSecurity
add_compile_definitions(WIN32 _CRT_SECURE_NO_WARNINGS MBEDTLS_CONFIG_FILE="mbedtls/mbedtls_config.h")

# set standards conformance preprocessor & compiler to align with cross-compiled codebase
# NOTE: otherwise visual c++'s default compiler/preprocessor behaviour generates C4067 warnings
# (unexpected tokens following preprocessor directive - expected a newline)
add_compile_options(/Zc:preprocessor /permissive-)

if(USE_ASAN)
  add_compile_options(/fsanitize=address)
  add_link_options(/INFERASANLIBS /INCREMENTAL:no)
endif()

# libinjection

project(libinjection C)

set(LIBINJECTION_DIR ${BASE_DIR}/others/libinjection)

add_library(libinjection STATIC ${LIBINJECTION_DIR}/src/libinjection_sqli.c ${LIBINJECTION_DIR}/src/libinjection_xss.c ${LIBINJECTION_DIR}/src/libinjection_html5.c)

# get libinjection version with git describe
execute_process(
    COMMAND git describe
    WORKING_DIRECTORY ${LIBINJECTION_DIR}
    OUTPUT_VARIABLE LIBINJECTION_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

message("-- Detecting libinjection version - ${LIBINJECTION_VERSION}")

target_compile_definitions(libinjection PRIVATE LIBINJECTION_VERSION="${LIBINJECTION_VERSION}")

# mbedtls (mbedcrypto)

project(mbedcrypto C)

set(MBEDTLS_DIR ${BASE_DIR}/others/mbedtls)

add_library(mbedcrypto STATIC ${MBEDTLS_DIR}/library/base64.c ${MBEDTLS_DIR}/library/sha1.c ${MBEDTLS_DIR}/library/md5.c ${MBEDTLS_DIR}/library/platform_util.c ${MBEDTLS_DIR}/library/constant_time.c)

target_include_directories(mbedcrypto PRIVATE ${MBEDTLS_DIR}/include)

# get mbedtls version with git describe
execute_process(
    COMMAND git describe
    WORKING_DIRECTORY ${MBEDTLS_DIR}
    OUTPUT_VARIABLE MBEDTLS_VERSION
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

message("-- Detecting Mbed TLS version - ${MBEDTLS_VERSION}")

#
# libModSecurity
#

project(libModSecurity
    VERSION
        3.0.12
    LANGUAGES
        CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED On)
set(CMAKE_CXX_EXTENSIONS Off)

set(PACKAGE_BUGREPORT "security@modsecurity.org")
set(PACKAGE_NAME "modsecurity")
set(PACKAGE_VERSION "${PROJECT_VERSION}")
set(PACKAGE_STRING "${PACKAGE_NAME} ${PACKAGE_VERSION}")
set(PACKAGE_TARNAME "${PACKAGE_NAME}")

set(HAVE_YAJL     1)    # should always be one, mandatory dependency
set(HAVE_GEOIP    0)    # should always be zero, no conan package available
set(HAVE_SSDEEP   0)    # should always be zero, no conan package available

macro(enable_feature flag option)
  if(${option})
    set(${flag} 1)  # ON
  else()
    set(${flag} 0)  # OFF
  endif()
endmacro()

enable_feature(HAVE_LMDB ${WITH_LMDB})
enable_feature(HAVE_LUA ${WITH_LUA})
enable_feature(HAVE_LIBXML2 ${WITH_LIBXML2})
enable_feature(HAVE_MAXMIND ${WITH_MAXMIND})
enable_feature(HAVE_CURL ${WITH_CURL})

include(${CMAKE_CURRENT_LIST_DIR}/ConfigureChecks.cmake)

configure_file(config.h.cmake ${BASE_DIR}/src/config.h)

find_package(PCRE2 REQUIRED)
find_package(Poco REQUIRED)
find_package(dirent REQUIRED)		# used only by tests (check dirent::dirent refernces)

macro(include_package package flag)
  if(${flag})
    find_package(${package} REQUIRED)
  endif()
endmacro()

include_package(yajl HAVE_YAJL)
include_package(libxml2 HAVE_LIBXML2)
include_package(lua HAVE_LUA)
include_package(CURL HAVE_CURL)
include_package(lmdb HAVE_LMDB)
include_package(maxminddb HAVE_MAXMIND)

# library
#

# NOTE: required to generate libModSecurity's import library (libModSecurity.lib), used by tests to link with shared library
set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

file(GLOB_RECURSE libModSecuritySources ${BASE_DIR}/src/*.cc)

add_library(libModSecurity SHARED ${libModSecuritySources})

target_compile_definitions(libModSecurity PRIVATE WITH_PCRE2)
target_include_directories(libModSecurity PRIVATE ${BASE_DIR} ${BASE_DIR}/headers ${BASE_DIR}/others ${MBEDTLS_DIR}/include)
target_link_libraries(libModSecurity PRIVATE pcre2::pcre2 libinjection mbedcrypto Poco::Poco Iphlpapi.lib)

macro(add_package_dependency project compile_definition link_library flag)
  if(${flag})
    target_compile_definitions(${project} PRIVATE ${compile_definition})
    target_link_libraries(${project} PRIVATE ${link_library})
  endif()
endmacro()

add_package_dependency(libModSecurity WITH_YAJL yajl::yajl HAVE_YAJL)
add_package_dependency(libModSecurity WITH_LIBXML2 LibXml2::LibXml2 HAVE_LIBXML2)
add_package_dependency(libModSecurity WITH_LUA lua::lua HAVE_LUA)
if(HAVE_LUA)
  target_compile_definitions(libModSecurity PRIVATE WITH_LUA_5_4)
endif()
add_package_dependency(libModSecurity MSC_WITH_CURL CURL::libcurl HAVE_CURL)
add_package_dependency(libModSecurity WITH_LMDB lmdb::lmdb HAVE_LMDB)
add_package_dependency(libModSecurity WITH_MAXMIND maxminddb::maxminddb HAVE_MAXMIND)

# tests
#

project(libModSecurityTests)

function(setTestTargetProperties executable)
  target_compile_definitions(${executable} PRIVATE WITH_PCRE2)
  target_include_directories(${executable} PRIVATE ${BASE_DIR} ${BASE_DIR}/headers)
  target_link_libraries(${executable} PRIVATE libModSecurity pcre2::pcre2 dirent::dirent)
  add_package_dependency(${executable} WITH_YAJL yajl::yajl HAVE_YAJL)
endfunction()

# unit tests
file(GLOB unitTestSources ${BASE_DIR}/test/unit/*.cc)
add_executable(unit_tests ${unitTestSources} ${BASE_DIR}/test/common/custom_debug_log.cc)
setTestTargetProperties(unit_tests)
target_compile_options(unit_tests PRIVATE /wd4805)

# regression tests
file(GLOB regressionTestsSources ${BASE_DIR}/test/regression/*.cc)
add_executable(regression_tests ${regressionTestsSources} ${BASE_DIR}/test/common/custom_debug_log.cc)
setTestTargetProperties(regression_tests)

macro(add_regression_test_capability compile_definition flag)
  if(${flag})
    target_compile_definitions(regression_tests PRIVATE ${compile_definition})
  endif()
endmacro()

add_regression_test_capability(WITH_LUA HAVE_LUA)
add_regression_test_capability(WITH_CURL HAVE_CURL)
add_regression_test_capability(WITH_LMDB HAVE_LMDB)
add_regression_test_capability(WITH_MAXMIND HAVE_MAXMIND)

enable_testing()

file(READ ${BASE_DIR}/test/test-suite.in TEST_FILES_RAW)
string(REPLACE "\n" ";" TEST_FILES ${TEST_FILES_RAW})

foreach(TEST_FILE ${TEST_FILES})
  # ignore comment lines
  string(FIND ${TEST_FILE} "#" is_comment)
  if(NOT is_comment EQUAL 0)
    string(FIND ${TEST_FILE} "TESTS+=" is_valid_prefix)
    if(NOT is_valid_prefix EQUAL 0)
      message(FATAL_ERROR "Invalid prefix in line: ${TEST_FILE}")
    endif()

    # remove 'TESTS+=' prefix and 'test/' too because tests are launched
    # from that directory
    string(SUBSTRING ${TEST_FILE} 12 -1 TEST_FILE)

    # test name
    get_filename_component(TEST_NAME ${TEST_FILE} NAME_WE)

    # determine test runner based on test path prefix
    string(FIND ${TEST_FILE} "test-cases/regression/" is_regression_test)
    if(is_regression_test EQUAL 0)
        set(TEST_RUNNER "regression_tests")
    else()
        set(TEST_RUNNER "unit_tests")
    endif()

    add_test(NAME ${TEST_NAME} COMMAND ${TEST_RUNNER} ${TEST_FILE} WORKING_DIRECTORY ${BASE_DIR}/test)
  endif()
endforeach()

# benchmark
add_executable(benchmark ${BASE_DIR}/test/benchmark/benchmark.cc)
setTestTargetProperties(benchmark)

# rules_optimization
add_executable(rules_optimization ${BASE_DIR}/test/optimization/optimization.cc)
setTestTargetProperties(rules_optimization)


# examples
#

project(libModSecurityExamples)

function(setExampleTargetProperties executable)
  target_include_directories(${executable} PRIVATE ${BASE_DIR} ${BASE_DIR}/headers)
  target_link_libraries(${executable} PRIVATE libModSecurity)
endfunction()

# simple_example_using_c
add_executable(simple_example_using_c ${BASE_DIR}/examples/simple_example_using_c/test.c)
setExampleTargetProperties(simple_example_using_c)

# using_bodies_in_chunks
add_executable(using_bodies_in_chunks ${BASE_DIR}/examples/using_bodies_in_chunks/simple_request.cc)
setExampleTargetProperties(using_bodies_in_chunks)

# reading_logs_via_rule_message
add_executable(reading_logs_via_rule_message ${BASE_DIR}/examples/reading_logs_via_rule_message/simple_request.cc)
setExampleTargetProperties(reading_logs_via_rule_message)

# reading_logs_with_offset
add_executable(reading_logs_with_offset ${BASE_DIR}/examples/reading_logs_with_offset/read.cc)
setExampleTargetProperties(reading_logs_with_offset)

# multithread
add_executable(multithread ${BASE_DIR}/examples/multithread/multithread.cc)
setExampleTargetProperties(multithread)

# tools
#

# rules_check
add_executable(rules_check ${BASE_DIR}/tools/rules-check/rules-check.cc)
target_include_directories(rules_check PRIVATE ${BASE_DIR} ${BASE_DIR}/headers)
target_link_libraries(rules_check PRIVATE libModSecurity)
