#!/bin/bash

PREFIX=""
if [[ -n "$IN_CICD" ]]; then
    PREFIX="sudo "
fi

bash -c "${PREFIX}mkdir -p /var/www/html/errors"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  echo "⭕ Failed to create custom error file directory ❌"
  return 1
  # shellcheck disable=SC2317
  exit 1
fi

bash -c "echo '<html>
  <body>
    <h1>It Works!</h1>
  </body>
</html>' | ${PREFIX}tee \"/var/www/html/errors/403.html\""
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  echo "⭕ Failed to create custom error file ❌"
  return 1
  # shellcheck disable=SC2317
  exit 1
fi

bash -c "${PREFIX}chmod -R 777 /var/www/html/errors"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
  echo "⭕ Failed to change permissions for custom error file ❌"
  return 1
  # shellcheck disable=SC2317
  exit 1
fi

grep '127.0.0.1 .*\.example\.com' "tests/misc/conf/dnsmasq.hosts" | awk '{print $2}' | while read -r hostname; do
  bash -c "${PREFIX}mkdir -p \"/var/www/html/${hostname}/errors\""
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    echo "⭕ Failed to create directory for ${hostname} custom error file ❌"
    return 1
    # shellcheck disable=SC2317
    exit 1
  fi

  bash -c "echo '<html>
  <body>
    <h1>It Works!</h1>
  </body>
</html>' | ${PREFIX}tee \"/var/www/html/${hostname}/errors/403.html\""
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    echo "⭕ Failed to create ${hostname} custom error file ❌"
    return 1
    # shellcheck disable=SC2317
    exit 1
  fi

  bash -c "${PREFIX}chmod -R 777 \"/var/www/html/${hostname}/errors\""
  # shellcheck disable=SC2181
  if [ $? -ne 0 ] ; then
    echo "⭕ Failed to change permissions for ${hostname} custom error file ❌"
    return 1
    # shellcheck disable=SC2317
    exit 1
  fi
done
