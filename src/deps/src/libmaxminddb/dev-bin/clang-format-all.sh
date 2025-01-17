#!/bin/sh

format="clang-format -i -style=file"

for dir in bin include src t; do
    c_files=`find $dir -maxdepth 1 -name '*.c'`
    if [ "$c_files" != "" ]; then
        $format $dir/*.c;
    fi

    h_files=`find $dir -maxdepth 1 -name '*.h'`
    if [ "$h_files" != "" ]; then
        $format $dir/*.h;
    fi
done
