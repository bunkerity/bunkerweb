#!/bin/sh

openssl req -newkey rsa:2048 -sha256 -keyout rootAkey.pem -out rootAreq.pem -nodes -config ./rootA.cnf -days 365 -batch

openssl x509 -req -in rootAreq.pem -sha256 -extfile ./rootA.cnf -extensions v3_ca -signkey rootAkey.pem -out rootA.pem -days 365

openssl x509 -subject -issuer -noout -in rootA.pem
