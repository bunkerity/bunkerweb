# getopt is required by mmdblookup which is not available by default on Windows
if(NOT WIN32)
  add_executable(mmdblookup
    mmdblookup.c
  )

  target_link_libraries(mmdblookup maxminddb pthread)

  install(
    TARGETS mmdblookup
    RUNTIME DESTINATION bin
  )
endif()
