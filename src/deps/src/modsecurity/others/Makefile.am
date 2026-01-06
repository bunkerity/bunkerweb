
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
	mbedtls/include/mbedtls/base64.h \
	mbedtls/include/mbedtls/check_config.h \
	mbedtls/include/mbedtls/mbedtls_config.h \
	mbedtls/include/mbedtls/md5.h \
	mbedtls/include/mbedtls/platform.h \
	mbedtls/include/mbedtls/sha1.h

libmbedtls_la_SOURCES = \
	mbedtls/library/base64.c \
	mbedtls/library/md5.c \
	mbedtls/library/sha1.c \
	mbedtls/library/platform_util.c

libmbedtls_la_CFLAGS = -DMBEDTLS_CONFIG_FILE=\"mbedtls/mbedtls_config.h\" -I$(top_srcdir)/others/mbedtls/include
libmbedtls_la_CPPFLAGS =
libmbedtls_la_LIBADD =
