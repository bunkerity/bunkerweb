INST_PREFIX ?= /usr
INST_LIBDIR ?= $(INST_PREFIX)/lib/lua/5.1
INST_LUADIR ?= $(INST_PREFIX)/share/lua/5.1
INSTALL ?= install


### lint:         Lint Lua source code
.PHONY: lint
lint:
	luacheck -q resty

### test:         Run test suite. Use test=... for specific tests
.PHONY: test
test:
	TEST_NGINX_LOG_LEVEL=info \
	prove -I. -I../test-nginx/lib -r t/


### install:      Install the library to runtime
.PHONY: install
install:
	$(INSTALL) -d $(INST_LUADIR)/resty/
	$(INSTALL) resty/*.lua $(INST_LUADIR)/resty/


### help:         Show Makefile rules
.PHONY: help
help:
	@echo Makefile rules:
	@echo
	@grep -E '^### [-A-Za-z0-9_]+:' Makefile | sed 's/###/   /'
