# Default prefix
PREFIX = /usr/local

# System's lua directory (where Lua libraries are installed)
LUA_DIR= $(PREFIX)/share/lua/5.1

LUAS= src/logging/console.lua src/logging/email.lua src/logging/file.lua src/logging/rolling_file.lua src/logging/socket.lua src/logging/sql.lua src/logging/nginx.lua src/logging/rsyslog.lua src/logging/envconfig.lua
ROOT_LUAS= src/logging.lua

build clean:

install:
	mkdir -p $(LUA_DIR)/logging
	cp $(LUAS) $(LUA_DIR)/logging
	cp $(ROOT_LUAS) $(LUA_DIR)

test:
	cd tests && ./run_tests.sh
	cd tests && LUA_INIT="_G.debug = nil" ./run_tests.sh

lint:
	luacheck .
