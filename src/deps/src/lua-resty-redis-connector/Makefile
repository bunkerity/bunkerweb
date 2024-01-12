SHELL := /bin/bash # Cheat by using bash :)

OPENRESTY_PREFIX    = /usr/local/openresty

TEST_FILE          ?= t
TMP_DIR			   ?= /tmp

REDIS_CMD           = redis-server
SENTINEL_CMD        = $(REDIS_CMD) --sentinel

REDIS_SOCK          = /redis.sock
REDIS_PID           = /redis.pid
REDIS_LOG           = /redis.log
REDIS_PREFIX        = $(TMP_DIR)/redis-

# Overrideable redis test variables
TEST_REDIS_PORT              ?= 6380
TEST_REDIS_PORT_SL1          ?= 6381
TEST_REDIS_PORT_SL2          ?= 6382
TEST_REDIS_PORT_AUTH         ?= 6383
TEST_REDIS_PORTS             ?= $(TEST_REDIS_PORT) $(TEST_REDIS_PORT_SL1) $(TEST_REDIS_PORT_SL2)
TEST_REDIS_PORTS_ALL         ?= $(TEST_REDIS_PORTS) $(TEST_REDIS_PORT_AUTH)
TEST_REDIS_DATABASE          ?= 1
TEST_REDIS_SOCKET            ?= $(REDIS_PREFIX)$(TEST_REDIS_PORT)$(REDIS_SOCK)

REDIS_SLAVE_ARG                     := --slaveof 127.0.0.1 $(TEST_REDIS_PORT)
REDIS_CLI                           := redis-cli -p $(TEST_REDIS_PORT) -n $(TEST_REDIS_DATABASE)

# Overrideable redis + sentinel test variables
TEST_SENTINEL_PORT1           ?= 6390
TEST_SENTINEL_PORT2           ?= 6391
TEST_SENTINEL_PORT3           ?= 6392
TEST_SENTINEL_PORT_AUTH       ?= 6393
TEST_SENTINEL_PORTS           ?= $(TEST_SENTINEL_PORT1) $(TEST_SENTINEL_PORT2) $(TEST_SENTINEL_PORT3)
TEST_SENTINEL_PORTS_ALL       ?= $(TEST_SENTINEL_PORTS) $(TEST_SENTINEL_PORT_AUTH)
TEST_SENTINEL_MASTER_NAME     ?= mymaster
TEST_SENTINEL_PROMOTION_TIME  ?= 20

# Command line arguments for redis tests
TEST_REDIS_VARS     = PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$(PATH) \
TEST_NGINX_REDIS_PORT=$(TEST_REDIS_PORT) \
TEST_NGINX_REDIS_PORT_SL1=$(TEST_REDIS_PORT_SL1) \
TEST_NGINX_REDIS_PORT_SL2=$(TEST_REDIS_PORT_SL2) \
TEST_NGINX_REDIS_PORT_AUTH=$(TEST_REDIS_PORT_AUTH) \
TEST_NGINX_REDIS_SOCKET=unix:$(TEST_REDIS_SOCKET) \
TEST_NGINX_REDIS_DATABASE=$(TEST_REDIS_DATABASE) \
TEST_NGINX_NO_SHUFFLE=1

# Command line arguments for sentinel tests
TEST_SENTINEL_VARS  = PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$(PATH) \
TEST_NGINX_REDIS_PORT=$(TEST_NGINX_REDIS_PORT) \
TEST_NGINX_REDIS_PORT_SL1=$(TEST_NGINX_REDIS_PORT_SL1) \
TEST_NGINX_REDIS_PORT_SL2=$(TEST_NGINX_REDIS_PORT_SL2) \
TEST_NGINX_SENTINEL_PORT1=$(TEST_NGINX_SENTINEL_PORT1) \
TEST_NGINX_SENTINEL_PORT2=$(TEST_NGINX_SENTINEL_PORT2) \
TEST_NGINX_SENTINEL_PORT3=$(TEST_NGINX_SENTINEL_PORT3) \
TEST_NGINX_SENTINEL_PORT_AUTH=$(TEST_NGINX_SENTINEL_AUTH) \
TEST_NGINX_SENTINEL_MASTER_NAME=$(TEST_NGINX_SENTINEL_MASTER_NAME) \
TEST_NGINX_REDIS_DATABASE=$(TEST_NGINX_REDIS_DATABASE) \
TEST_NGINX_NO_SHUFFLE=1

# Sentinel configuration can only be set by a config file
define TEST_SENTINEL_CONFIG
sentinel       monitor $(TEST_SENTINEL_MASTER_NAME) 127.0.0.1 $(TEST_REDIS_PORT) 2
sentinel       down-after-milliseconds $(TEST_SENTINEL_MASTER_NAME) 2000
sentinel       failover-timeout $(TEST_SENTINEL_MASTER_NAME) 10000
sentinel       parallel-syncs $(TEST_SENTINEL_MASTER_NAME) 5
endef
define TEST_SENTINEL_AUTH_CONFIG
sentinel       monitor $(TEST_SENTINEL_MASTER_NAME) 127.0.0.1 $(TEST_REDIS_PORT_AUTH) 1
endef

export TEST_SENTINEL_CONFIG TEST_SENTINEL_AUTH_CONFIG

SENTINEL_CONFIG_FILE = /tmp/sentinel-test-config
SENTINEL_AUTH_CONFIG_FILE = /tmp/sentinel-auth-test-config


PREFIX          ?= /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR     ?= $(PREFIX)/lib/lua/$(LUA_VERSION)
PROVE           ?= prove -I ../test-nginx/lib
INSTALL         ?= install

.PHONY: all install test test_all start_redis_instances stop_redis_instances \
	start_redis_instance stop_redis_instance cleanup_redis_instance flush_db \
	create_sentinel_config delete_sentinel_config check_ports test_redis \
	test_sentinel sleep

all: ;

install: all
	$(INSTALL) -d $(DESTDIR)/$(LUA_LIB_DIR)/resty/redis
	$(INSTALL) lib/resty/redis/*.lua $(DESTDIR)/$(LUA_LIB_DIR)/resty/redis

test: test_redis
test_all: start_redis_instances sleep test_redis stop_redis_instances

check:
	luacheck lib

sleep:
	sleep 3

start_redis_instances: check_ports create_sentinel_config
	$(REDIS_CMD) --version

	@$(foreach port,$(TEST_REDIS_PORTS), \
		[[ "$(port)" != "$(TEST_REDIS_PORT)" ]] && \
			SLAVE="$(REDIS_SLAVE_ARG)" || \
			SLAVE="" && \
		$(MAKE) start_redis_instance args="$$SLAVE" port=$(port) \
		prefix=$(REDIS_PREFIX)$(port) && \
	) true

	$(MAKE) start_redis_instance \
		args="--user redisuser on '>redisuserpass' '~*' '&*' '+@all'" \
		port=$(TEST_REDIS_PORT_AUTH) \
		prefix=$(REDIS_PREFIX)$(TEST_REDIS_PORT_AUTH)

	@$(foreach port,$(TEST_SENTINEL_PORTS), \
		$(MAKE) start_redis_instance \
		port=$(port) args="$(SENTINEL_CONFIG_FILE) --sentinel" \
		prefix=$(REDIS_PREFIX)$(port) && \
	) true

	$(MAKE) start_redis_instance \
		args="$(SENTINEL_AUTH_CONFIG_FILE) --sentinel --user sentineluser on '>sentineluserpass' '~*' '&*' '+@all'" \
		port=$(TEST_SENTINEL_PORT_AUTH) \
		prefix=$(REDIS_PREFIX)$(TEST_SENTINEL_PORT_AUTH)

stop_redis_instances: delete_sentinel_config
	-@$(foreach port,$(TEST_REDIS_PORTS_ALL) $(TEST_SENTINEL_PORTS_ALL), \
		$(MAKE) stop_redis_instance cleanup_redis_instance port=$(port) \
		prefix=$(REDIS_PREFIX)$(port) && \
	) true 2>&1 > /dev/null


start_redis_instance:
	-@echo "Starting redis on port $(port) with args: \"$(args)\""
	-@mkdir -p $(prefix)
	$(REDIS_CMD) $(args) \
		--pidfile $(prefix)$(REDIS_PID) \
		--bind 127.0.0.1 --port $(port) \
		--unixsocket $(prefix)$(REDIS_SOCK) \
		--unixsocketperm 777 \
		--dir $(prefix) \
		--logfile $(prefix)$(REDIS_LOG) \
		--loglevel debug \
		--daemonize yes

stop_redis_instance:
	-@echo "Stopping redis on port $(port)"
	-@[[ -f "$(prefix)$(REDIS_PID)" ]] && kill -QUIT \
	`cat $(prefix)$(REDIS_PID)` 2>&1 > /dev/null || true

cleanup_redis_instance: stop_redis_instance
	-@echo "Cleaning up redis files in $(prefix)"
	-@rm -rf $(prefix)

flush_db:
	-@echo "Flushing Redis DB"
	@$(REDIS_CLI) flushdb

create_sentinel_config:
	-@echo "Creating $(SENTINEL_CONFIG_FILE)"
	@echo "$$TEST_SENTINEL_CONFIG" > $(SENTINEL_CONFIG_FILE)
	-@echo "Creating $(SENTINEL_AUTH_CONFIG_FILE)"
	@echo "$$TEST_SENTINEL_AUTH_CONFIG" > $(SENTINEL_AUTH_CONFIG_FILE)

delete_sentinel_config:
	-@echo "Removing $(SENTINEL_CONFIG_FILE)"
	@rm -f $(SENTINEL_CONFIG_FILE)
	-@echo "Removing $(SENTINEL_AUTH_CONFIG_FILE)"
	@rm -f $(SENTINEL_AUTH_CONFIG_FILE)

check_ports:
	-@echo "Checking ports $(TEST_REDIS_PORTS_ALL) $(TEST_SENTINEL_PORTS_ALL)"
	@$(foreach port,$(TEST_REDIS_PORTS_ALL) $(TEST_SENTINEL_PORTS_ALL),! lsof -i :$(port) &&) true 2>&1 > /dev/null

test_redis: flush_db
	util/lua-releng
	@rm -f luacov.stats.out
	$(TEST_REDIS_VARS) $(PROVE) $(TEST_FILE)
	@luacov
	@tail -7 luacov.report.out

test_leak: flush_db
	$(TEST_REDIS_VARS) TEST_NGINX_CHECK_LEAK=1 $(PROVE) $(TEST_FILE)
