#!/bin/bash

echo "ℹ️ Generating certificate for app1.example.com ..."
openssl req -nodes -x509 -newkey rsa:4096 -keyout /certs/privatekey.key -out /certs/certificate.pem -days 365 -subj /CN=app1.example.com/

chown -R root:101 /certs
chmod -R 777 /certs
