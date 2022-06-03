

noinst_PROGRAMS = benchmark

benchmark_SOURCES = \
        benchmark.cc

benchmark_LDADD = \
	$(top_builddir)/src/.libs/libmodsecurity.a \
	$(CURL_LDADD) \
	$(GEOIP_LDADD) \
	$(MAXMIND_LDADD) \
	$(PCRE_LDADD) \
	$(YAJL_LDADD) \
	$(LMDB_LDADD) \
	$(SSDEEP_LDADD) \
	$(LUA_LDADD) \
	$(LIBXML2_LDADD) \
	$(GLOBAL_LDADD)

benchmark_LDFLAGS = \
	$(top_builddir)/src/.libs/libmodsecurity.a \
	$(GEOIP_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(YAJL_LDFLAGS) \
	$(LMDB_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(LUA_LDFLAGS)

benchmark_CPPFLAGS = \
	-std=c++11 \
	-I$(top_builddir)/headers \
	$(GLOBAL_CPPFLAGS) \
	$(PCRE_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(LIBXML2_CFLAGS)

MAINTAINERCLEANFILES = \
        Makefile.in

