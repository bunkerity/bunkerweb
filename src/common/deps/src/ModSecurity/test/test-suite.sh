#!/usr/bin/env bash

cd test 1> /dev/null

length=$(($#-1))
array=${@:1:$length}

PARAM=$array
FILE=${@: -1}

if [[ $FILE == *"test-cases/regression/"* ]]
then
    AMOUNT=$(./regression_tests countall ../$FILE)
    for i in `seq 1 $AMOUNT`; do
        $VALGRIND $PARAM ./regression_tests ../$FILE:$i
        if [ $? -eq 139 ]; then
            echo ":test-result: FAIL segfault: ../$FILE:$i"
        fi
        echo $VALGRIND $PARAM ./regression_tests ../$FILE:$i
    done;
else
      $VALGRIND $PARAM ./unit_tests ../$FILE
fi
cd - 1> /dev/null
