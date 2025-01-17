# luagd -- gd bindings for the Lua Programming Language.
# (c) 2004-11 Alexandre Erwin Ittner <alexandre@ittner.com.br>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDER BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# If you use this package in a product, an acknowledgment in the product
# documentation would be greatly appreciated (but it is not required).
#


# Lua-GD version. This one must be set.
VERSION=2.0.33r3

# Command used to run Lua code
LUABIN=lua5.1

# Optimization for the brave of heart ;)
OMITFP=-fomit-frame-pointer


# ---------------------------------------------------------------------------
# Automatic configuration using pkgconfig. These lines should work on most
# Linux/Unix systems. If your system does not have these programs you must
# comment out these lines and uncomment and change the next ones.

# Name of .pc file. "lua5.1" on Debian/Ubuntu
LUAPKG=lua5.1
OUTFILE=gd.so

CFLAGS=-O3 -Wall -fPIC $(OMITFP)
CFLAGS+=`pkg-config $(LUAPKG) --cflags`
CFLAGS+=-DVERSION=\"$(VERSION)\"

GDFEATURES=-DGD_XPM -DGD_JPEG -DGD_FONTCONFIG -DGD_FREETYPE -DGD_PNG -DGD_GIF
LFLAGS=-shared `pkg-config $(LUAPKG) --libs` -lgd

INSTALL_PATH := `pkg-config $(LUAPKG) --variable=INSTALL_CMOD`


# ---------------------------------------------------------------------------
# Manual configuration for systems without pkgconfig.
# WARNING: These instructions will only work on older versions of GD, since
# gdlib-config has been removed in favor of pkg-config.

# Path to the utility 'gdlib-config'. This may be changed to compile the
# module with development versions of libgd.
#GDLIBCONFIG=gdlib-config

#OUTFILE=gd.so
#CFLAGS=-O3 -Wall -fPIC $(OMITFP)
#CFLAGS+=`$(GDLIBCONFIG) --cflags` -I/usr/include/lua5.1
#CFLAGS+=-DVERSION=\"$(VERSION)\"
#GDFEATURES=`$(GDLIBCONFIG) --features |sed -e "s/GD_/-DGD_/g"`
#LFLAGS=-shared `$(GDLIBCONFIG) --ldflags` `$(GDLIBCONFIG) --libs` -lgd
#INSTALL_PATH=/usr/lib/lua/


# ---------------------------------------------------------------------------
# Manual configuration for Windows and systems without sed, pkgconfig, etc.
# Uncomment, change and good luck :)

#OUTFILE=gd.dll
#CFLAGS=-O3 -Wall -fPIC $(OMITFP)
#CFLAGS+=-IC:/lua5.1/
#CFLAGS+=-DVERSION=\"$(VERSION)\"
#GDFEATURES=-DGD_XPM -DGD_JPEG -DGD_FONTCONFIG -DGD_FREETYPE -DGD_PNG -DGD_GIF
#LFLAGS=-shared -lgd2 -lm $(OMITFP)
#INSTALL_PATH="C:/Program Files/lua/"
# ---------------------------------------------------------------------------


all: test

$(OUTFILE): gd.lo
	$(CC) -o $(OUTFILE) gd.lo $(LFLAGS)

test: $(OUTFILE)
	$(LUABIN) test_features.lua

gd.lo: luagd.c
	$(CC) -o gd.lo -c $(GDFEATURES) $(CFLAGS) luagd.c

install: $(OUTFILE)
	install -D -s $(OUTFILE) $(DESTDIR)/$(INSTALL_PATH)/$(OUTFILE)


# Rules for making a distribution tarball

TDIR=lua-gd-$(VERSION)
DFILES=COPYING README luagd.c lua-gd.spec Makefile test_features.lua
dist: $(DISTFILES)
	rm -f $(TDIR).tar.gz
	mkdir $(TDIR)
	mkdir -p $(TDIR)/doc $(TDIR)/demos $(TDIR)/debian
	cp $(DFILES) $(TDIR)
	cp demos/* $(TDIR)/demos/
	cp doc/* $(TDIR)/doc/
	cp debian/* $(TDIR)/debian/
	tar czf $(TDIR).tar.gz $(TDIR)
	rm -rf $(TDIR)

clean:
	rm -f $(OUTFILE) gd.lo
	rm -rf $(TDIR) $(TDIR).tar.gz
	rm -f demos/out.png demos/out.gif demos/counter.txt

.PHONY: all test install clean dist
