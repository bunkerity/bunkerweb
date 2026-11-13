# if we are built from with zlib, use this path's)
if(NOT DEFINED ZLIB_BUILD_BLAST)
    set(WORK_DIR ${CMAKE_CURRENT_BINARY_DIR})
    set(inst_setup zlib_blast_install)
    set(ZLIB_ARG "-DZLIB_DIR=${ZLIB_DIR}")

    add_test(
        NAME zlib_blast_install
        COMMAND ${CMAKE_COMMAND}
                --install ${blast_BINARY_DIR}
                --prefix ${WORK_DIR}/test_install
                --config $<CONFIG>
        WORKING_DIRECTORY ${WORK_DIR})

    set_tests_properties(zlib_blast_install
        PROPERTIES
            FIXTURES_SETUP zlib_blast_install)
endif(NOT DEFINED ZLIB_BUILD_BLAST)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_test.cmake.in
    ${WORK_DIR}/blast_find_package_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_test.cmake.in
    ${WORK_DIR}/blast_add_subdirectory_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_exclude_test.cmake.in
    ${WORK_DIR}/blast_add_subdirectory_exclude_test/CMakeLists.txt
    @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_no_components_test.cmake.in
    ${WORK_DIR}/blast_find_package_no_components_test/CMakeLists.txt
    @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_wrong_components_test.cmake.in
    ${WORK_DIR}/blast_find_package_wrong_components_test/CMakeLists.txt
    @ONLY)

# CMAKE_GENERATOR_PLATFORM doesn't work in the if
set(GENERATOR ${CMAKE_GENERATOR_PLATFORM})

if(GENERATOR)
    set(PLATFORM "-A ${GENERATOR}")
endif(GENERATOR)

#
# find_package_test
#
add_test(
    NAME zlib_blast_find_package_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/blast_find_package_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/blast_find_package_test)

add_test(
    NAME zlib_blast_find_package_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/blast_find_package_test_build)

set_tests_properties(zlib_blast_find_package_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP blast_fp_config)

set_tests_properties(zlib_blast_find_package_build
    PROPERTIES
        FIXTURES_REQUIRED blast_fp_config)

#
# add_subdirectory_test
#
add_test(
    NAME zlib_blast_add_subdirectory_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/blast_add_subdirectory_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/blast_add_subdirectory_test)

add_test(
    NAME zlib_blast_add_subdirectory_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/blast_add_subdirectory_test_build)

set_tests_properties(zlib_blast_add_subdirectory_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP blast_as_config)

set_tests_properties(zlib_blast_add_subdirectory_build
    PROPERTIES
        FIXTURES_REQUIRED blast_as_config)

#
# add_subdirectory_exclude_test
#
add_test(
    NAME zlib_blast_add_subdirectory_exclude_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/blast_add_subdirectory_exclude_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/blast_add_subdirectory_exclude_test)

add_test(
    NAME zlib_blast_add_subdirectory_exclude_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY
        ${WORK_DIR}/blast_add_subdirectory_exclude_test_build)

set_tests_properties(zlib_blast_add_subdirectory_exclude_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP blast_asx_config)

set_tests_properties(zlib_blast_add_subdirectory_exclude_build
    PROPERTIES
        FIXTURES_REQUIRED blast_asx_config)

#
# findpackage_no_components_test
#
add_test(
    NAME zlib_blast_find_package_no_components_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/blast_find_package_no_components_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/blast_find_package_no_components_test)

set_tests_properties(zlib_blast_find_package_no_components_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup})

if(NOT ZLIB_BLAST_BUILD_SHARED OR NOT ZLIB_BLAST_BUILD_STATIC)
    set_tests_properties(zlib_blast_find_package_no_components_configure
        PROPERTIES
            WILL_FAIL TRUE)
endif(NOT ZLIB_BLAST_BUILD_SHARED OR NOT ZLIB_BLAST_BUILD_STATIC)

#
# find_package_wrong_components_test
#
add_test(
    NAME zlib_blast_find_package_wrong_components_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/blast_find_package_wrong_components_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/blast_find_package_wrong_components_test)

set_tests_properties(zlib_blast_find_package_wrong_components_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        WILL_FAIL TRUE)
