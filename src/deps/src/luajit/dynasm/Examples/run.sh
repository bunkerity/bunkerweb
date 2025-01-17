#!/bin/bash
# set -x

# run test
lua ../dynasm.lua test_z_inst.c | gcc -DDASM_CHECKS -std=gnu99 -Wall -Werror -g -x c -o test_z_inst -
./test_z_inst
ec=$?

# cleanup
rm -f ./test_z_inst

# exit
exit $ec

