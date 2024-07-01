#!/usr/bin/env sh

openssl dhparam -2 -out dh-512.pem  -outform PEM 512
openssl dhparam -2 -out dh-1024.pem -outform PEM 1024
