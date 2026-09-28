
noinst_LTLIBRARIES = libinjection.la libmbedtls.la

libinjection_la_SOURCES = \
	libinjection/src/libinjection_html5.c \
	libinjection/src/libinjection_sqli.c \
	libinjection/src/libinjection_xss.c

libinjection_la_CFLAGS = -D LIBINJECTION_VERSION=\"${LIBINJECTION_VERSION}\"
libinjection_la_LIBADD =

noinst_HEADERS = \
	libinjection/src/libinjection.h \
	libinjection/src/libinjection_html5.h \
	libinjection/src/libinjection_sqli.h \
	libinjection/src/libinjection_sqli_data.h \
	libinjection/src/libinjection_xss.h \
	libinjection/src/libinjection_error.h \
	mbedtls/tf-psa-crypto/include/mbedtls/base64.h \
	mbedtls/tf-psa-crypto/core/check_crypto_config.h \
	mbedtls/include/mbedtls/mbedtls_config.h \
	mbedtls/tf-psa-crypto/include/mbedtls/md.h \
	mbedtls/tf-psa-crypto/include/mbedtls/platform.h

libmbedtls_la_SOURCES = \
	mbedtls/tf-psa-crypto/utilities/base64.c \
	mbedtls/tf-psa-crypto/utilities/constant_time.c \
	mbedtls/tf-psa-crypto/platform/platform_util.c \
	mbedtls/tf-psa-crypto/extras/md.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/md5.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/sha1.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/sha256.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/sha512.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/sha3.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/ripemd160.c \
	mbedtls/tf-psa-crypto/drivers/builtin/src/psa_util_internal.c

libmbedtls_la_CFLAGS = -DMBEDTLS_CONFIG_FILE=\"mbedtls/mbedtls_config.h\" -I$(top_srcdir)/others/mbedtls/include -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/include -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/core -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/extras -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/library -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/utilities -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/drivers/builtin/include -I$(top_srcdir)/others/mbedtls/tf-psa-crypto/drivers/builtin/src
libmbedtls_la_CPPFLAGS =
libmbedtls_la_LIBADD =
