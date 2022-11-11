if DEBUG
AM_CFLAGS=-O0 -g -Wall -Wextra
else
AM_CFLAGS=-O2 -g
endif

AM_CPPFLAGS = -I$(top_srcdir)/include
