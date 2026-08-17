#!/bin/bash

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"
docker run --rm -v /tmp/output:/tmp/output alpine:latest \
    sh -c "mkdir -p /tmp/output && chown -R ${USER_ID}:${GROUP_ID} /tmp/output" || return 1

cat > /tmp/output/web-cache-acl.json <<'EOF'
{
  "users": {
    "cache-reader": {
      "admin": false,
      "password": "ReaderPass123!",
      "permissions": {"web_cache": {"*": {"web_cache_read": true}}}
    },
    "cache-purger": {
      "admin": false,
      "password": "PurgerPass123!",
      "permissions": {"web_cache": {"*": {"web_cache_purge": true}}}
    }
  }
}
EOF
