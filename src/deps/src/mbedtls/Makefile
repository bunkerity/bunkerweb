DESTDIR=/usr/local
PREFIX=mbedtls_
PERL ?= perl

ifneq (,$(filter-out lib library/%,$(or $(MAKECMDGOALS),all)))
    ifeq (,$(wildcard framework/exported.make))
        # Use the define keyword to get a multi-line message.
        # GNU make appends ".  Stop.", so tweak the ending of our message accordingly.
        ifneq (,$(wildcard .git))
            define error_message
${MBEDTLS_PATH}/framework/exported.make not found (and does appear to be a git checkout). Run `git submodule update --init` from the source tree to fetch the submodule contents.
This is a fatal error
            endef
        else
            define error_message
${MBEDTLS_PATH}/framework/exported.make not found (and does not appear to be a git checkout). Please ensure you have downloaded the right archive from the release page on GitHub.
            endef
        endif
        $(error $(error_message))
    endif
    include framework/exported.make
endif

.SILENT:

.PHONY: all no_test programs lib tests install uninstall clean test check lcov apidoc apidoc_clean

all: programs tests
	$(MAKE) post_build

no_test: programs

programs: lib mbedtls_test
	$(MAKE) -C programs

ssl-opt: lib mbedtls_test
	$(MAKE) -C programs ssl-opt
	$(MAKE) -C tests ssl-opt

lib:
	$(MAKE) -C library

tests: lib mbedtls_test
	$(MAKE) -C tests

mbedtls_test:
	$(MAKE) -C tests mbedtls_test

.PHONY: FORCE
FORCE:

library/%: FORCE
	$(MAKE) -C library $*
programs/%: FORCE
	$(MAKE) -C programs $*
tests/%: FORCE
	$(MAKE) -C tests $*

.PHONY: generated_files
generated_files: library/generated_files
generated_files: programs/generated_files
generated_files: tests/generated_files
generated_files: visualc_files

# Set GEN_FILES to the empty string to disable dependencies on generated
# source files. Then `make generated_files` will only build files that
# are missing, it will not rebuilt files that are present but out of date.
# This is useful, for example, if you have a source tree where
# `make generated_files` has already run and file timestamps reflect the
# time the files were copied or extracted, and you are now in an environment
# that lacks some of the necessary tools to re-generate the files.
# If $(GEN_FILES) is non-empty, the generated source files' dependencies
# are treated ordinarily, based on file timestamps.
GEN_FILES ?=

# In dependencies where the target is a configuration-independent generated
# file, use `TARGET: $(gen_file_dep) DEPENDENCY1 DEPENDENCY2 ...`
# rather than directly `TARGET: DEPENDENCY1 DEPENDENCY2 ...`. This
# enables the re-generation to be turned off when GEN_FILES is disabled.
ifdef GEN_FILES
gen_file_dep =
else
# Order-only dependency: generate the target if it's absent, but don't
# re-generate it if it's present but older than its dependencies.
gen_file_dep = |
endif

.PHONY: visualc_files
VISUALC_FILES = visualc/VS2017/mbedTLS.sln visualc/VS2017/mbedTLS.vcxproj
# TODO: $(app).vcxproj for each $(app) in programs/
visualc_files: $(VISUALC_FILES)

# Ensure that the .c files that generate_visualc_files.pl enumerates are
# present before it runs. It doesn't matter if the files aren't up-to-date,
# they just need to be present.
$(VISUALC_FILES): | library/generated_files
$(VISUALC_FILES): | programs/generated_files
$(VISUALC_FILES): | tests/generated_files
$(VISUALC_FILES): $(gen_file_dep) scripts/generate_visualc_files.pl
$(VISUALC_FILES): $(gen_file_dep) scripts/data_files/vs2017-app-template.vcxproj
$(VISUALC_FILES): $(gen_file_dep) scripts/data_files/vs2017-main-template.vcxproj
$(VISUALC_FILES): $(gen_file_dep) scripts/data_files/vs2017-sln-template.sln
# TODO: also the list of .c and .h source files, but not their content
$(VISUALC_FILES):
	echo "  Gen   $@ ..."
	$(PERL) scripts/generate_visualc_files.pl

ifndef WINDOWS
install: no_test
	mkdir -p $(DESTDIR)/include/mbedtls
	cp -rp include/mbedtls $(DESTDIR)/include
	mkdir -p $(DESTDIR)/include/psa
	cp -rp include/psa $(DESTDIR)/include

	mkdir -p $(DESTDIR)/lib
	cp -RP library/libmbedtls.*    $(DESTDIR)/lib
	cp -RP library/libmbedx509.*   $(DESTDIR)/lib
	cp -RP library/libmbedcrypto.* $(DESTDIR)/lib

	mkdir -p $(DESTDIR)/bin
	for p in programs/*/* ; do              \
	    if [ -x $$p ] && [ ! -d $$p ] ;     \
	    then                                \
	        f=$(PREFIX)`basename $$p` ;     \
	        cp $$p $(DESTDIR)/bin/$$f ;     \
	    fi                                  \
	done

uninstall:
	rm -rf $(DESTDIR)/include/mbedtls
	rm -rf $(DESTDIR)/include/psa
	rm -f $(DESTDIR)/lib/libmbedtls.*
	rm -f $(DESTDIR)/lib/libmbedx509.*
	rm -f $(DESTDIR)/lib/libmbedcrypto.*

	for p in programs/*/* ; do              \
	    if [ -x $$p ] && [ ! -d $$p ] ;     \
	    then                                \
	        f=$(PREFIX)`basename $$p` ;     \
	        rm -f $(DESTDIR)/bin/$$f ;      \
	    fi                                  \
	done
endif


WARNING_BORDER_LONG      =**********************************************************************************\n
CTR_DRBG_128_BIT_KEY_WARN_L1=****  WARNING!  MBEDTLS_CTR_DRBG_USE_128_BIT_KEY defined!                      ****\n
CTR_DRBG_128_BIT_KEY_WARN_L2=****  Using 128-bit keys for CTR_DRBG limits the security of generated         ****\n
CTR_DRBG_128_BIT_KEY_WARN_L3=****  keys and operations that use random values generated to 128-bit security ****\n

CTR_DRBG_128_BIT_KEY_WARNING=\n$(WARNING_BORDER_LONG)$(CTR_DRBG_128_BIT_KEY_WARN_L1)$(CTR_DRBG_128_BIT_KEY_WARN_L2)$(CTR_DRBG_128_BIT_KEY_WARN_L3)$(WARNING_BORDER_LONG)

# Post build steps
post_build:
ifndef WINDOWS

	# If 128-bit keys are configured for CTR_DRBG, display an appropriate warning
	-scripts/config.py get MBEDTLS_CTR_DRBG_USE_128_BIT_KEY && ([ $$? -eq 0 ]) && \
	    echo '$(CTR_DRBG_128_BIT_KEY_WARNING)'

endif

clean: clean_more_on_top
	$(MAKE) -C library clean
	$(MAKE) -C programs clean
	$(MAKE) -C tests clean

clean_more_on_top:
ifndef WINDOWS
	find . \( -name \*.gcno -o -name \*.gcda -o -name \*.info \) -exec rm {} +
endif

neat: clean_more_on_top
	$(MAKE) -C library neat
	$(MAKE) -C programs neat
	$(MAKE) -C tests neat
ifndef WINDOWS
	rm -f visualc/VS2017/*.vcxproj visualc/VS2017/mbedTLS.sln
else
	if exist visualc\VS2017\*.vcxproj del /Q /F visualc\VS2017\*.vcxproj
	if exist visualc\VS2017\mbedTLS.sln del /Q /F visualc\VS2017\mbedTLS.sln
endif

check: lib tests
	$(MAKE) -C tests check

test: check

ifndef WINDOWS
# For coverage testing:
# 1. Build with:
#         make CFLAGS='--coverage -g3 -O0' LDFLAGS='--coverage'
# 2. Run the relevant tests for the part of the code you're interested in.
#    For the reference coverage measurement, see
#    tests/scripts/basic-build-test.sh
# 3. Run scripts/lcov.sh to generate an HTML report.
lcov:
	scripts/lcov.sh

apidoc:
	mkdir -p apidoc
	cd doxygen && doxygen mbedtls.doxyfile

apidoc_clean:
	rm -rf apidoc
endif

## Editor navigation files
C_SOURCE_FILES = $(wildcard \
	3rdparty/*/include/*/*.h 3rdparty/*/include/*/*/*.h 3rdparty/*/include/*/*/*/*.h \
	3rdparty/*/*.c 3rdparty/*/*/*.c 3rdparty/*/*/*/*.c 3rdparty/*/*/*/*/*.c \
	include/*/*.h \
	library/*.[hc] \
	programs/*/*.[hc] \
	framework/tests/include/*/*.h framework/tests/include/*/*/*.h \
	framework/tests/src/*.c framework/tests/src/*/*.c \
	tests/suites/*.function \
)
# Exuberant-ctags invocation. Other ctags implementations may require different options.
CTAGS = ctags --langmap=c:+.h.function --line-directives=no -o
tags: $(C_SOURCE_FILES)
	$(CTAGS) $@ $(C_SOURCE_FILES)
TAGS: $(C_SOURCE_FILES)
	etags --no-line-directive -o $@ $(C_SOURCE_FILES)
global: GPATH GRTAGS GSYMS GTAGS
GPATH GRTAGS GSYMS GTAGS: $(C_SOURCE_FILES)
	ls $(C_SOURCE_FILES) | gtags -f - --gtagsconf .globalrc
cscope: cscope.in.out cscope.po.out cscope.out
cscope.in.out cscope.po.out cscope.out: $(C_SOURCE_FILES)
	cscope -bq -u -Iinclude -Ilibrary $(patsubst %,-I%,$(wildcard 3rdparty/*/include)) -Iframework/tests/include $(C_SOURCE_FILES)
.PHONY: cscope global
