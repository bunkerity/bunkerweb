
if TEST_UTILITIES
export MAYBE_TEST = test
endif

if EXAMPLES
export MAYBE_EXAMPLES = examples
endif


SUBDIRS = \
	others \
	src \
	doc \
	tools \
	$(MAYBE_EXAMPLES) \
	$(MAYBE_TEST)



# make clean
CLEANFILES = 

ACLOCAL_AMFLAGS = -I build

# make maintainer-clean
MAINTAINERCLEANFILES = \
	aclocal.m4 \
	ar-lib \
	build/libtool.m4 \
	build/lt~obsolete.m4 \
	build/ltoptions.m4 \
	build/ltsugar.m4 \
	build/ltversion.m4 \
	coding-style.txt \
	compile \
	config.guess \
	config.sub \
	configure \
	cppcheck.txt \
	depcomp \
	install-sh \
	ltmain.sh \
	Makefile.in \
	missing \
	test/modsec-shared-collections \
	test/modsec-shared-collections-lock \
	test-suite-drd.log \
	test-suite-helgrind.log \
	test-suite-memcheck.log \
	ylwrap

parser:
	cat src/parser/seclang-parser.hh | sed "s/return \*new (yyas_<T> ()) T (t)/return *new (yyas_<T> ()) T (std::move((T\&)t))/g"  > src/parser/seclang-parser.hh.fix && mv src/parser/seclang-parser.hh.fix src/parser/seclang-parser.hh



cppcheck:
	@cppcheck -U YYSTYPE -U MBEDTLS_MD5_ALT -U MBEDTLS_SHA1_ALT \
		-D MS_CPPCHECK_DISABLED_FOR_PARSER -U YY_USER_INIT \
		--suppressions-list=./test/cppcheck_suppressions.txt \
		--inline-suppr \
		--enable=warning,style,performance,portability,unusedFunction,missingInclude \
		--inconclusive \
		--template="warning: {file},{line},{severity},{id},{message}" \
		-I headers -I . -I $(top_srcdir)/others -I $(top_srcdir)/src -I $(top_srcdir)/others/mbedtls/include \
		--error-exitcode=1 \
		-i "src/parser/seclang-parser.cc" -i "src/parser/seclang-scanner.cc" \
		-i others \
		--std=c++17 \
		--force --verbose .


check-static: cppcheck

check-style: check-coding-style

check-coding-style:
	@cpplint.py \
		$$(find . -name "*.h" -o -name "*.cc" | xargs) 2>&1 \
 		| egrep -v $$(echo -n "catchall" ; \
	  		for i in $$(cat test/coding_style_suppressions.txt); do echo -n "|"$$i; done) \
		| sed 's/^\./warning: ./g' > coding-style.txt
	-cat coding-style.txt


@VALGRIND_CHECK_RULES@
VALGRIND_SUPPRESSIONS_FILES = valgrind_suppressions.txt

LOG_DRIVER = env $(SHELL) $(top_srcdir)/test/custom-test-driver
AM_TESTS_ENVIRONMENT=AUTOMAKE_TESTS=true; export AUTOMAKE_TESTS;
LOG_COMPILER=test/test-suite.sh

TESTS=
include test/test-suite.in

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = modsecurity.pc
EXTRA_DIST = modsecurity.pc.in \
             modsecurity.conf-recommended \
             unicode.mapping

