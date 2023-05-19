#!/bin/bash

echo "ℹ️ Generating certificate for www.example.com ..."
openssl req -nodes -x509 -newkey rsa:4096 -keyout /certs/privatekey.key -out /certs/certificate.pem -days 365 -subj /CN=www.example.com/

chown -R root:101 /certs
chmod -R 777 /certs
