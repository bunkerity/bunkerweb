FIND_PROGRAM(doxygenPath doxygen)

IF (doxygenPath)
  SET (YAJL_VERSION ${YAJL_MAJOR}.${YAJL_MINOR}.${YAJL_MICRO})
  SET(yajlDirName yajl-${YAJL_VERSION})
  SET(docPath
      "${CMAKE_CURRENT_BINARY_DIR}/${yajlDirName}/share/doc/${yajlDirName}")
  MESSAGE("** using doxygen at: ${doxygenPath}")
  MESSAGE("** documentation output to: ${docPath}")

  CONFIGURE_FILE(${CMAKE_CURRENT_SOURCE_DIR}/src/YAJL.dxy
                 ${CMAKE_CURRENT_BINARY_DIR}/YAJL.dxy @ONLY)

  FILE(MAKE_DIRECTORY "${docPath}")

  ADD_CUSTOM_TARGET(doc
                    ${doxygenPath} YAJL.dxy   
                    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})

ELSE (doxygenPath)
  MESSAGE("!! doxygen not found, not generating documentation")     
  ADD_CUSTOM_TARGET(
    doc
    echo doxygen not installed, not generating documentation
  )
ENDIF (doxygenPath)
