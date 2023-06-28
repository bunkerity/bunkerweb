
noinst_LTLIBRARIES = libinjection.la libmbedtls.la
libinjection_la_SOURCES = \
	libinjection/src/libinjection_html5.c \
	libinjection/src/libinjection_sqli.c \
	libinjection/src/libinjection_xss.c

noinst_HEADERS = \
	libinjection/src/libinjection.h \
	libinjection/src/libinjection_html5.h \
	libinjection/src/libinjection_sqli.h \
	libinjection/src/libinjection_sqli_data.h \
	libinjection/src/libinjection_xss.h \
	mbedtls/base64.h \
	mbedtls/check_config.h \
	mbedtls/mbed-tls-config.h \
	mbedtls/md5.h \
	mbedtls/platform.h \
	mbedtls/sha1.h

libmbedtls_la_SOURCES = \
	mbedtls/base64.c \
	mbedtls/md5.c \
	mbedtls/sha1.c

libmbedtls_la_CFLAGS = -D MBEDTLS_CONFIG_FILE=\"mbed-tls-config.h\" -Iothers
libmbedtls_la_CPPFLAGS =
libmbedtls_la_LIBADD =
