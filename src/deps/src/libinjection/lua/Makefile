
# either works

# ubuntu
#LUA_FLAGS=-I/usr/include/lua5.1 -llua5.1
#LUA=/usr/bin/lua5.1

# ubuntu luajit 2
LUA_FLAGS=-I/usr/include/luajit-2.0 -lluajit-5.1
LUA=luajit

# centos and friends
#LUA_FLAGS=-I/usr/include/ -L/usr/lib64 -llua
#LUA=lua

SHARED=-shared -Wl,-soname,libinjection.so
CFLAGS= -O0 -g -Wall -Wextra -Wformat=2 -fPIC -fno-common
APPLE=$(shell uname -a | grep -c Darwin)

# MAC OS X - brew install luajit
ifeq ($(APPLE),1)
	SHARED=-dynamiclib
	LUA_FLAGS=-I/usr/local/include/luajit-2.0 -L/usr/local/lib -lluajit-5.1
	LUA=luajit
endif

# need to hack a linux version here
#
# MAC OS X: note using ".so" suffix NOT ".dylib"
libinjection.so: copy libinjection_wrap.c
	${CC} ${CFLAGS} -I. ${LUA_FLAGS} \
	${SHARED} libinjection_wrap.c libinjection_sqli.c libinjection_html5.c libinjection_xss.c -o libinjection.so

# build and run unit tests
# Uses a python helper to read the test files to generate
# a TAP test plan.  Easier that writing lots of LUA glue code
# and super-fast!
#
test-unit: libinjection.so lua-TestMore
	./make_test.py > unit-test.t
	LUA_PATH='?.lua;lua-TestMore/src/?.lua' ${LUA} unit-test.t

test: test-unit

libinjection_wrap.c: libinjection.i libinjection.h
	swig -version
	swig -lua -Wall -Wextra libinjection.i

sqlifingerprints.lua: generate_lua_fingerprints.py ../src/sqlparse_data.json
	./generate_lua_fingerprints.py > sqlifingerprints.lua

copy: 
	cp ../src/libinjection*.h ../src/libinjection*.c .
.PHONY: copy

sample: sqlifingerprints.lua
	${LUA} luatest.lua

# --depth 1 -- get without history
lua-TestMore:
	git clone --depth 1 https://github.com/fperrad/lua-TestMore.git

speed:
	${LUA} luatest.lua
clean:
	@rm -f *~
	@rm -rf *.dSYM *.so *.dylib
	@rm -f libinjection.h libinjection_sqli.c libinjection_sqli_data.h
	@rm -f sqlifingerprints.lua
	@rm -f unit-test.t
	@rm -f libinjection_sqli.c.*
	@rm -f junit*.xml
	@rm -f libinjection_wrap.c
