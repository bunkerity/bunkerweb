#!/usr/bin/env sh

mkdir -p certs

openssl ecparam -name secp256r1 -genkey -out certs/serverECDSAkey.pem
openssl req -new -config ../certs/serverA.cnf -extensions usr_cert -x509 -key certs/serverECDSAkey.pem -out certs/serverECDSA.pem -days 360 -batch

openssl ecparam -name secp256r1 -genkey -out certs/clientECDSAkey.pem
openssl req -config ../certs/clientA.cnf -extensions usr_cert -x509 -new -key certs/clientECDSAkey.pem -out certs/clientECDSA.pem -days 360 -batch

openssl req -config ../certs/serverB.cnf -extensions usr_cert -x509 -new -newkey rsa:2048 -keyout certs/serverRSAkey.pem -out certs/serverRSA.pem -nodes -days 365 -batch

openssl req -config ../certs/clientB.cnf -extensions usr_cert -x509 -new -newkey rsa:2048 -keyout certs/clientRSAkey.pem -out certs/clientRSA.pem -nodes -days 365 -batch
