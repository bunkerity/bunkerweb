ACLOCAL_AMFLAGS = -I build-aux/m4

MAINTAINERCLEANFILES = Makefile.in aclocal.m4 build-aux/compile \
		build-aux/config.guess build-aux/config.sub build-aux/depcomp \
		build-aux/install-sh build-aux/ltmain.sh build-aux/missing \
		config.h.in config.h.in~ configure build-aux/m4/libtool.m4 \
		build-aux/m4/ltoptions.m4 build-aux/m4/ltsugar.m4 \
		build-aux/m4/ltversion.m4 build-aux/m4/lt~obsolete.m4

SUBDIRS = src
if BUILD_FUZZTARGETS
SUBDIRS += src/fuzz
endif

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = libinjection.pc

# Standard stuff.
EXTRA_DIST = bootstrap COPYING README.md CHANGELOG.md

LIBTOOL_DEPS = @LIBTOOL_DEPS@
libtool: $(LIBTOOL_DEPS)
	$(SHELL) ./config.status libtool

tests: all
	@cd src && $(MAKE) $(AM_MAKEFLAGS) check
  
# Some helpers for compat
clang-asan: all
	@cd src && $(MAKE) $(AM_MAKEFLAGS) clang-asan

cppcheck: $(CPPCHECK)
	@cd src && $(MAKE) $(AM_MAKEFLAGS) cppcheck

ci: all
	@cd src && $(MAKE) $(AM_MAKEFLAGS) tests analyze cppcheck
