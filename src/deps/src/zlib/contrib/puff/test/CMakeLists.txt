# if we are built from with zlib, use this path's)
if(NOT DEFINED ZLIB_BUILD_PUFF)
    set(WORK_DIR ${CMAKE_CURRENT_BINARY_DIR})
    set(inst_setup zlib_puff_install)
    set(ZLIB_ARG "-DZLIB_DIR=${ZLIB_DIR}")

    add_test(
        NAME zlib_puff_install
        COMMAND ${CMAKE_COMMAND}
                --install ${puff_BINARY_DIR}
                --prefix ${WORK_DIR}/test_install
                --config $<CONFIG>
        WORKING_DIRECTORY ${WORK_DIR})

    set_tests_properties(zlib_puff_install
        PROPERTIES
            FIXTURES_SETUP zlib_puff_install)
endif(NOT DEFINED ZLIB_BUILD_PUFF)

if(ZLIB_PUFF_BUILD_SHARED AND NOT WIN32)
    add_executable(${ZLIB_CONTRIB_PREFIX}puff_test
        ${puff_SOURCE_DIR}/pufftest.c
        ${puff_SOURCE_DIR}/puff.h)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}puff_test
        PRIVATE ${ZLIB_CONTRIB_PREFIX}puff_puff)

    add_test(NAME ${ZLIB_CONTRIB_PREFIX}puff_test
        COMMAND ${CMAKE_COMMAND} -P
                ${CMAKE_CURRENT_SOURCE_DIR}/tester.cmake
                "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_test>"
                "${puff_SOURCE_DIR}")

    if(GCOV_EXECUTABLE)
        add_executable(${ZLIB_CONTRIB_PREFIX}puff_test-coverage
            ${puff_SOURCE_DIR}/pufftest.c
            ${puff_SOURCE_DIR}/puff.c
            ${puff_SOURCE_DIR}/puff.h)

        target_compile_options(${ZLIB_CONTRIB_PREFIX}puff_test-coverage PRIVATE -coverage)

        target_link_options(${ZLIB_CONTRIB_PREFIX}puff_test-coverage PRIVATE -coverage)

        add_test(NAME ${ZLIB_CONTRIB_PREFIX}puff_test-coverage
            COMMAND ${CMAKE_COMMAND}
                    -P
                    ${CMAKE_CURRENT_SOURCE_DIR}/tester-cov.cmake
                    "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_test-coverage>"
                    "${puff_SOURCE_DIR}"
                    "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_bin-writer>"
                    ${GCOV_EXECUTABLE}
                    ${llvm_option})
    endif(GCOV_EXECUTABLE)
endif(ZLIB_PUFF_BUILD_SHARED AND NOT WIN32)

if(ZLIB_PUFF_BUILD_STATIC AND NOT WIN32)
    add_executable(${ZLIB_CONTRIB_PREFIX}puff_testStatic
        ${puff_SOURCE_DIR}/pufftest.c
        ${puff_SOURCE_DIR}/puff.h)

    target_link_libraries(${ZLIB_CONTRIB_PREFIX}puff_testStatic
        PRIVATE ${ZLIB_CONTRIB_PREFIX}puff_puffStatic)
    add_test(NAME ${ZLIB_CONTRIB_PREFIX}puff_testStatic
        COMMAND ${CMAKE_COMMAND} -P
                ${CMAKE_CURRENT_SOURCE_DIR}/tester.cmake
                "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_testStatic>"
                "${puff_SOURCE_DIR}")

    if(GCOV_EXECUTABLE)
        add_executable(${ZLIB_CONTRIB_PREFIX}puff_testStatic-coverage
            ${puff_SOURCE_DIR}/pufftest.c
            ${puff_SOURCE_DIR}/puff.c
            ${puff_SOURCE_DIR}/puff.h)

        target_compile_options(${ZLIB_CONTRIB_PREFIX}puff_testStatic-coverage
            PRIVATE -coverage)

        target_link_options(${ZLIB_CONTRIB_PREFIX}puff_testStatic-coverage
            PRIVATE -coverage)

        add_test(NAME ${ZLIB_CONTRIB_PREFIX}puff_testStatic-coverage
            COMMAND ${CMAKE_COMMAND}
                    -P
                    ${CMAKE_CURRENT_SOURCE_DIR}/tester-cov.cmake
                    "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_testStatic-coverage>"
                    "${puff_SOURCE_DIR}"
                    "$<TARGET_FILE:${ZLIB_CONTRIB_PREFIX}puff_bin-writer>"
                    ${GCOV_EXECUTABLE}
                    ${llvm_option})
    endif(GCOV_EXECUTABLE)
endif(ZLIB_PUFF_BUILD_STATIC AND NOT WIN32)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_test.cmake.in
    ${WORK_DIR}/puff_find_package_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_test.cmake.in
    ${WORK_DIR}/puff_add_subdirectory_test/CMakeLists.txt @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/add_subdirectory_exclude_test.cmake.in
    ${WORK_DIR}/puff_add_subdirectory_exclude_test/CMakeLists.txt
    @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_no_components_test.cmake.in
    ${WORK_DIR}/puff_find_package_no_components_test/CMakeLists.txt
    @ONLY)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/find_package_wrong_components_test.cmake.in
    ${WORK_DIR}/puff_find_package_wrong_components_test/CMakeLists.txt
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
    NAME zlib_puff_find_package_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/puff_find_package_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/puff_find_package_test)

add_test(
    NAME zlib_puff_find_package_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/puff_find_package_test_build)

set_tests_properties(zlib_puff_find_package_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP puff_fp_config)

set_tests_properties(zlib_puff_find_package_build
    PROPERTIES
        FIXTURES_REQUIRED puff_fp_config)

#
# add_subdirectory_test
#
add_test(
    NAME zlib_puff_add_subdirectory_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/puff_add_subdirectory_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/puff_add_subdirectory_test)

add_test(
    NAME zlib_puff_add_subdirectory_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY ${WORK_DIR}/puff_add_subdirectory_test_build)

set_tests_properties(zlib_puff_add_subdirectory_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP puff_as_config)

set_tests_properties(zlib_puff_add_subdirectory_build
    PROPERTIES
        FIXTURES_REQUIRED puff_as_config)

#
# add_subdirectory_exclude_test
#
add_test(
    NAME zlib_puff_add_subdirectory_exclude_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/puff_add_subdirectory_exclude_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/puff_add_subdirectory_exclude_test)

add_test(
    NAME zlib_puff_add_subdirectory_exclude_build
    COMMAND ${CMAKE_COMMAND} --build . --config $<CONFIG>
    WORKING_DIRECTORY
        ${WORK_DIR}/puff_add_subdirectory_exclude_test_build)

set_tests_properties(zlib_puff_add_subdirectory_exclude_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        FIXTURES_SETUP puff_asx_config)

set_tests_properties(zlib_puff_add_subdirectory_exclude_build
    PROPERTIES
        FIXTURES_REQUIRED puff_asx_config)

#
# find_package_no_components_test
#
add_test(
    NAME zlib_puff_find_package_no_components_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/puff_findpackage_no_components_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/puff_find_package_no_components_test)

set_tests_properties(zlib_puff_find_package_no_components_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup})

if(NOT ZLIB_PUFF_BUILD_SHARED OR NOT ZLIB_PUFF_BUILD_STATIC)
    set_tests_properties(zlib_puff_find_package_no_components_configure
        PROPERTIES
            WILL_FAIL TRUE)
endif(NOT ZLIB_PUFF_BUILD_SHARED OR NOT ZLIB_PUFF_BUILD_STATIC)

#
# find_package_no_components_test
#
add_test(
    NAME zlib_puff_find_package_wrong_components_configure
    COMMAND
        ${CMAKE_COMMAND}
        ${PLATFORM}
        -B${WORK_DIR}/puff_find_package_wrong_components_test_build
        -DCMAKE_BUILD_TYPE=$<CONFIG>
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_C_FLAGS=${CMAKE_C_FLAGS}
        "-DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}"
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}"
        -DCMAKE_INSTALL_PREFIX=${WORK_DIR}/test_install
        ${ZLIB_ARG}
        $<$<VERSION_GREATER_EQUAL:${CMAKE_VERSION},3.24>:--fresh>
        -G "${CMAKE_GENERATOR}"
        -S${WORK_DIR}/puff_find_package_wrong_components_test)

set_tests_properties(zlib_puff_find_package_wrong_components_configure
    PROPERTIES
        FIXTURES_REQUIRED ${inst_setup}
        WILL_FAIL TRUE)
