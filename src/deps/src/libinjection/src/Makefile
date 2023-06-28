
AR ?= ar
# MAC
# AR=libtool -static

CC ?= cc
LD ?= ld
CFLAGS=-Wall -Wextra -Werror -pedantic -ansi -g -O3 -fPIC

INSTALL=install
PREFIX=/usr/local
INCLUDE_DIR=${PREFIX}/include
LIB_DIR=${PREFIX}/lib

LIBNAME=injection
STATICLIB_SUFFIX=a
STATICLIB=lib${LIBNAME}.${STATICLIB_SUFFIX}

SHAREDLIB_SUFFIX=so
SHAREDLIB=lib${LIBNAME}.${SHAREDLIB_SUFFIX}

HEADERS=libinjection.h libinjection_sqli.h libinjection_sqli_data.h libinjection_html5.h libinjection_xss.h

SOURCES=libinjection_sqli.c \
	libinjection_html5.c \
	libinjection_xss.c

OBJECTS=libinjection_sqli.o \
	libinjection_html5.o \
	libinjection_xss.o

SAMPLES=html5 sqli fptool
TESTDRIVERS=reader testdriver testspeedxss testspeedsqli

all: ${SHAREDLIB} ${STATICLIB}
#all: ${STATICLIB}

samples: ${SAMPLES}
.PHONY: samples

fingerprints.txt: make_parens.py
	./make_parens.py < fingerprints.txt > fingerprints2.txt
	mv fingerprints2.txt fingerprints.txt

fingerprints:
	./make_parens.py < fingerprints.txt > fingerprints2.txt
	mv fingerprints2.txt fingerprints.txt
.PHONY: fingerprints

sqlparse_data.json: sqlparse_map.py fingerprints
	./sqlparse_map.py > sqlparse_data.json

libinjection_sqli_data.h: sqlparse2c.py sqlparse_data.json
	./sqlparse2c.py < sqlparse_data.json > libinjection_sqli_data.h

libinjection_sqli.o: libinjection.h libinjection_sqli.c libinjection_sqli.h libinjection_sqli_data.h
	${CC} ${CFLAGS} -c -o libinjection_sqli.o libinjection_sqli.c

libinjection_xss.o: libinjection.h libinjection_xss.c libinjection_xss.h libinjection_html5.h
	${CC} ${CFLAGS} -c -o libinjection_xss.o libinjection_xss.c

libinjection_html5.o: libinjection.h libinjection_html5.c libinjection_html5.h
	${CC} ${CFLAGS} -c -o libinjection_html5.o libinjection_html5.c

${SHAREDLIB}: ${OBJECTS}
	$(CC) $+ -shared -lc -o $@

${STATICLIB}: ${OBJECTS}
	rm -f ${STATICLIB}
	${AR} -r ${STATICLIB} ${OBJECTS}

check: ${TESTDRIVERS}
	@./test-driver.sh test-unit.sh
	@./test-driver.sh test-samples-sqli-negative.sh
	@./test-driver.sh test-samples-sqli-positive.sh
	@./test-driver.sh test-samples-xss-positive.sh

# remove speed checks for now
#	@./test-driver.sh test-speed-xss.sh
#	@./test-driver.sh test-speed-sqli.sh

test: check
.PHONY: check test

reader: reader.c ${STATICLIB}
	${CC} ${CFLAGS} -o reader reader.c -L. ${STATICLIB}

sqli: sqli_cli.c ${STATICLIB}
	rm -f sqli
	${CC} ${CFLAGS} -o sqli sqli_cli.c -L. ${STATICLIB}

html5: html5_cli.c ${STATICLIB}
	${CC} ${CFLAGS} -o html5 html5_cli.c -L. ${STATICLIB}

testdriver: testdriver.c ${STATICLIB}
	${CC} ${CFLAGS} -o testdriver testdriver.c -L. ${STATICLIB}

testspeedsqli: test_speed_sqli.c ${STATICLIB}
	${CC} ${CFLAGS} -o testspeedsqli test_speed_sqli.c -L. ${STATICLIB}

testspeedxss: test_speed_xss.c ${STATICLIB}
	${CC} ${CFLAGS} -o testspeedxss test_speed_xss.c -L. ${STATICLIB}

fptool: fptool.c ${STATICLIB}
	${CC} ${CFLAGS} -o fptool fptool.c -L. ${STATICLIB}

install: ${STATICLIB}
	${INSTALL} -d ${INCLUDE_DIR}
	${INSTALL} -c ${HEADERS} ${INCLUDE_DIR}
	${INSTALL} -d ${LIB_DIR}
	${INSTALL} -c ${STATICLIB} ${LIB_DIR}

.PHONY: install

clean:
	@rm -f *.so *.a *.o *.dylib *.lo *.gch
	@rm -f *~
	@rm -f *.log
	@rm -f ${SAMPLES} ${TESTDRIVERS}
	@rm -f *.gcno
	@rm -rf *.dSYM


#---- CLANG STATIC ANALYZER
#
#
#
# We are not using scan-analyze since it depends on perl
# Using clang directly produces text output which is fine for
# automated testing.  Oddly -Werror doesn't work here, and
# we have to test if any output occurred or not.  This done by
# piping output to a file and then checking what it contains.
#
# Open to better ideas here.
#

# ubuntu adds "-3.7" suffix
CLANG_VERSION=

analyze:
	rm -f /tmp/libinjection-analyze.txt
	clang${CLANG_VERSION} \
	-I. --analyze \
	-Xanalyzer -analyzer-checker=alpha.core.BoolAssignment \
	-Xanalyzer -analyzer-checker=alpha.core.CastSize \
	-Xanalyzer -analyzer-checker=alpha.core.FixedAddr \
	-Xanalyzer -analyzer-checker=alpha.core.IdenticalExpr \
	-Xanalyzer -analyzer-checker=alpha.core.PointerArithm \
	-Xanalyzer -analyzer-checker=alpha.core.PointerSub \
	-Xanalyzer -analyzer-checker=alpha.core.SizeofPtr \
	-Xanalyzer -analyzer-checker=alpha.core.TestAfterDivZero \
	-Xanalyzer -analyzer-checker=alpha.security.ArrayBound \
	-Xanalyzer -analyzer-checker=alpha.security.MallocOverflow \
	-Xanalyzer -analyzer-checker=alpha.security.ReturnPtrRange \
	-Xanalyzer -analyzer-checker=alpha.unix.cstring.BufferOverlap \
	-Xanalyzer -analyzer-checker=alpha.unix.cstring.OutOfBounds \
	libinjection*.c 2>&1 | tee /tmp/libinjection-analyze.txt
	test ! -s /tmp/libinjection-analyze.txt

.PHONY: analyze
