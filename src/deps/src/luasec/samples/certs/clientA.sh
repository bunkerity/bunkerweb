#!/bin/sh

openssl req -newkey rsa:2048 -sha256 -keyout clientAkey.pem -out clientAreq.pem \
  -nodes -config ./clientA.cnf -days 365 -batch

openssl x509 -req -in clientAreq.pem -sha256 -extfile ./clientA.cnf \
  -extensions usr_cert -CA rootA.pem -CAkey rootAkey.pem -CAcreateserial \
  -out clientAcert.pem -days 365

cat clientAcert.pem rootA.pem > clientA.pem

openssl x509 -subject -issuer -noout -in clientA.pem
