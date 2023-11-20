OPENRESTY_PREFIX=/usr/local/openresty

PREFIX ?=          /usr/local
LUA_INCLUDE_DIR ?= $(PREFIX)/include
LUA_LIB_DIR ?=     $(PREFIX)/lib/lua/$(LUA_VERSION)
INSTALL ?= install

.PHONY: all test install

SRC := resty_signal.c
OBJ := $(SRC:.c=.o)

C_SO_NAME := librestysignal.so

CFLAGS := -O3 -g -Wall -fpic

LDFLAGS := -shared
# on Mac OS X, one should set instead:
# LDFLAGS := -bundle -undefined dynamic_lookup

MY_CFLAGS := $(CFLAGS)
MY_LDFLAGS := $(LDFLAGS) -fvisibility=hidden

test := t

.PHONY = all test clean install

all : $(C_SO_NAME)

${OBJ} : %.o : %.c
	$(CC) $(MY_CFLAGS) -c $<

${C_SO_NAME} : ${OBJ}
	$(CC) $(MY_LDFLAGS) $^ -o $@

#export TEST_NGINX_NO_CLEAN=1

clean:; rm -f *.o *.so a.out *.d

install:
	$(INSTALL) -d $(DESTDIR)$(LUA_LIB_DIR)/resty
	$(INSTALL) lib/resty/*.lua $(DESTDIR)$(LUA_LIB_DIR)/resty
	$(INSTALL) $(C_SO_NAME) $(DESTDIR)$(LUA_LIB_DIR)/

test : all
	PATH=$(OPENRESTY_PREFIX)/nginx/sbin:$$PATH prove -I../test-nginx/lib -r $(test)
