LT_CURRENT=3
LT_REVISION=9
LT_AGE=2

CPPCHECK=@CPPCHECK@
CPPCHECK_FLAGS=--quiet --enable=all --inconclusive --error-exitcode=2 \
        --std=c89 --std=c++11 \
        --suppress=variableScope  \
        --template '{file}:{line} {severity} {id} {message}'

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

check: reader testdriver testspeedxss testspeedsqli teststackxss
	@./test-driver.sh test-unit.sh
	@./test-driver.sh test-samples-sqli-negative.sh
	@./test-driver.sh test-samples-sqli-positive.sh
	@./test-driver.sh test-samples-xss-positive.sh
	@./test-driver.sh teststackxss

analyze:
	$(RM) /tmp/libinjection-analyze.txt
	$(CLANG) -I. --analyze \
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


cppcheck:
	$(CPPCHECK) $(CPPCHECK_FLAGS) .

clang-asan: testdriver
	$(RM) libinjection.info
	$(LIBTOOL) $(AM_LIBTOOLFLAGS) $(LIBTOOLFLAGS) --mode=execute ./$< ../tests/test-*.txt

lib_LTLIBRARIES = libinjection.la

libinjection_la_LDFLAGS = -rpath '$(libdir)' -version-info $(LT_CURRENT):$(LT_REVISION):$(LT_AGE)

libinjection_la_SOURCES = libinjection_sqli_data.h libinjection_sqli.c libinjection_html5.c libinjection_xss.c

include_HEADERS= libinjection.h libinjection_sqli.h libinjection_sqli_data.h libinjection_html5.h libinjection_xss.h

noinst_PROGRAMS = html5 sqli fptool reader testdriver testspeedxss testspeedsqli teststackxss

# Samples
html5_SOURCES = html5_cli.c
html5_LDADD = libinjection.la
sqli_SOURCES = sqli_cli.c
sqli_LDADD = libinjection.la
fptool_SOURCES = fptool.c
fptool_LDADD = libinjection.la

# Test Drivers
reader_SOURCES = reader.c
reader_LDADD = libinjection.la
testdriver_SOURCES = testdriver.c
testdriver_LDADD = libinjection.la
testspeedxss_SOURCES = test_speed_xss.c
testspeedxss_LDADD = libinjection.la
testspeedsqli_SOURCES = test_speed_sqli.c
testspeedsqli_LDADD = libinjection.la
teststackxss_SOURCES = test_stack_xss.c
teststackxss_LDADD = libinjection.la
teststackxss_CFLAGS = -O0