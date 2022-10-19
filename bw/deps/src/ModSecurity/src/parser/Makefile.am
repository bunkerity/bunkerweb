
noinst_LTLIBRARIES = libmodsec_parser.la

BUILT_SOURCES = \
	seclang-parser.cc \
	test.cc

libmodsec_parser_la_SOURCES = \
	seclang-parser.yy \
	seclang-scanner.ll \
	test.cc

libmodsec_parser_la_CPPFLAGS = \
	-std=c++11 \
	-I../.. \
	-I../../headers \
	-I../../others \
	-std=c++11 \
	-I.. \
	-g \
	-fPIC \
	-O3 \
	$(GEOIP_CFLAGS) \
	$(GLOBAL_CPPFLAGS) \
	$(MODSEC_NO_LOGS) \
	$(YAJL_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(PCRE_CFLAGS) \
	$(LIBXML2_CFLAGS)

test.cc: seclang-parser.hh
	cat seclang-parser.hh | sed "s/return \*new (yyas_<T> ()) T (t)/return *new (yyas_<T> ()) T (std::move((T\&)t))/g"  > seclang-parser.hh.fix && mv seclang-parser.hh.fix seclang-parser.hh
	touch test.cc

CLEANFILES = test.cc \
	seclang-scanner.cc \
	seclang-parser.cc \
	seclang-parser.hh \
	location.hh \
	position.hh \
	stack.hh

EXTRA_DIST = $(CLEANFILES)

DISTCLAEN =
