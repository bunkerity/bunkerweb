#!/usr/bin/env bash

cd test 1> /dev/null

length=$(($#-1))
array=${@:1:$length}

PARAM=$array
FILE=${@: -1}

if [[ $FILE == *"test-cases/regression/"* ]]
then
    AMOUNT=$(./regression_tests countall ../$FILE)
    RET=$?
    if [ $RET -ne 0 ]; then
        echo ":test-result: SKIP: json is not enabled. (regression/$RET) ../$FILE:$i"
        exit 0
    fi

    for i in `seq 1 $AMOUNT`; do
        $VALGRIND $PARAM ./regression_tests ../$FILE:$i
        RET=$?
        if [ $RET -ne 0 ]; then
            echo ":test-result: FAIL possible segfault/$RET: ../$FILE:$i"
        fi
        echo $VALGRIND $PARAM ./regression_tests ../$FILE:$i
    done;
else
      $VALGRIND $PARAM ./unit_tests ../$FILE
      RET=$?
      if [ $RET -eq 127 ]
      then
          echo ":test-result: SKIP: json is not enabled. (unit/$RET) ../$FILE:$i"
      elif [ $RET -ne 0 ]
      then
          echo ":test-result: FAIL possible segfault: (unit/$RET) ../$FILE:$i"
      fi
fi

cd - 1> /dev/null
