

# make clean
CLEANFILES = 

# make maintainer-clean
MAINTAINERCLEANFILES = \
	Makefile.in


noinst_PROGRAMS = afl_fuzzer

afl_fuzzer_SOURCES = \
	afl_fuzzer.cc

afl_fuzzer_LDADD = \
	$(GLOBAL_LDADD) \
	$(CURL_LDADD) \
	$(GEOIP_LDFLAGS) $(GEOIP_LDADD) \
	$(PCRE_LDADD) \
	$(PCRE2_LDADD) \
	$(YAJL_LDFLAGS) $(YAJL_LDADD) \
	$(LMDB_LDFLAGS) $(LMDB_LDADD) \
	$(MAXMIND_LDFLAGS) $(MAXMIND_LDADD) \
	$(SSDEEP_LDFLAGS) $(SSDEEP_LDADD) \
	$(LUA_LDFLAGS) $(LUA_LDADD) \
	$(LIBXML2_LDADD) \
	$(top_builddir)/src/.libs/libmodsecurity.a \
	$(top_builddir)/others/libinjection.la \
	$(top_builddir)/others/libmbedtls.la


afl_fuzzer_CPPFLAGS = \
	-Icommon \
	-I../ \
	-I../../ \
	-O0 \
	-g \
	-I$(top_builddir)/headers \
	$(CURL_CFLAGS) \
	$(GEOIP_CFLAGS) \
	$(MAXMIND_CFLAGS) \
	$(GLOBAL_CPPFLAGS) \
	$(MODSEC_NO_LOGS) \
	$(YAJL_CFLAGS) \
	$(LMDB_CFLAGS) \
	$(PCRE_CFLAGS) \
	$(PCRE2_CFLAGS) \
	$(LIBXML2_CFLAGS)
