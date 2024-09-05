set(p256m_target ${MBEDTLS_TARGET_PREFIX}p256m)

add_library(${p256m_target}
    p256-m_driver_entrypoints.c
    p256-m/p256-m.c)

target_include_directories(${p256m_target}
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
         $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/p256-m>
         $<BUILD_INTERFACE:${MBEDTLS_DIR}/include>
         $<INSTALL_INTERFACE:include>
  PRIVATE ${MBEDTLS_DIR}/library/)

# Pass-through MBEDTLS_CONFIG_FILE and MBEDTLS_USER_CONFIG_FILE
# This must be duplicated from library/CMakeLists.txt because
# p256m is not directly linked against any mbedtls targets
# so does not inherit the compile definitions.
if(MBEDTLS_CONFIG_FILE)
    target_compile_definitions(${p256m_target}
        PUBLIC MBEDTLS_CONFIG_FILE="${MBEDTLS_CONFIG_FILE}")
endif()
if(MBEDTLS_USER_CONFIG_FILE)
    target_compile_definitions(${p256m_target}
        PUBLIC MBEDTLS_USER_CONFIG_FILE="${MBEDTLS_USER_CONFIG_FILE}")
endif()

if(INSTALL_MBEDTLS_HEADERS)

  install(DIRECTORY :${CMAKE_CURRENT_SOURCE_DIR}
    DESTINATION include
    FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
    DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    FILES_MATCHING PATTERN "*.h")

endif(INSTALL_MBEDTLS_HEADERS)

install(TARGETS ${p256m_target}
EXPORT MbedTLSTargets
DESTINATION ${CMAKE_INSTALL_LIBDIR}
PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
