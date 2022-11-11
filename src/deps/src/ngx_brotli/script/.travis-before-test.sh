#!/bin/bash
set -ex

# Setup shortcuts.
ROOT=`pwd`
FILES=$ROOT/script/test

# Setup directory structure.
cd $ROOT/script
if [ ! -d test ]; then
  mkdir test
fi
cd test
if [ ! -d logs ]; then
  mkdir logs
fi

# Download sample texts.
curl --compressed -o $FILES/war-and-peace.txt http://www.gutenberg.org/files/2600/2600-0.txt
echo "Kot lomom kolol slona!" > $FILES/small.txt
echo "<html>Kot lomom kolol slona!</html>" > $FILES/small.html

# Restore status-quo.
cd $ROOT
