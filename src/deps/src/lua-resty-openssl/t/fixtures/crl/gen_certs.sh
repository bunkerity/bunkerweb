#!/bin/bash
#
# run this script in t/fixtures/crl
#
# root ca
mkdir -p rootca/newcerts
touch rootca/index.txt
echo 1000 > rootca/serial

# root ca key
openssl genrsa -out rootca.key.pem 4096
chmod 400 rootca.key.pem

# root ca cert
openssl req -config rootca.cnf -key rootca.key.pem \
    -new -x509 -days 3650 -sha256 -extensions v3_ca \
    -out rootca.cert.pem \
    -subj "/C=US/ST=CA/L=SF/O=Kong/OU=Kong/CN=www.rootca.kong.com"


# sub ca
mkdir -p subca/newcerts
touch subca/index.txt
echo 2000 > subca/serial
echo 2000 > subca/crlnumber

# sub ca key
openssl genrsa -out subca.key.pem 4096
chmod 400 subca.key.pem

# sub ca csr
openssl req -config subca.cnf -new -sha256 \
    -key subca.key.pem -out subca.csr.pem \
    -subj "/C=US/ST=CA/L=SF/O=Kong/OU=Kong/CN=www.subca.kong.com"

# sub ca cert
echo -e "y\ny\n" | openssl ca -config rootca.cnf -extensions v3_sub_ca \
      -days 3650 -notext -md sha256 \
      -in subca.csr.pem -out subca.cert.pem

# ca chain
#cat ca/sub/subca.cert.pem ca/root/root.cert.pem > chain.pem

# leaf certs
for name in valid revoked
do
  openssl genrsa -out $name.key.pem 2048
  chmod 400 $name.key.pem

  openssl req -config subca.cnf -key subca.key.pem \
      -new -sha256 -out $name.csr.pem \
      -subj "/C=US/ST=CA/L=SF/O=Kong/OU=Kong/CN=www.$name.kong.com"

  echo -e "y\ny\n" | openssl ca -config subca.cnf -extensions usr_cert \
      -days 3650 -notext -md sha256 \
      -in $name.csr.pem -out $name.cert.pem
done

# revoke cert
openssl ca -config subca.cnf -revoke revoked.cert.pem

# generate crl file
openssl ca -config subca.cnf -gencrl -out crl.pem -crldays 3650

# remove unused files
rm -rf rootca subca *.csr.pem
