# Copyright (c) 2007-2014, Lloyd Hilaiel <me@lloyd.io>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# set up a paths
SET (binDir ${CMAKE_CURRENT_BINARY_DIR}/../${YAJL_DIST_NAME}/bin)

# create a directories
FILE(MAKE_DIRECTORY ${binDir})

SET (SRCS json_reformat.c)

# use the library we build, duh.
INCLUDE_DIRECTORIES(${CMAKE_CURRENT_BINARY_DIR}/../${YAJL_DIST_NAME}/include)
LINK_DIRECTORIES(${CMAKE_CURRENT_BINARY_DIR}/../${YAJL_DIST_NAME}/lib)

ADD_EXECUTABLE(json_reformat ${SRCS})

TARGET_LINK_LIBRARIES(json_reformat yajl_s)

# In some environments, we must explicitly link libm (like qnx,
# thanks @shahbag)
IF (NOT WIN32)
    TARGET_LINK_LIBRARIES(json_reformat m)
ENDIF (NOT WIN32)

# copy the binary into the output directory
GET_TARGET_PROPERTY(binPath json_reformat LOCATION)

ADD_CUSTOM_COMMAND(TARGET json_reformat POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${binPath} ${binDir})

INSTALL(TARGETS json_reformat RUNTIME DESTINATION bin)
