#CMAKE_ARGV0 = /path/to/cmake
#CMAKE_ARGV1 = -P
#CMAKE_ARGV2 = path/to/this/file
#CMAKE_ARGV3 = --
#CMAKE_ARGV4 = compiler
#CMAKE_ARGV5 = OBJECT-DIR
#CMAKE_ARGV6 = source-file

if(NOT CMAKE_ARGV4)
    message(FATAL_ERROR "compiler not set")
endif(NOT CMAKE_ARGV4)

if(NOT CMAKE_ARGV5)
    message(FATAL_ERROR "object dir not set")
endif(NOT CMAKE_ARGV5)

if(NOT CMAKE_ARGV6)
    message(FATAL_ERROR "source not set")
endif(NOT CMAKE_ARGV6)

foreach(arg RANGE 7 ${CMAKE_ARGC})
    list(APPEND FLAGS "${CMAKE_ARGV${arg}}")
endforeach(arg RANGE 7 ${CMAKE_ARGC})

execute_process(COMMAND ${CMAKE_ARGV4} compile ${FLAGS} ${CMAKE_ARGV6}
                WORKING_DIRECTORY ${CMAKE_ARGV5}
                RESULT_VARIABLE RESULT
                OUTPUT_VARIABLE dont_care
                ERROR_VARIABLE ERROR)

if(RESULT)
    message(FATAL_ERROR ${RESULT} ${ERROR})
endif(RESULT)
