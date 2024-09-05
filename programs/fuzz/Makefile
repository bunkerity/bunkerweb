MBEDTLS_TEST_PATH:=../../tests

MBEDTLS_PATH := ../..
include ../../scripts/common.make

DEP=${MBEDLIBS}

ifdef FUZZINGENGINE
LOCAL_LDFLAGS += -lFuzzingEngine
endif

# A test application is built for each fuzz_*.c file.
APPS = $(basename $(wildcard fuzz_*.c))

# Construct executable name by adding OS specific suffix $(EXEXT).
BINARIES := $(addsuffix $(EXEXT),$(APPS))

.SILENT:

.PHONY: all check test clean

all: $(BINARIES)

C_FILES := $(addsuffix .c,$(APPS))

%.o: %.c
	$(CC) $(LOCAL_CFLAGS) $(CFLAGS) -c $<	-o $@


ifdef FUZZINGENGINE
$(BINARIES): %$(EXEXT): %.o common.o $(DEP)
	echo " $(CC) common.o $< $(LOCAL_LDFLAGS) $(LDFLAGS) -o $@"
	$(CXX) common.o $<	$(LOCAL_LDFLAGS) $(LDFLAGS) -o $@
else
$(BINARIES): %$(EXEXT): %.o common.o onefile.o $(DEP)
	echo " $(CC) common.o onefile.o $< $(LOCAL_LDFLAGS) $(LDFLAGS) -o $@"
	$(CC) common.o onefile.o $<	$(LOCAL_LDFLAGS) $(LDFLAGS) -o $@
endif

clean:
ifndef WINDOWS
	rm -rf $(BINARIES) *.o
else
	if exist *.o del /Q /F *.o
	if exist *.exe del /Q /F *.exe
endif
