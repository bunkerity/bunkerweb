# getopt is required by mmdblookup which is not available by default on Windows
# but available in mingw-64 toolchain by-default.

if(NOT MSVC)
  add_executable(mmdblookup
    mmdblookup.c
  )

# Otherwise 'undefined reference to WinMain' linker error happen due to wmain()
  if(MINGW)
    target_link_options(mmdblookup PRIVATE "-municode")
  endif()

  target_link_libraries(mmdblookup maxminddb pthread)

  install(
    TARGETS mmdblookup
    DESTINATION bin
  )
endif()
