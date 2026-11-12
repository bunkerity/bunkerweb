prefix=${CMAKE_INSTALL_PREFIX}
libdir=${dollar}{prefix}/lib${LIB_SUFFIX}
includedir=${dollar}{prefix}/include/yajl

Name: Yet Another JSON Library
Description: A Portable JSON parsing and serialization library in ANSI C
Version: ${YAJL_MAJOR}.${YAJL_MINOR}.${YAJL_MICRO}
Cflags: -I${dollar}{includedir}
Libs: -L${dollar}{libdir} -lyajl
