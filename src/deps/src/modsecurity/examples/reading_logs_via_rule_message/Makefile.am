

noinst_PROGRAMS = simple_request

simple_request_SOURCES = \
	simple_request.cc

simple_request_LDADD = \
	$(CURL_LDADD) \
	$(GEOIP_LDADD) \
	$(GLOBAL_LDADD) \
	$(LIBXML2_LDADD) \
	$(LMDB_LDADD) \
	$(MAXMIND_LDADD) \
	$(LUA_LDADD) \
	$(PCRE_LDADD) \
	$(PCRE2_LDADD) \
	$(SSDEEP_LDADD) \
	$(YAJL_LDADD)

simple_request_LDFLAGS = \
	-L$(top_builddir)/src/.libs/ \
	$(GEOIP_LDFLAGS) \
	-lmodsecurity \
	-lpthread \
	-lm \
	-lstdc++ \
	$(LMDB_LDFLAGS) \
	$(LUA_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(YAJL_LDFLAGS)

simple_request_CPPFLAGS = \
	$(GLOBAL_CFLAGS) \
	-I$(top_builddir)/headers \
	-I$(top_builddir) \
	-g \
	-I../others \
	-fPIC \
	-O3 \
	$(CURL_CFLAGS) \
	$(GEOIP_CFLAGS) \
	$(GLOBAL_CPPFLAGS) \
	$(MODSEC_NO_LOGS) \
	$(YAJL_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(LUA_CFLAGS) \
	$(PCRE_CFLAGS) \
	$(PCRE2_CFLAGS) \
	$(LIBXML2_CFLAGS)


MAINTAINERCLEANFILES = \
	Makefile.in


