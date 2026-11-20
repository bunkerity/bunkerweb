#!/bin/bash

PREFIX=""
if [[ -n "$IN_CICD" ]]; then
    PREFIX="sudo "
fi

echo "🧰 Generating valkey certs and ACL ..."

bash -c "${PREFIX}rm -rf /tmp/valkey-tls"
bash -c "${PREFIX}rm -rf /tmp/valkey-acl"
bash -c "${PREFIX}rm -rf /tmp/valkey-sentinel"

mkdir -p /tmp/valkey-tls
mkdir -p /tmp/valkey-acl
mkdir -p /tmp/valkey-sentinel

# Generate TLS certificates for Valkey
openssl genrsa -out /tmp/valkey-tls/ca.key 2048
openssl req \
    -x509 -new -nodes -sha256 \
    -key /tmp/valkey-tls/ca.key \
    -days 365 \
    -subj /CN=valkey/ \
    -out /tmp/valkey-tls/ca.crt

openssl genrsa -out /tmp/valkey-tls/valkey.key 2048

cat > /tmp/valkey-tls/valkey.cnf <<'EOF'
[ req ]
default_bits        = 2048
prompt              = no
default_md          = sha256
req_extensions      = req_ext
distinguished_name  = dn

[ dn ]
CN                  = valkey

[ req_ext ]
subjectAltName      = @alt_names

[ alt_names ]
DNS.1               = valkey
DNS.2               = localhost
IP.1                = 127.0.0.1
EOF

openssl req \
    -new \
    -key /tmp/valkey-tls/valkey.key \
    -out /tmp/valkey-tls/valkey.csr \
    -config /tmp/valkey-tls/valkey.cnf

openssl x509 \
    -req \
    -in /tmp/valkey-tls/valkey.csr \
    -CA /tmp/valkey-tls/ca.crt \
    -CAkey /tmp/valkey-tls/ca.key \
    -CAcreateserial \
    -out /tmp/valkey-tls/valkey.crt \
    -days 365 \
    -sha256 \
    -extensions req_ext \
    -extfile /tmp/valkey-tls/valkey.cnf

rm -f /tmp/valkey-tls/valkey.csr

# Create ACL configuration file
cat > /tmp/valkey-acl/valkey.acl <<'EOF'
user default on nopass +@all ~*
user admin on >secret +@all ~*
EOF

# Create Sentinel ACL configuration file
cat > /tmp/valkey-acl/sentinel.acl <<'EOF'
user default on nopass +@all ~*
user admin on >secret +@all ~*
EOF

# Create Sentinel configuration file
cat > /tmp/valkey-sentinel/sentinel.conf <<'EOF'
sentinel monitor valkey-master 10.20.30.50 6379 2
sentinel down-after-milliseconds valkey-master 5000
sentinel parallel-syncs valkey-master 1
sentinel failover-timeout valkey-master 10000
EOF

bash -c "${PREFIX}chmod -R 777 /tmp/valkey-tls"
bash -c "${PREFIX}chmod -R 777 /tmp/valkey-acl"
bash -c "${PREFIX}chmod -R 777 /tmp/valkey-sentinel"

echo "🧰 Valkey certs and ACL generated ✅"
