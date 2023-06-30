

bin_PROGRAMS = modsec-rules-check

modsec_rules_check_SOURCES = \
        rules-check.cc

modsec_rules_check_LDADD = \
	$(top_builddir)/src/.libs/libmodsecurity.la \
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

modsec_rules_check_LDFLAGS = \
	$(GEOIP_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(LDFLAGS) \
	$(LMDB_LDFLAGS) \
	$(LUA_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(YAJL_LDFLAGS)

modsec_rules_check_CPPFLAGS = \
	-std=c++11 \
	-I$(top_builddir)/headers \
	$(GLOBAL_CPPFLAGS) \
	$(PCRE_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(MAXMIND_CFLAGS) \
	$(LIBXML2_CFLAGS)

MAINTAINERCLEANFILES = \
        Makefile.in

