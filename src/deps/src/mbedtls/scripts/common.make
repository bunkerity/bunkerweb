# To compile on SunOS: add "-lsocket -lnsl" to LDFLAGS

ifndef MBEDTLS_PATH
MBEDTLS_PATH := ..
endif

ifeq (,$(wildcard $(MBEDTLS_PATH)/framework/exported.make))
    # Use the define keyword to get a multi-line message.
    # GNU make appends ".  Stop.", so tweak the ending of our message accordingly.
    define error_message
$(MBEDTLS_PATH)/framework/exported.make not found.
Run `git submodule update --init` to fetch the submodule contents.
This is a fatal error
    endef
    $(error $(error_message))
endif
include $(MBEDTLS_PATH)/framework/exported.make

CFLAGS	?= -O2
WARNING_CFLAGS ?= -Wall -Wextra -Wformat=2 -Wno-format-nonliteral
WARNING_CXXFLAGS ?= -Wall -Wextra -Wformat=2 -Wno-format-nonliteral -std=c++11 -pedantic
LDFLAGS ?=

LOCAL_CFLAGS = $(WARNING_CFLAGS) -I$(MBEDTLS_TEST_PATH)/include \
               -I$(MBEDTLS_PATH)/framework/tests/include \
               -I$(MBEDTLS_PATH)/include \
               -D_FILE_OFFSET_BITS=64
LOCAL_CXXFLAGS = $(WARNING_CXXFLAGS) $(LOCAL_CFLAGS)

LOCAL_LDFLAGS = ${MBEDTLS_TEST_OBJS} 		\
		-L$(MBEDTLS_PATH)/library			\
		-lmbedtls$(SHARED_SUFFIX)	\
		-lmbedx509$(SHARED_SUFFIX)	\
		-lmbedcrypto$(SHARED_SUFFIX)

include $(MBEDTLS_PATH)/3rdparty/Makefile.inc
LOCAL_CFLAGS+=$(THIRDPARTY_INCLUDES)

ifndef SHARED
MBEDLIBS=$(MBEDTLS_PATH)/library/libmbedcrypto.a $(MBEDTLS_PATH)/library/libmbedx509.a $(MBEDTLS_PATH)/library/libmbedtls.a
else
MBEDLIBS=$(MBEDTLS_PATH)/library/libmbedcrypto.$(DLEXT) $(MBEDTLS_PATH)/library/libmbedx509.$(DLEXT) $(MBEDTLS_PATH)/library/libmbedtls.$(DLEXT)
endif

ifdef DEBUG
LOCAL_CFLAGS += -g3
endif

# if we're running on Windows, build for Windows
ifdef WINDOWS
WINDOWS_BUILD=1
endif

## Usage: $(call remove_enabled_options,PREPROCESSOR_INPUT)
## Remove the preprocessor symbols that are set in the current configuration
## from PREPROCESSOR_INPUT. Also normalize whitespace.
## Example:
##   $(call remove_enabled_options,MBEDTLS_FOO MBEDTLS_BAR)
## This expands to an empty string "" if MBEDTLS_FOO and MBEDTLS_BAR are both
## enabled, to "MBEDTLS_FOO" if MBEDTLS_BAR is enabled but MBEDTLS_FOO is
## disabled, etc.
##
## This only works with a Unix-like shell environment (Bourne/POSIX-style shell
## and standard commands) and a Unix-like compiler (supporting -E). In
## other environments, the output is likely to be empty.
define remove_enabled_options
$(strip $(shell
  exec 2>/dev/null;
  { echo '#include <mbedtls/build_info.h>'; echo $(1); } |
  $(CC) $(LOCAL_CFLAGS) $(CFLAGS) -E - |
  tail -n 1
))
endef

ifdef WINDOWS_BUILD
  DLEXT=dll
  EXEXT=.exe
  LOCAL_LDFLAGS += -lws2_32 -lbcrypt
  ifdef SHARED
    SHARED_SUFFIX=.$(DLEXT)
  endif

else # Not building for Windows
  DLEXT ?= so
  EXEXT=
  SHARED_SUFFIX=
  ifndef THREADING
    # Auto-detect configurations with pthread.
    # If the call to remove_enabled_options returns "control", the symbols
    # are confirmed set and we link with pthread.
    # If the auto-detection fails, the result of the call is empty and
    # we keep THREADING undefined.
    ifeq (control,$(call remove_enabled_options,control MBEDTLS_THREADING_C MBEDTLS_THREADING_PTHREAD))
      THREADING := pthread
    endif
  endif

  ifeq ($(THREADING),pthread)
    LOCAL_LDFLAGS += -lpthread
  endif
endif

ifdef WINDOWS
PYTHON ?= python
else
PYTHON ?= $(shell if type python3 >/dev/null 2>/dev/null; then echo python3; else echo python; fi)
endif

# See root Makefile
GEN_FILES ?= yes
ifdef GEN_FILES
gen_file_dep =
else
gen_file_dep = |
endif

default: all

$(MBEDLIBS):
	$(MAKE) -C $(MBEDTLS_PATH)/library

neat: clean
ifndef WINDOWS
	rm -f $(GENERATED_FILES)
else
	for %f in ($(subst /,\,$(GENERATED_FILES))) if exist %f del /Q /F %f
endif

# Auxiliary modules used by tests and some sample programs
MBEDTLS_CORE_TEST_OBJS := $(patsubst %.c,%.o,$(wildcard \
    ${MBEDTLS_PATH}/framework/tests/src/*.c \
    ${MBEDTLS_PATH}/framework/tests/src/drivers/*.c \
  ))
# Additional auxiliary modules for TLS testing
MBEDTLS_TLS_TEST_OBJS = $(patsubst %.c,%.o,$(wildcard \
    ${MBEDTLS_TEST_PATH}/src/*.c \
    ${MBEDTLS_TEST_PATH}/src/test_helpers/*.c \
  ))

MBEDTLS_TEST_OBJS = $(MBEDTLS_CORE_TEST_OBJS) $(MBEDTLS_TLS_TEST_OBJS)
