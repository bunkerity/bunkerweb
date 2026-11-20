#!/bin/bash

integration="${1:-}"

if [ "$integration" == "Linux" ] && [ -f "$BW_TESTS_ETC/variables.env" ]; then
  docker exec -u 0 bunkerweb-linux chmod 777 /etc/bunkerweb/variables.env
fi

# The extra BunkerWeb instance this category registers through the UI is started by run.sh once
# the stack is up -- see the "extra instance" block there. It needs the generated variables.env
# and the bw-universe network, and this hook runs before either exists.
