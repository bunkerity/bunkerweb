OPENRESTY_PREFIX=/usr/local/openresty

#LUA_VERSION := 5.1
PREFIX ?=          /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR ?=     $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL ?= install

.PHONY: all test install

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)$(LUA_LIB_DIR)/resty/core/
	$(INSTALL) -d $(DESTDIR)$(LUA_LIB_DIR)/ngx/
	$(INSTALL) -d $(DESTDIR)$(LUA_LIB_DIR)/ngx/ssl
	$(INSTALL) lib/resty/*.lua $(DESTDIR)$(LUA_LIB_DIR)/resty/
	$(INSTALL) lib/resty/core/*.lua $(DESTDIR)$(LUA_LIB_DIR)/resty/core/
	$(INSTALL) lib/ngx/*.lua $(DESTDIR)$(LUA_LIB_DIR)/ngx/
	$(INSTALL) lib/ngx/ssl/*.lua $(DESTDIR)$(LUA_LIB_DIR)/ngx/ssl/
ifeq ($(LUA_LIB_DIR),/usr/local/lib/lua/)
	@echo
	@printf "\033[33mPLEASE NOTE: \033[0m\n"
	@printf "\033[33mThe necessary lua_package_path directive needs to be added to nginx.conf\033[0m\n"
	@printf "\033[33min the http context, because \"/usr/local/lib/lua/\" is not in LuaJIT’s default search path.\033[0m\n"
	@printf "\033[33mRefer to the Installation section of README.markdown.\033[0m\n"
endif

test: all
	PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$$PATH prove -I../test-nginx/lib -r t

