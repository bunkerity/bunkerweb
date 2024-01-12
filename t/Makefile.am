include $(top_srcdir)/common.mk

all-local:
		cd libtap && $(MAKE) $(AM_MAKEFLAGS) all
clean-local:
		cd libtap && $(MAKE) $(AM_MAKEFLAGS) clean

AM_LDFLAGS = $(top_builddir)/src/libmaxminddb.la
CFLAGS += -I$(top_srcdir)/src

noinst_LTLIBRARIES = libmmdbtest.la
libmmdbtest_la_SOURCES = maxminddb_test_helper.c maxminddb_test_helper.h

EXTRA_DIST = compile_c++_t.pl external_symbols_t.pl  mmdblookup_t.pl \
	     libtap/COPYING libtap/INSTALL libtap/Makefile libtap/README.md \
	     libtap/tap.c libtap/tap.h maxmind-db

check_PROGRAMS = \
	bad_pointers_t bad_databases_t basic_lookup_t data_entry_list_t \
    data-pool-t data_types_t dump_t get_value_t get_value_pointer_bug_t \
	ipv4_start_cache_t ipv6_lookup_in_ipv4_t metadata_t metadata_pointers_t \
	no_map_get_value_t read_node_t threads_t version_t

data_pool_t_LDFLAGS = $(AM_LDFLAGS) -lm
data_pool_t_SOURCES = data-pool-t.c ../src/data-pool.c

threads_t_CFLAGS = $(CFLAGS) -pthread

TESTS = $(check_PROGRAMS) compile_c++_t.pl external_symbols_t.pl mmdblookup_t.pl

LDADD = libmmdbtest.la libtap/libtap.a
