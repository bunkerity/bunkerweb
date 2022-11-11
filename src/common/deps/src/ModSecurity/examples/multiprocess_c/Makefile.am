

noinst_PROGRAMS = multi

multi_SOURCES = \
	multi.c

multi_LDADD = \
	$(SSDEEP_LDADD) \
	$(LUA_LDADD) \
	$(MAXMIND_LDADD) \
	$(GLOBAL_LDADD)

multi_LDFLAGS = \
	-L$(top_builddir)/src/.libs/ \
	$(GEOIP_LDFLAGS) \
	-lmodsecurity \
	-lpthread \
	-lm \
	-lstdc++ \
	$(LUA_LDFLAGS) \
	$(SSDEEP_LDFLAGS) \
	$(MAXMIND_LDFLAGS) \
	$(YAJL_LDFLAGS)

multi_CFLAGS = \
	-I$(top_builddir)/headers \
	-I$(top_builddir) \
	$(GLOBAL_CFLAGS)

MAINTAINERCLEANFILES = \
	Makefile.in


