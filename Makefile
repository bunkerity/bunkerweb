OPENRESTY_PREFIX=/usr/local/openresty

PREFIX ?=          /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR ?=     $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL ?= install

SHELL:=/bin/bash

.PHONY: all test install lint

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)/$(LUA_LIB_DIR)/resty/lrucache
	$(INSTALL) lib/resty/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/
	$(INSTALL) lib/resty/lrucache/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/lrucache/
ifeq ($(LUA_LIB_DIR),/usr/local/lib/lua/)
	@echo
	@echo -e "\033[33mPLEASE NOTE: \033[0m"
	@echo -e "\033[33mThe necessary lua_package_path directive needs to be added to nginx.conf\033[0m"
	@echo -e "\033[33min the http context, because \"/usr/local/lib/lua/\" is not in LuaJIT’s default search path.\033[0m"
	@echo -e "\033[33mRefer to the Installation section of README.markdown.\033[0m"
endif

test: all lint
	PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$$PATH prove -I../test-nginx/lib -r t

lint:
	@! grep -P -n --color -- 'require.*?resty\.lrucache[^.]' t/*pureffi*/*.t || (echo "ERROR: Found pureffi tests requiring 'resty.lrucache'." > /dev/stderr; exit 1)
	@! grep -R -P -n --color --exclude-dir=pureffi --exclude=*mixed.t -- 'require.*?resty\.lrucache\.pureffi' t/*.t || (echo "ERROR: Found pure Lua tests requiring 'resty.lrucache.pureffi'." > /dev/stderr; exit 1)

