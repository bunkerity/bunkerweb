#
# this requires swig, and an installation of php (and php-dev tools)
#
# everything is copied and generating int the build directory
#

all: module

build/modules/libinjection.so: build build/libinjection.h build/libinjection_sqli.h build/libinjection_sqli.c build/libinjection_sqli_data.h build/config.m4 build/libinjection.i
	swig -version
	(cd build; swig -noproxy -php -Wall -Wextra libinjection.i)
	(cd build; phpize; ./configure ; make )

module: build/modules/libinjection.so

test: build/modules/libinjection.so
	mkdir -p build/tests
	./gentests.py
	cp testsupport.php build/
	(cd build; export NO_INTERACTION=1 && make test)
.PHONY: test

install: build/modules/libinjection.so
	(cd build; make install)

build:
	mkdir build

build/libinjection.h: ../src/libinjection.h
	cp ../src/libinjection.h build/libinjection.h

build/libinjection_sqli.c: ../src/libinjection_sqli.c
	cp ../src/libinjection_sqli.c build/libinjection_sqli.c

build/libinjection_sqli.h: ../src/libinjection_sqli.h
	cp ../src/libinjection_sqli.h build/libinjection_sqli.h

build/libinjection_sqli_data.h: ../src/libinjection_sqli_data.h
	cp ../src/libinjection_sqli_data.h build/libinjection_sqli_data.h

build/libinjection.i: libinjection.i
	cp libinjection.i build/

build/config.m4: config.m4
	mkdir -p build
	cp config.m4 build/config.m4


#
# old
#
words.php: Makefile json2php.py ../src/sqlparse_data.json
	./json2php.py < ../src/sqlparse_data.json > words.php

clean:
	rm -f *~ *.o *.so
	rm -f words.php
	rm -rf build
