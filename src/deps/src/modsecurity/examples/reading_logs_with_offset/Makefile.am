

noinst_PROGRAMS = read

read_SOURCES = \
	read.cc

read_LDADD = \
	$(CURL_LDADD) \
	$(GEOIP_LDADD) \
	$(MAXMIND_LDADD) \
	$(GLOBAL_LDADD) \
	$(LIBXML2_LDADD) \
	$(LMDB_LDADD) \
	$(LUA_LDADD) \
	$(PCRE_LDADD) \
	$(PCRE2_LDADD) \
	$(SSDEEP_LDADD) \
	$(YAJL_LDADD)

read_LDFLAGS = \
	-L$(top_builddir)/src/.libs/ \
	$(GEOIP_LDFLAGS) \
	-lmodsecurity \
	-lm \
	-lstdc++ \
	$(LMDB_LDFLAGS) \
	$(LUA_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(YAJL_LDFLAGS)

read_CPPFLAGS = \
	$(GLOBAL_CFLAGS) \
	-I$(top_builddir)/headers \
	-I$(top_builddir) \
	-g \
	-I../others \
	-fPIC \
	-O3 \
	$(CURL_CFLAGS) \
	$(GEOIP_CFLAGS) \
	$(MAXMIND_CFLAGS) \
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


