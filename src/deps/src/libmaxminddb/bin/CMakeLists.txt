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

  target_compile_definitions(mmdblookup PRIVATE PACKAGE_VERSION="${PROJECT_VERSION}")

  target_link_libraries(mmdblookup maxminddb pthread)

  if (MAXMINDDB_INSTALL)
    install(
      TARGETS mmdblookup
      DESTINATION ${CMAKE_INSTALL_BINDIR}
    )
  endif()
endif()
