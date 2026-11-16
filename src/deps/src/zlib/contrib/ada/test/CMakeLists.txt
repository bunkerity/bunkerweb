function(ZLIB_ADA_findTestEnv testName)
    set(testEnv "PATH=")

    if(MSVC OR MINGW)
        set(separator "\\\;")
    else()
        set(separator ":")
    endif()

    string(APPEND testEnv "$<TARGET_FILE_DIR:ZLIB::ZLIB>${separator}")
    string(APPEND testEnv "$ENV{PATH}")

    set_tests_properties(${testName} PROPERTIES ENVIRONMENT "${testEnv}")
endfunction(ZLIB_ADA_findTestEnv testName)

if(ZLIB_ADA_BUILD_SHARED)
    ada_add_executable(zlib_ada_test ${zlibAda_SOURCE_DIR}/test.adb)

    target_link_libraries(zlib_ada_test
        PRIVATE
            zlib_ada_Ada
            zlib_ada_streams)

    ada_find_ali(zlib_ada_test)

    add_test(NAME zlib_ada_test COMMAND zlib_ada_test)
    set_tests_properties(zlib_ada_test
        PROPERTIES
            FIXTURES_REQUIRED zlib_ada_cleanup
            RESOURCE_LOCK ada_test_files)

    if(MSVC
       OR MSYS
       OR MINGW
       OR CYGWIN)
        zlib_ada_findtestenv(zlib_ada_ada-test)
    endif(
        MSVC
        OR MSYS
        OR MINGW
        OR CYGWIN)

    ada_add_executable(zlib_ada_buffer_demo
        ${zlibAda_SOURCE_DIR}/buffer_demo.adb)

    target_link_libraries(zlib_ada_buffer_demo
        PRIVATE
            zlib_ada_Ada)

    ada_find_ali(zlib_ada_buffer_demo)

    add_test(NAME zlib_ada_buffer-demo COMMAND zlib_ada_buffer_demo)

    if(MSVC
       OR MSYS
       OR MINGW
       OR CYGWIN)
        zlib_ada_findtestenv(zlib_ada_buffer-demo)
    endif(
        MSVC
        OR MSYS
        OR MINGW
        OR CYGWIN)

    ada_add_executable(zlib_ada_mtest ${zlibAda_SOURCE_DIR}/mtest.adb)

    target_link_libraries(zlib_ada_mtest
        PRIVATE
            zlib_ada_Ada)

    ada_find_ali(zlib_ada_mtest)

    #Not adding test as this is an endless-loop

    ada_add_executable(zlib_ada_read ${zlibAda_SOURCE_DIR}/read.adb)

    target_link_libraries(zlib_ada_read
        PRIVATE
            zlib_ada_Ada)

    ada_find_ali(zlib_ada_read)

    add_test(NAME zlib_ada_read COMMAND zlib_ada_read)

    if(MSVC
       OR MSYS
       OR MINGW
       OR CYGWIN)
        zlib_ada_findtestenv(zlib_ada_read)
    endif(
        MSVC
        OR MSYS
        OR MINGW
        OR CYGWIN)
endif(ZLIB_ADA_BUILD_SHARED)

if(ZLIB_ADA_BUILD_STATIC)
    ada_add_executable(zlib_ada_testStatic ${zlibAda_SOURCE_DIR}/test.adb)

    target_link_libraries(zlib_ada_testStatic
        PRIVATE
            zlib_ada_AdaStatic
            zlib_ada_streamsStatic)

    ada_find_ali(zlib_ada_testStatic)

    add_test(NAME zlib_ada_testStatic COMMAND zlib_ada_testStatic)
    set_tests_properties(zlib_ada_testStatic
        PROPERTIES
            FIXTURES_REQUIRED zlib_ada_cleanup
            RESOURCE_LOCK ada_test_files)

    ada_add_executable(zlib_ada_buffer-demoStatic
        ${zlibAda_SOURCE_DIR}/buffer_demo.adb)

    target_link_libraries(zlib_ada_buffer-demoStatic
        PRIVATE
            zlib_ada_AdaStatic)

    ada_find_ali(zlib_ada_buffer-demoStatic)

    add_test(NAME zlib_ada_buffer-demoStatic
             COMMAND zlib_ada_buffer-demoStatic)

    ada_add_executable(zlib_ada_mtestStatic ${zlibAda_SOURCE_DIR}/mtest.adb)

    target_link_libraries(zlib_ada_mtestStatic
        PRIVATE
            zlib_ada_AdaStatic)

    ada_find_ali(zlib_ada_mtestStatic)

    # Not adding test as this is an endless-loop

    ada_add_executable(zlib_ada_readStatic ${zlibAda_SOURCE_DIR}/read.adb)

    target_link_libraries(zlib_ada_readStatic
        PRIVATE
            zlib_ada_AdaStatic)

    ada_find_ali(zlib_ada_readStatic)

    add_test(NAME zlib_ada_readStatic COMMAND zlib_ada_readStatic)
endif(ZLIB_ADA_BUILD_STATIC)

add_test(NAME zlib_ada_cleanup
    COMMAND ${CMAKE_COMMAND} -E rm
    ${CMAKE_CURRENT_BINARY_DIR}/testzlib.in
    ${CMAKE_CURRENT_BINARY_DIR}/testzlib.out
    ${CMAKE_CURRENT_BINARY_DIR}/testzlib.zlb)
set_tests_properties(zlib_ada_cleanup
    PROPERTIES
        FIXTURES_CLEANUP zlib_ada_cleanup)
