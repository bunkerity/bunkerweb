rem #!/bin/sh

openssl req -newkey rsa:1024 -sha1 -keyout rootBkey.pem -out rootBreq.pem -nodes -config ./rootB.cnf -days 365 -batch

openssl x509 -req -in rootBreq.pem -sha1 -extfile ./rootB.cnf -extensions v3_ca -signkey rootBkey.pem -out rootB.pem -days 365

openssl x509 -subject -issuer -noout -in rootB.pem
