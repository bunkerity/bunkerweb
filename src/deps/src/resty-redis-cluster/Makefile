LUA_VERSION      ?= 5.1
OPENRESTY_PREFIX ?= /usr/local/openresty
NGINX_SBIN       ?= $(OPENRESTY_PREFIX)/nginx/sbin
PREFIX           ?= /usr/local
LUA_INCLUDE_DIR  ?= $(PREFIX)/include
LUA_LIB_DIR      ?= $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL          ?= install

# Test::Nginx takes `nginx` from PATH, or from TEST_NGINX_BINARY. A distribution
# nginx has no ngx_lua, so pin the OpenResty build instead of trusting PATH.
TEST_ENV = PATH=$(NGINX_SBIN):$$PATH TEST_NGINX_BINARY=$(NGINX_SBIN)/nginx

.PHONY: all test test-redis7 install

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)$(LUA_LIB_DIR)/resty
	$(INSTALL) lib/resty/*.lua $(DESTDIR)$(LUA_LIB_DIR)/resty

test: all
	$(TEST_ENV) prove -r t

# z-recover.t starts the 6.2 fixture itself and clashes with the fixture of the
# job, so the 7.2 jobs leave it out. Every other file runs there.
REDIS7_SKIP  ?= t/z-recover.t
REDIS7_TESTS ?= $(filter-out $(REDIS7_SKIP),$(wildcard t/*.t))

test-redis7: all
	$(TEST_ENV) prove $(REDIS7_TESTS)
