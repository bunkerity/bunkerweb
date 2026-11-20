#!/bin/bash

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"

# /tmp/output may be root-owned (created by a prior sudo run or Docker bind-mount).
# Use a throwaway container to create it and own it as the current user, so the
# rest of this script runs sudo-free regardless of how it was created.
docker run --rm -v /tmp/output:/tmp/output alpine:latest \
    sh -c "mkdir -p /tmp/output && chown -R ${USER_ID}:${GROUP_ID} /tmp/output"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔐 Failed to create /tmp/output directory ❌"
    return 1
fi

# "ops" pass: Bunkerity123!

echo "🔐 Generate acl file"
cat > /tmp/output/acl.json <<EOF
{
  "users": {
    "ci": {
      "admin": false,
      "password": "Str0ng&P@ss!",
      "permissions": {
        "services": {
          "*": { "service_read": true }
        },
        "bans": {
          "*": { "ban_read": true }
        }
      }
    },
    "ops": {
      "admin": false,
      "password_hash": "\$2b\$10\$kqnCbLjlAcR0660HxhhwkevYVxtTUhQBnmAon0uzfy9A.MOjm4U1G",
      "permissions": {
        "instances": { "*": { "instances_read": true, "instances_execute": true } },
        "jobs": { "*": { "job_run": true } }
      }
    }
  }
}
EOF
