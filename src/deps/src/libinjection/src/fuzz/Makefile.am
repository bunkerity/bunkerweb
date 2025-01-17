bin_PROGRAMS = fuzzer

fuzzer_SOURCES = fuzzer.c
fuzzer_CFLAGS = $(CXXFLAGS) $(LIB_FUZZING_ENGINE)
fuzzer_LDADD = ../.libs/libinjection.a
fuzzer_LDFLAGS = $(LIB_FUZZING_ENGINE)
# force usage of CXX for linker
fuzzer_LINK=$(LIBTOOL) $(AM_V_lt) --tag=CC $(AM_LIBTOOLFLAGS) \
    $(LIBTOOLFLAGS) --mode=link $(CXX) $(AM_CXXFLAGS) $(CXXFLAGS) \
    $(fuzzer_LDFLAGS) $(LDFLAGS) -o $@

corpus:
	./create_seed_corpus.sh corpus

clean-local:
	@rm -rf corpus

all: corpus
