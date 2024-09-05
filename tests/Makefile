MBEDTLS_TEST_PATH = .
include ../scripts/common.make

# Set this to -v to see the details of failing test cases
TEST_FLAGS ?= $(if $(filter-out 0 OFF Off off NO No no FALSE False false N n,$(CTEST_OUTPUT_ON_FAILURE)),-v,)

# Also include library headers, for the sake of invasive tests.
LOCAL_CFLAGS += -I../library

# Enable definition of various functions used throughout the testsuite
# (gethostname, strdup, fileno...) even when compiling with -std=c99. Harmless
# on non-POSIX platforms.
LOCAL_CFLAGS += -D_POSIX_C_SOURCE=200809L

ifdef RECORD_PSA_STATUS_COVERAGE_LOG
LOCAL_CFLAGS += -Werror -DRECORD_PSA_STATUS_COVERAGE_LOG
endif

GENERATED_BIGNUM_DATA_FILES := $(patsubst tests/%,%,$(shell \
	$(PYTHON) ../framework/scripts/generate_bignum_tests.py --list || \
	echo FAILED \
))
ifeq ($(GENERATED_BIGNUM_DATA_FILES),FAILED)
$(error "$(PYTHON) ../framework/scripts/generate_bignum_tests.py --list" failed)
endif
GENERATED_DATA_FILES += $(GENERATED_BIGNUM_DATA_FILES)

GENERATED_CONFIG_DATA_FILES := $(patsubst tests/%,%,$(shell \
	$(PYTHON) ../framework/scripts/generate_config_tests.py --list || \
	echo FAILED \
))
ifeq ($(GENERATED_CONFIG_DATA_FILES),FAILED)
$(error "$(PYTHON) ../framework/scripts/generate_config_tests.py --list" failed)
endif
GENERATED_DATA_FILES += $(GENERATED_CONFIG_DATA_FILES)

GENERATED_ECP_DATA_FILES := $(patsubst tests/%,%,$(shell \
	$(PYTHON) ../framework/scripts/generate_ecp_tests.py --list || \
	echo FAILED \
))
ifeq ($(GENERATED_ECP_DATA_FILES),FAILED)
$(error "$(PYTHON) ../framework/scripts/generate_ecp_tests.py --list" failed)
endif
GENERATED_DATA_FILES += $(GENERATED_ECP_DATA_FILES)

GENERATED_PSA_DATA_FILES := $(patsubst tests/%,%,$(shell \
	$(PYTHON) ../framework/scripts/generate_psa_tests.py --list || \
	echo FAILED \
))
ifeq ($(GENERATED_PSA_DATA_FILES),FAILED)
$(error "$(PYTHON) ../framework/scripts/generate_psa_tests.py --list" failed)
endif
GENERATED_DATA_FILES += $(GENERATED_PSA_DATA_FILES)

GENERATED_FILES = $(GENERATED_DATA_FILES)
GENERATED_FILES += src/test_keys.h src/test_certs.h

.PHONY: generated_files
generated_files: $(GENERATED_FILES)

# generate_bignum_tests.py and generate_psa_tests.py spend more time analyzing
# inputs than generating outputs. Its inputs are the same no matter which files
# are being generated.
# It's rare not to want all the outputs. So always generate all of its outputs.
# Use an intermediate phony dependency so that parallel builds don't run
# a separate instance of the recipe for each output file.
$(GENERATED_BIGNUM_DATA_FILES): $(gen_file_dep) generated_bignum_test_data
generated_bignum_test_data: ../framework/scripts/generate_bignum_tests.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/bignum_common.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/bignum_core.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/bignum_mod_raw.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/bignum_mod.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/test_case.py
generated_bignum_test_data: ../framework/scripts/mbedtls_framework/test_data_generation.py
generated_bignum_test_data:
	echo "  Gen   $(GENERATED_BIGNUM_DATA_FILES)"
	$(PYTHON) ../framework/scripts/generate_bignum_tests.py
.SECONDARY: generated_bignum_test_data

# We deliberately omit the configuration files (mbedtls_config.h,
# crypto_config.h) from the depenency list because during development
# and on the CI, we often edit those in a way that doesn't change the
# output, to comment out certain options, or even to remove certain
# lines which do affect the output negatively (it will miss the
# corresponding test cases).
$(GENERATED_CONFIG_DATA_FILES): $(gen_file_dep) generated_config_test_data
generated_config_test_data: ../framework/scripts/generate_config_tests.py
generated_config_test_data: ../scripts/config.py
generated_config_test_data: ../framework/scripts/mbedtls_framework/test_case.py
generated_config_test_data: ../framework/scripts/mbedtls_framework/test_data_generation.py
generated_config_test_data:
	echo "  Gen   $(GENERATED_CONFIG_DATA_FILES)"
	$(PYTHON) ../framework/scripts/generate_config_tests.py
.SECONDARY: generated_config_test_data

$(GENERATED_ECP_DATA_FILES): $(gen_file_dep) generated_ecp_test_data
generated_ecp_test_data: ../framework/scripts/generate_ecp_tests.py
generated_ecp_test_data: ../framework/scripts/mbedtls_framework/bignum_common.py
generated_ecp_test_data: ../framework/scripts/mbedtls_framework/ecp.py
generated_ecp_test_data: ../framework/scripts/mbedtls_framework/test_case.py
generated_ecp_test_data: ../framework/scripts/mbedtls_framework/test_data_generation.py
generated_ecp_test_data:
	echo "  Gen   $(GENERATED_ECP_DATA_FILES)"
	$(PYTHON) ../framework/scripts/generate_ecp_tests.py
.SECONDARY: generated_ecp_test_data

$(GENERATED_PSA_DATA_FILES): $(gen_file_dep) generated_psa_test_data
generated_psa_test_data: ../framework/scripts/generate_psa_tests.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/crypto_data_tests.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/crypto_knowledge.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/macro_collector.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/psa_information.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/psa_storage.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/test_case.py
generated_psa_test_data: ../framework/scripts/mbedtls_framework/test_data_generation.py
## The generated file only depends on the options that are present in
## crypto_config.h, not on which options are set. To avoid regenerating this
## file all the time when switching between configurations, don't declare
## crypto_config.h as a dependency. Remove this file from your working tree
## if you've just added or removed an option in crypto_config.h.
#generated_psa_test_data: ../include/psa/crypto_config.h
generated_psa_test_data: ../include/psa/crypto_values.h
generated_psa_test_data: ../include/psa/crypto_extra.h
generated_psa_test_data: suites/test_suite_psa_crypto_metadata.data
generated_psa_test_data:
	echo "  Gen   $(GENERATED_PSA_DATA_FILES) ..."
	$(PYTHON) ../framework/scripts/generate_psa_tests.py
.SECONDARY: generated_psa_test_data

# A test application is built for each suites/test_suite_*.data file.
# Application name is same as .data file's base name and can be
# constructed by stripping path 'suites/' and extension .data.
DATA_FILES := $(wildcard suites/test_suite_*.data)
# Make sure that generated data files are included even if they don't
# exist yet when the makefile is parsed.
DATA_FILES += $(filter-out $(DATA_FILES),$(GENERATED_DATA_FILES))
APPS = $(basename $(subst suites/,,$(DATA_FILES)))

# Construct executable name by adding OS specific suffix $(EXEXT).
BINARIES := $(addsuffix $(EXEXT),$(APPS))

.SILENT:

.PHONY: all check test clean

all: $(BINARIES)

mbedtls_test: $(MBEDTLS_TEST_OBJS)

src/test_certs.h: ../framework/scripts/generate_test_cert_macros.py \
				  $($(PYTHON) ../framework/scripts/generate_test_cert_macros.py --list-dependencies)
	$(PYTHON) ../framework/scripts/generate_test_cert_macros.py --output $@

src/test_keys.h: ../framework/scripts/generate_test_keys.py
	$(PYTHON) ../framework/scripts/generate_test_keys.py --output $@

TEST_OBJS_DEPS = $(wildcard include/test/*.h include/test/*/*.h)
ifdef RECORD_PSA_STATUS_COVERAGE_LOG
# Explicitly depend on this header because on a clean copy of the source tree,
# it doesn't exist yet and must be generated as part of the build, and
# therefore the wildcard enumeration above doesn't include it.
TEST_OBJS_DEPS += include/test/instrument_record_status.h
endif
TEST_OBJS_DEPS += src/test_certs.h src/test_keys.h

# Rule to compile common test C files in src folder
src/%.o : src/%.c $(TEST_OBJS_DEPS)
	echo "  CC    $<"
	$(CC) $(LOCAL_CFLAGS) $(CFLAGS) -o $@ -c $<

src/drivers/%.o : src/drivers/%.c
	echo "  CC    $<"
	$(CC) $(LOCAL_CFLAGS) $(CFLAGS) -o $@ -c $<

src/test_helpers/%.o : src/test_helpers/%.c
	echo "  CC    $<"
	$(CC) $(LOCAL_CFLAGS) $(CFLAGS) -o $@ -c $<

C_FILES := $(addsuffix .c,$(APPS))
c: $(C_FILES)

# Wildcard target for test code generation:
# A .c file is generated for each .data file in the suites/ directory. Each .c
# file depends on a .data and .function file from suites/ directory. Following
# nameing convention is followed:
#
#     C file        |        Depends on
#-----------------------------------------------------------------------------
#  foo.c            | suites/foo.function suites/foo.data
#  foo.bar.c        | suites/foo.function suites/foo.bar.data
#
# Note above that .c and .data files have same base name.
# However, corresponding .function file's base name is the word before first
# dot in .c file's base name.
#
.SECONDEXPANSION:
%.c: suites/$$(firstword $$(subst ., ,$$*)).function suites/%.data ../framework/scripts/generate_test_code.py suites/helpers.function suites/main_test.function suites/host_test.function
	echo "  Gen   $@"
	$(PYTHON) ../framework/scripts/generate_test_code.py -f suites/$(firstword $(subst ., ,$*)).function \
		-d suites/$*.data \
		-t suites/main_test.function \
		-p suites/host_test.function \
		-s suites  \
		--helpers-file suites/helpers.function \
		-o .


$(BINARIES): %$(EXEXT): %.c $(MBEDLIBS) $(TEST_OBJS_DEPS) $(MBEDTLS_TEST_OBJS)
	echo "  CC    $<"
	$(CC) $(LOCAL_CFLAGS) $(CFLAGS) $< $(LOCAL_LDFLAGS) $(LDFLAGS) -o $@

clean:
ifndef WINDOWS
	rm -rf $(BINARIES) *.c *.datax
	rm -f src/*.o src/drivers/*.o src/test_helpers/*.o src/libmbed*
	rm -f include/test/instrument_record_status.h
	rm -f include/alt-extra/*/*_alt.h
	rm -rf libtestdriver1
	rm -f ../library/libtestdriver1.a
else
	if exist *.c del /Q /F *.c
	if exist *.exe del /Q /F *.exe
	if exist *.datax del /Q /F *.datax
	if exist src/*.o del /Q /F src/*.o
	if exist src/drivers/*.o del /Q /F src/drivers/*.o
	if exist src/test_helpers/*.o del /Q /F src/test_helpers/*.o
	if exist src/libmbed* del /Q /F src/libmbed*
	if exist include/test/instrument_record_status.h del /Q /F include/test/instrument_record_status.h
endif

# Test suites caught by SKIP_TEST_SUITES are built but not executed.
check: $(BINARIES)
	perl scripts/run-test-suites.pl $(TEST_FLAGS) --skip=$(SKIP_TEST_SUITES)

test: check

# Generate variants of some headers for testing
include/alt-extra/%_alt.h: ../include/%.h
	perl -p -e 's/^(# *(define|ifndef) +\w+_)H\b/$${1}ALT_H/' $< >$@

# Generate test library

# Perl code that is executed to transform each original line from a library
# source file into the corresponding line in the test driver copy of the
# library. Add a LIBTESTDRIVER1_/libtestdriver1_ to mbedtls_xxx and psa_xxx
# symbols.
define libtestdriver1_rewrite :=
	s!^(\s*#\s*include\s*[\"<])(mbedtls|psa)/!$${1}libtestdriver1/include/$${2}/!; \
	next if /^\s*#\s*include/; \
	s/\b(?=MBEDTLS_|PSA_)/LIBTESTDRIVER1_/g; \
	s/\b(?=mbedtls_|psa_)/libtestdriver1_/g;
endef

libtestdriver1.a: export MBEDTLS_PATH := $(patsubst ../..//%,/%,../../$(MBEDTLS_PATH))
libtestdriver1.a:
	# Copy the library and fake a 3rdparty Makefile include.
	rm -Rf ./libtestdriver1
	mkdir ./libtestdriver1
	cp -Rf ../library ./libtestdriver1
	cp -Rf ../include ./libtestdriver1
	cp -Rf ../scripts ./libtestdriver1
	mkdir ./libtestdriver1/3rdparty
	touch ./libtestdriver1/3rdparty/Makefile.inc

	# Set the test driver base (minimal) configuration.
	cp ./include/test/drivers/config_test_driver.h ./libtestdriver1/include/mbedtls/mbedtls_config.h

	# Set the PSA cryptography configuration for the test library.
	# It is set from the copied include/psa/crypto_config.h of the Mbed TLS
        # library the test library is intended to be linked with extended by
        # ./include/test/drivers/crypto_config_test_driver_extension.h to
        # mirror the PSA_ACCEL_* macros.
	mv ./libtestdriver1/include/psa/crypto_config.h ./libtestdriver1/include/psa/crypto_config.h.bak
	head -n -1 ./libtestdriver1/include/psa/crypto_config.h.bak > ./libtestdriver1/include/psa/crypto_config.h
	cat ./include/test/drivers/crypto_config_test_driver_extension.h >> ./libtestdriver1/include/psa/crypto_config.h
	echo "#endif /* PSA_CRYPTO_CONFIG_H */" >> ./libtestdriver1/include/psa/crypto_config.h

	# Prefix MBEDTLS_* PSA_* symbols with LIBTESTDRIVER1_ as well as
	# mbedtls_* psa_* symbols with libtestdriver1_ to avoid symbol clash
	# when this test driver library is linked with the Mbed TLS library.
	perl -pi -e '$(libtestdriver1_rewrite)' ./libtestdriver1/library/*.[ch]
	perl -pi -e '$(libtestdriver1_rewrite)' ./libtestdriver1/include/*/*.h

	$(MAKE) -C ./libtestdriver1/library CFLAGS="-I../../ $(CFLAGS)" LDFLAGS="$(LDFLAGS)" libmbedcrypto.a
	cp ./libtestdriver1/library/libmbedcrypto.a ../library/libtestdriver1.a

ifdef RECORD_PSA_STATUS_COVERAGE_LOG
include/test/instrument_record_status.h: ../include/psa/crypto.h Makefile
	echo "  Gen  $@"
	sed <../include/psa/crypto.h >$@ -n 's/^psa_status_t \([A-Za-z0-9_]*\)(.*/#define \1(...) RECORD_STATUS("\1", \1(__VA_ARGS__))/p'
endif
