set(everest_target "${MBEDTLS_TARGET_PREFIX}everest")

add_library(${everest_target}
  library/everest.c
  library/x25519.c
  library/Hacl_Curve25519_joined.c)

target_include_directories(${everest_target}
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<BUILD_INTERFACE:${MBEDTLS_DIR}/include>
         $<INSTALL_INTERFACE:include>
  PRIVATE include/everest
          include/everest/kremlib
          ${MBEDTLS_DIR}/library/)

# Pass-through MBEDTLS_CONFIG_FILE and MBEDTLS_USER_CONFIG_FILE
# This must be duplicated from library/CMakeLists.txt because
# everest is not directly linked against any mbedtls targets
# so does not inherit the compile definitions.
if(MBEDTLS_CONFIG_FILE)
    target_compile_definitions(${everest_target}
        PUBLIC MBEDTLS_CONFIG_FILE="${MBEDTLS_CONFIG_FILE}")
endif()
if(MBEDTLS_USER_CONFIG_FILE)
    target_compile_definitions(${everest_target}
        PUBLIC MBEDTLS_USER_CONFIG_FILE="${MBEDTLS_USER_CONFIG_FILE}")
endif()

if(INSTALL_MBEDTLS_HEADERS)

  install(DIRECTORY include/everest
    DESTINATION include
    FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
    DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    FILES_MATCHING PATTERN "*.h")

endif(INSTALL_MBEDTLS_HEADERS)

install(TARGETS ${everest_target}
  EXPORT MbedTLSTargets
  DESTINATION ${CMAKE_INSTALL_LIBDIR}
  PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
