#!/bin/bash

#Use the same input string of *all* the tests

CORPUS_DIR=$1

rm -f ${CORPUS_DIR}/*
mkdir -p ${CORPUS_DIR}

i=0
for filename in ../../tests/*.txt; do
    [ -e "$filename" ] || continue
    sed -n '4p' < "$filename" > ${CORPUS_DIR}/"$i"
    i=$((i + 1))
done
