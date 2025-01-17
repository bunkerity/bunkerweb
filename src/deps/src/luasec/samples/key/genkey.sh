#!/usr/bin/env sh

openssl genrsa -des3 -out key.pem -passout pass:foobar 2048
