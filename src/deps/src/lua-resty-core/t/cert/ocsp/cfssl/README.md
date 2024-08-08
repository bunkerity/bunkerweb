Following steps require https://github.com/cloudflare/cfssl

Initiate CA by creating root certificate pair:

```
cfssl gencert -initca ca_csr.json | cfssljson -bare ca
```

Continue with intermediate certificate pair for signing:

```
cfssl gencert -ca ca.pem -ca-key ca-key.pem -config=cfssl_config.json -profile=intermediate intermediate_ca_csr.json | cfssljson -bare intermediate_ca
```

Also create OCSP certificate pair to sign OCSP responses:

```
cfssl gencert -ca intermediate_ca.pem -ca-key intermediate_ca-key.pem -config=cfssl_config.json -profile=ocsp ocsp_csr.json | cfssljson -bare ocsp
```

Create a leaf certificate:

```
cfssl gencert -ca intermediate_ca.pem -ca-key intermediate_ca-key.pem -config cfssl_config.json -profile server leaf_csr.json | cfssljson -bare leaf
```

Create an OCSP response for the certificate:

```
cfssl ocspsign -ca intermediate_ca.pem -responder ocsp.pem -responder-key ocsp-key.pem -cert leaf.pem -status good | cfssljson -bare ocsp-response-good
```

Bundle certificate to be installed at Nginx:

```
cat leaf.pem intermediate_ca.pem ca.pem > leaf-bundle.pem
```

Inspect OCSP response to see what is the Next Update:

```
openssl ocsp -text -no_cert_verify -respin t/cert/ocsp/cfssl/ocsp-response-good-response.der | grep "Next Update"
```
