include $(top_srcdir)/common.mk

AM_LDFLAGS = $(top_builddir)/src/libmaxminddb.la

bin_PROGRAMS = mmdblookup

if WINDOWS
AM_LDFLAGS += -municode
endif

if !WINDOWS
AM_CPPFLAGS += -pthread
AM_LDFLAGS += -pthread
endif
