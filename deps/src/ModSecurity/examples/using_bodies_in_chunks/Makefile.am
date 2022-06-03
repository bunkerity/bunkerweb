

noinst_PROGRAMS = simple_request

simple_request_SOURCES = \
	simple_request.cc

simple_request_LDADD = \
	$(top_builddir)/src/.libs/libmodsecurity.a \
	$(CURL_LDADD) \
	$(GEOIP_LDADD) \
	$(MAXMIND_LDADD) \
	$(GLOBAL_LDADD) \
	$(LIBXML2_LDADD) \
	$(LMDB_LDADD) \
	$(LUA_LDADD) \
	$(PCRE_LDADD) \
	$(SSDEEP_LDADD) \
	$(YAJL_LDADD)

simple_request_LDFLAGS = \
	$(GEOIP_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(LMDB_LDFLAGS) \
	-lpthread \
	$(LUA_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(YAJL_LDFLAGS)

simple_request_CPPFLAGS = \
	$(GLOBAL_CFLAGS) \
	-std=c++11 \
	-I$(top_builddir)/headers \
	-I$(top_builddir) \
	-g \
	-I../others \
	-fPIC \
	-O3 \
	$(GEOIP_CFLAGS) \
	$(MAXMIND_CFLAGS) \
	$(GLOBAL_CPPFLAGS) \
	$(MODSEC_NO_LOGS) \
	$(YAJL_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(LUA_CFLAGS) \
	$(PCRE_CFLAGS) \
	$(LIBXML2_CFLAGS)

MAINTAINERCLEANFILES = \
	Makefile.in


