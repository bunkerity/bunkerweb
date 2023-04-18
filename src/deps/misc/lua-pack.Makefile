LUA ?= lua5.1
LUA_LIBDIR ?= $(shell pkg-config $(LUA) --libs)
LUA_INCDIR ?= $(shell pkg-config $(LUA) --cflags)

LIBFLAG ?= -shared
CFLAGS ?= -std=c99 -O2 -Wall

.PHONY: all clean install

all: lua_pack.so

lua_pack.so: lua_pack.o
	$(CC) $(LIBFLAG) $(LUA_LIBDIR) $< -o $@

%.o: %.c
	$(CC) -c $(CFLAGS) -fPIC $(LUA_INCDIR) $< -o $@

install: lua_pack.so
	cp lua_pack.so $(INST_LIBDIR)

clean:
	rm -f *.so *.o *.rock

# eof