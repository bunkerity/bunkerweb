# if we are built from with zlib, use this path's)
if(NOT DEFINED ZLIB_BUILD_ZLIB1_DLL)
    set(WORK_DIR ${CMAKE_CURRENT_BINARY_DIR})
    set(inst_setup zlib1-dll_install)
    set(ZLIB_ARG "-DZLIB_DIR=${ZLIB_DIR}")

    add_test(
        NAME zlib1-dll_install
        COMMAND ${CMAKE_COMMAND}
                --install ${zlib1-dll_BINARY_DIR}
                --prefix ${WORK_DIR}/test_install
                --config $<CONFIG>
        WORKING_DIRECTORY ${WORK_DIR})

    set_tests_properties(zlib1-dll_install
        PROPERTIES
            FIXTURES_SETUP zlib1-dll_install)
endif(NOT DEFINED ZLIB_BUILD_ZLIB1_DLL)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_test.cmake.in
    ${WORK_DIR}/zlib1-dll_find_package_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_test.cmake.in
    ${WORK_DIR}/zlib1-dll_add_subdirectory_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_exclude_test.cmake.in
    ${WORK_DIR}/zlib1-dll_add_subdirectory_exclude_test/CMakeLists.txt
    @ONLY)

# CMAKE_GENERATOR_PLATFORM doesn't work in the if
set(GENERATOR ${CMAKE_GENERATOR_PLATFORM})

if(GENERATOR)
    set(PLATFORM "-A ${GENERATOR}")
endif(GENERATOR)

#
# findpackage_test
#
add_test(
    NAME zlib1-dll_find_package_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/zlib1-dll_find_package_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/zlib1-dll_find_package_test)

add_test(
    NAME zlib1-dll_find_package_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/zlib1-dll_find_package_test_build)

set_tests_properties(zlib1-dll_find_package_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP z1dll_config)

set_tests_properties(zlib1-dll_find_package_build
    PROPERTIES
        FIXTURES_REQUIRED z1dll_config)

#
# add_subdirectory_test
#
add_test(
    NAME zlib1-dll_add_subdirectory_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/zlib1-dll_add_subdirectory_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/zlib1-dll_add_subdirectory_test)

add_test(
    NAME zlib1-dll_add_subdirectory_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/zlib1-dll_add_subdirectory_test_build)

set_tests_properties(zlib1-dll_add_subdirectory_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP z1dllas_config)

set_tests_properties(zlib1-dll_add_subdirectory_build
    PROPERTIES
        FIXTURES_REQUIRED z1dllas_config)

#
# add_subdirectory_exclude_test
#
add_test(
    NAME zlib1-dll_add_subdirectory_exclude_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/zlib1-dll_add_subdirectory_exclude_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/zlib1-dll_add_subdirectory_exclude_test)

add_test(
    NAME zlib1-dll_add_subdirectory_exclude_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY
        ${WORK_DIR}/zlib1-dll_add_subdirectory_exclude_test_build)

set_tests_properties(zlib1-dll_add_subdirectory_exclude_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP z1dllx_config)

set_tests_properties(zlib1-dll_add_subdirectory_exclude_build
    PROPERTIES
        FIXTURES_REQUIRED z1dllx_config)
