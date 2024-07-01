OPENRESTY_PREFIX=/usr/local/openresty

PREFIX ?=          /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR ?=     $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL ?= install

.PHONY: all test install lint

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)/$(LUA_LIB_DIR)/resty/lrucache
	$(INSTALL) lib/resty/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/
	$(INSTALL) lib/resty/lrucache/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/lrucache/

test: all lint
	PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$$PATH prove -I../test-nginx/lib -r t

lint:
	@! grep -P -n --color -- 'require.*?resty\.lrucache[^.]' t/*pureffi*/*.t || (echo "ERROR: Found pureffi tests requiring 'resty.lrucache'." > /dev/stderr; exit 1)
	@! grep -R -P -n --color --exclude-dir=pureffi --exclude=*mixed.t -- 'require.*?resty\.lrucache\.pureffi' t/*.t || (echo "ERROR: Found pure Lua tests requiring 'resty.lrucache.pureffi'." > /dev/stderr; exit 1)

