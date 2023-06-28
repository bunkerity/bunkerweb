add_library(tap
  libtap/tap.c
)

# test programs
set(TEST_TARGET_NAMES
  bad_pointers_t
  basic_lookup_t
  data_entry_list_t
  data-pool-t
  data_types_t
  dump_t
  get_value_pointer_bug_t
  get_value_t
  ipv4_start_cache_t
  ipv6_lookup_in_ipv4_t
  metadata_pointers_t
  metadata_t
  no_map_get_value_t
  read_node_t
  version_t
)

if(UNIX)  # or if (NOT WIN32)
  list(APPEND TEST_TARGET_NAMES
    bad_databases_t
    threads_t
  )
  find_package(Threads)
endif()

foreach(TEST_TARGET_NAME ${TEST_TARGET_NAMES})
  add_executable(${TEST_TARGET_NAME} ${TEST_TARGET_NAME}.c maxminddb_test_helper.c)
  target_include_directories(${TEST_TARGET_NAME} PRIVATE ../src)
  target_link_libraries(${TEST_TARGET_NAME} maxminddb tap)

  if(UNIX)
    target_link_libraries(${TEST_TARGET_NAME} m)
  endif()

  if (UNIX)
    target_link_libraries(${TEST_TARGET_NAME} ${CMAKE_THREAD_LIBS_INIT})
  endif()

  add_test( NAME ${TEST_TARGET_NAME} COMMAND ${TEST_TARGET_NAME} WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}/t)
endforeach()
