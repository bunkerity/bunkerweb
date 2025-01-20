#!/bin/bash
set -ex

# Setup shortcuts.
ROOT=`pwd`

# Clone nginx read-only git repository.
if [ ! -d "nginx" ]; then
  git clone https://github.com/nginx/nginx.git
fi

# Build nginx + filter module.
cd $ROOT/nginx
# Pro memoria: --with-debug
./auto/configure \
    --prefix=$ROOT/script/test \
    --with-http_v2_module \
    --add-module=$ROOT
make -j 16

# Build brotli CLI.
cd $ROOT/deps/brotli
mkdir out
cd out
cmake ..
make -j 16 brotli

# Restore status-quo.
cd $ROOT
