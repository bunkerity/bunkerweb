rem #!/bin/sh

openssl req -newkey rsa:1024 -keyout serverAkey.pem -out serverAreq.pem -config ./serverA.cnf -nodes -days 365 -batch

openssl x509 -req -in serverAreq.pem -sha1 -extfile ./serverA.cnf -extensions usr_cert -CA rootA.pem -CAkey rootAkey.pem -CAcreateserial -out serverAcert.pem -days 365

copy serverAcert.pem + rootA.pem serverA.pem

openssl x509 -subject -issuer -noout -in serverA.pem
