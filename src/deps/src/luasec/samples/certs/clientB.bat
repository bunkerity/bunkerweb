rem #!/bin/sh

openssl req -newkey rsa:1024 -sha1 -keyout clientBkey.pem -out clientBreq.pem -nodes -config ./clientB.cnf -days 365 -batch

openssl x509 -req -in clientBreq.pem -sha1 -extfile ./clientB.cnf -extensions usr_cert -CA rootB.pem -CAkey rootBkey.pem -CAcreateserial -out clientBcert.pem -days 365

copy clientBcert.pem + rootB.pem clientB.pem

openssl x509 -subject -issuer -noout -in clientB.pem
