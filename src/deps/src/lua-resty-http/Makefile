OPENRESTY_PREFIX=/usr/local/openresty

PREFIX 			?= /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR     ?= $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL         ?= install
TEST_FILE       ?= t

export PATH := $(OPENRESTY_PREFIX)/nginx/sbin:$(PATH)
PROVE=TEST_NGINX_NO_SHUFFLE=1 prove -I../test-nginx/lib -r $(TEST_FILE)

# Keep in sync with .luacov, so that we show the right amount of output
LUACOV_NUM_MODULES ?= 3

.PHONY: all test install

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)/$(LUA_LIB_DIR)/resty
	$(INSTALL) lib/resty/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/

test: all
	$(PROVE)

coverage: all
	@rm -f luacov.stats.out
	TEST_COVERAGE=1 $(PROVE)
	@luacov
	@tail -$$(( $(LUACOV_NUM_MODULES) + 5)) luacov.report.out

check:
	luacheck lib
