if(MSVC)
    if(CMAKE_VERSION VERSION_GREATER_EQUAL 4.1)
        cmake_policy(SET CMP0194 NEW)
    endif(CMAKE_VERSION VERSION_GREATER_EQUAL 4.1)

    enable_language(ASM_MASM)
else(MSVC)
    enable_language(ASM)
endif(MSVC)

add_library(zlib_gvmat64 OBJECT gvmat64.S)
set_target_properties(zlib_gvmat64 PROPERTIES LINKER_LANGUAGE C)

if(ZLIB_BUILD_SHARED)
    target_sources(zlib PRIVATE $<TARGET_OBJECTS:zlib_gvmat64>)
endif(ZLIB_BUILD_SHARED)

if(ZLIB_BUILD_STATIC)
    target_sources(zlibstatic PRIVATE $<TARGET_OBJECTS:zlib_gvmat64>)
endif(ZLIB_BUILD_STATIC)
