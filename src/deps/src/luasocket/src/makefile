# luasocket src/makefile
#
# Definitions in this section can be overriden on the command line or in the
# environment.
#
# These are equivalent:
#
#    export PLAT=linux DEBUG=DEBUG LUAV=5.2 prefix=/sw
#    make
#
# and
#
#   make PLAT=linux DEBUG=DEBUG LUAV=5.2 prefix=/sw

# PLAT: linux macosx win32 win64 mingw
# platform to build for
PLAT?=linux

# LUAV: 5.1 5.2 5.3 5.4
# lua version to build against
LUAV?=5.1

# MYCFLAGS: to be set by user if needed
MYCFLAGS?=

# MYLDFLAGS: to be set by user if needed
MYLDFLAGS?=

# DEBUG: NODEBUG DEBUG
# debug mode causes luasocket to collect and returns timing information useful
# for testing and debugging luasocket itself
DEBUG?=NODEBUG

# where lua headers are found for macosx builds
# LUAINC_macosx:
# /opt/local/include
LUAINC_macosx_base?=/opt/local/include
LUAINC_macosx?=$(LUAINC_macosx_base)/lua/$(LUAV) $(LUAINC_macosx_base)/lua$(LUAV) $(LUAINC_macosx_base)/lua-$(LUAV)

# FIXME default should this default to fink or to macports?
# What happens when more than one Lua version is installed?
LUAPREFIX_macosx?=/opt/local
CDIR_macosx?=lib/lua/$(LUAV)
LDIR_macosx?=share/lua/$(LUAV)

# LUAINC_linux:
# /usr/include/lua$(LUAV)
# /usr/local/include
# /usr/local/include/lua$(LUAV)
# where lua headers are found for linux builds
LUAINC_linux_base?=/usr/include
LUAINC_linux?=$(LUAINC_linux_base)/lua/$(LUAV) $(LUAINC_linux_base)/lua$(LUAV)
LUAPREFIX_linux?=/usr/local
CDIR_linux?=lib/lua/$(LUAV)
LDIR_linux?=share/lua/$(LUAV)

# LUAINC_freebsd:
# /usr/local/include/lua$(LUAV)
# where lua headers are found for freebsd builds
LUAINC_freebsd_base?=/usr/local/include/
LUAINC_freebsd?=$(LUAINC_freebsd_base)/lua/$(LUAV) $(LUAINC_freebsd_base)/lua$(LUAV)
LUAPREFIX_freebsd?=/usr/local/
CDIR_freebsd?=lib/lua/$(LUAV)
LDIR_freebsd?=share/lua/$(LUAV)

# where lua headers are found for mingw builds
# LUAINC_mingw:
# /opt/local/include
LUAINC_mingw_base?=/usr/include
LUAINC_mingw?=$(LUAINC_mingw_base)/lua/$(LUAV) $(LUAINC_mingw_base)/lua$(LUAV)
LUALIB_mingw_base?=/usr/bin
LUALIB_mingw?=$(LUALIB_mingw_base)/lua/$(LUAV)/lua$(subst .,,$(LUAV)).dll
LUAPREFIX_mingw?=/usr
CDIR_mingw?=lua/$(LUAV)
LDIR_mingw?=lua/$(LUAV)/lua


# LUAINC_win32:
# LUALIB_win32:
# where lua headers and libraries are found for win32 builds
LUAPREFIX_win32?=
LUAINC_win32?=$(LUAPREFIX_win32)/include/lua/$(LUAV) $(LUAPREFIX_win32)/include/lua$(LUAV)
PLATFORM_win32?=Release
CDIR_win32?=bin/lua/$(LUAV)/$(PLATFORM_win32)
LDIR_win32?=bin/lua/$(LUAV)/$(PLATFORM_win32)/lua
LUALIB_win32?=$(LUAPREFIX_win32)/lib/lua/$(LUAV)/$(PLATFORM_win32)
LUALIBNAME_win32?=lua$(subst .,,$(LUAV)).lib

# LUAINC_win64:
# LUALIB_win64:
# where lua headers and libraries are found for win64 builds
LUAPREFIX_win64?=
LUAINC_win64?=$(LUAPREFIX_win64)/include/lua/$(LUAV) $(LUAPREFIX_win64)/include/lua$(LUAV)
PLATFORM_win64?=x64/Release
CDIR_win64?=bin/lua/$(LUAV)/$(PLATFORM_win64)
LDIR_win64?=bin/lua/$(LUAV)/$(PLATFORM_win64)/lua
LUALIB_win64?=$(LUAPREFIX_win64)/lib/lua/$(LUAV)/$(PLATFORM_win64)
LUALIBNAME_win64?=lua$(subst .,,$(LUAV)).lib


# LUAINC_solaris:
LUAINC_solaris_base?=/usr/include
LUAINC_solaris?=$(LUAINC_solaris_base)/lua/$(LUAV) $(LUAINC_solaris_base)/lua$(LUAV)
LUAPREFIX_solaris?=/usr/local
CDIR_solaris?=lib/lua/$(LUAV)
LDIR_solaris?=share/lua/$(LUAV)

# prefix: /usr/local /usr /opt/local /sw
# the top of the default install tree
prefix?=$(LUAPREFIX_$(PLAT))

CDIR?=$(CDIR_$(PLAT))
LDIR?=$(LDIR_$(PLAT))

# DESTDIR: (no default)
# used by package managers to install into a temporary destination
DESTDIR?=

#------
# Definitions below can be overridden on the make command line, but
# shouldn't have to be.


#------
# Install directories
#

INSTALL_DIR=install -d
INSTALL_DATA=install -m644
INSTALL_EXEC=install
INSTALL_TOP=$(DESTDIR)$(prefix)

INSTALL_TOP_LDIR=$(INSTALL_TOP)/$(LDIR)
INSTALL_TOP_CDIR=$(INSTALL_TOP)/$(CDIR)

INSTALL_SOCKET_LDIR=$(INSTALL_TOP_LDIR)/socket
INSTALL_SOCKET_CDIR=$(INSTALL_TOP_CDIR)/socket
INSTALL_MIME_LDIR=$(INSTALL_TOP_LDIR)/mime
INSTALL_MIME_CDIR=$(INSTALL_TOP_CDIR)/mime

print:
	@echo PLAT=$(PLAT)
	@echo LUAV=$(LUAV)
	@echo DEBUG=$(DEBUG)
	@echo prefix=$(prefix)
	@echo LUAINC_$(PLAT)=$(LUAINC_$(PLAT))
	@echo LUALIB_$(PLAT)=$(LUALIB_$(PLAT))
	@echo INSTALL_TOP_CDIR=$(INSTALL_TOP_CDIR)
	@echo INSTALL_TOP_LDIR=$(INSTALL_TOP_LDIR)
	@echo CFLAGS=$(CFLAGS)
	@echo LDFLAGS=$(LDFLAGS)

#------
# Supported platforms
#
PLATS= macosx linux win32 win64 mingw solaris

#------
# Compiler and linker settings
# for Mac OS X
SO_macosx=so
O_macosx=o
CC_macosx=gcc
DEF_macosx= -DLUASOCKET_$(DEBUG) -DUNIX_HAS_SUN_LEN
CFLAGS_macosx=$(LUAINC:%=-I%) $(DEF) -Wall -O2 -fno-common
LDFLAGS_macosx= -bundle -undefined dynamic_lookup -o
LD_macosx=gcc
SOCKET_macosx=usocket.o

#------
# Compiler and linker settings
# for Linux
SO_linux=so
O_linux=o
CC_linux=gcc
DEF_linux=-DLUASOCKET_$(DEBUG)
CFLAGS_linux=$(LUAINC:%=-I%) $(DEF) -Wall -Wshadow -Wextra \
	-Wimplicit -O2 -ggdb3 -fpic
LDFLAGS_linux=-O -shared -fpic -o
LD_linux=gcc
SOCKET_linux=usocket.o

#------
# Compiler and linker settings
# for FreeBSD
SO_freebsd=so
O_freebsd=o
CC_freebsd=gcc
DEF_freebsd=-DLUASOCKET_$(DEBUG) -DUNIX_HAS_SUN_LEN
CFLAGS_freebsd=$(LUAINC:%=-I%) $(DEF) -Wall -Wshadow -Wextra \
	-Wimplicit -O2 -ggdb3 -fpic
LDFLAGS_freebsd=-O -shared -fpic -o
LD_freebsd=gcc
SOCKET_freebsd=usocket.o

#------
# Compiler and linker settings
# for Solaris
SO_solaris=so
O_solaris=o
CC_solaris=gcc
DEF_solaris=-DLUASOCKET_$(DEBUG)
CFLAGS_solaris=$(LUAINC:%=-I%) $(DEF) -Wall -Wshadow -Wextra \
	-Wimplicit -O2 -ggdb3 -fpic
LDFLAGS_solaris=-lnsl -lsocket -lresolv -O -shared -fpic -o
LD_solaris=gcc
SOCKET_solaris=usocket.o

#------
# Compiler and linker settings
# for MingW
SO_mingw=dll
O_mingw=o
CC_mingw=gcc
DEF_mingw= -DLUASOCKET_$(DEBUG) \
	-DWINVER=0x0501
CFLAGS_mingw=$(LUAINC:%=-I%) $(DEF) -Wall -O2 -fno-common
LDFLAGS_mingw= $(LUALIB) -shared -Wl,-s -lws2_32 -o
LD_mingw=gcc
SOCKET_mingw=wsocket.o


#------
# Compiler and linker settings
# for Win32
SO_win32=dll
O_win32=obj
CC_win32=cl
DEF_win32= //D "WIN32" //D "NDEBUG" //D "_WINDOWS" //D "_USRDLL" \
     //D "_CRT_SECURE_NO_WARNINGS" \
     //D "_WINDLL"  \
     //D "LUASOCKET_$(DEBUG)"
CFLAGS_win32=$(LUAINC:%=//I "%") $(DEF) //O2 //Ot //MD //W3 //nologo
LDFLAGS_win32= //nologo //link //NOLOGO //DLL //INCREMENTAL:NO \
    //MANIFEST //MANIFESTFILE:"intermediate.manifest" \
    /MANIFESTUAC:"level='asInvoker' uiAccess='false'" \
	//SUBSYSTEM:WINDOWS //OPT:REF //OPT:ICF //DYNAMICBASE:NO \
    //MACHINE:X86 /LIBPATH:"$(LUALIB)" \
	$(LUALIBNAME_win32) ws2_32.lib //OUT:

LD_win32=cl
SOCKET_win32=wsocket.obj

#------
# Compiler and linker settings
# for Win64
SO_win64=dll
O_win64=obj
CC_win64=cl
DEF_win64= //D "WIN32" //D "NDEBUG" //D "_WINDOWS" //D "_USRDLL" \
     //D "_CRT_SECURE_NO_WARNINGS" \
     //D "_WINDLL"  \
     //D "LUASOCKET_$(DEBUG)"
CFLAGS_win64=$(LUAINC:%=//I "%") $(DEF) //O2 //Ot //MD //W3 //nologo
LDFLAGS_win64= //nologo //link //NOLOGO //DLL //INCREMENTAL:NO \
    //MANIFEST //MANIFESTFILE:"intermediate.manifest" \
    /MANIFESTUAC:"level='asInvoker' uiAccess='false'" \
	//SUBSYSTEM:WINDOWS //OPT:REF //OPT:ICF //DYNAMICBASE:NO \
    /LIBPATH:"$(LUALIB)" \
	$(LUALIBNAME_win64) ws2_32.lib //OUT:

LD_win64=cl
SOCKET_win64=wsocket.obj

.SUFFIXES: .obj

.c.obj:
	$(CC) $(CFLAGS) //Fo"$@" //c $<

#------
# Output file names
#
SO=$(SO_$(PLAT))
O=$(O_$(PLAT))
SOCKET_V=3.0.0
MIME_V=1.0.3
SOCKET_SO=socket-$(SOCKET_V).$(SO)
MIME_SO=mime-$(MIME_V).$(SO)
UNIX_SO=unix.$(SO)
SERIAL_SO=serial.$(SO)
SOCKET=$(SOCKET_$(PLAT))

#------
# Settings selected for platform
#
CC=$(CC_$(PLAT))
DEF=$(DEF_$(PLAT))
CFLAGS=$(MYCFLAGS) $(CFLAGS_$(PLAT))
LDFLAGS=$(MYLDFLAGS) $(LDFLAGS_$(PLAT))
LD=$(LD_$(PLAT))
LUAINC= $(LUAINC_$(PLAT))
LUALIB= $(LUALIB_$(PLAT))

#------
# Modules belonging to socket-core
#
SOCKET_OBJS= \
	luasocket.$(O) \
	timeout.$(O) \
	buffer.$(O) \
	io.$(O) \
	auxiliar.$(O) \
	compat.$(O) \
	options.$(O) \
	inet.$(O) \
	$(SOCKET) \
	except.$(O) \
	select.$(O) \
	tcp.$(O) \
	udp.$(O)

#------
# Modules belonging mime-core
#
MIME_OBJS= \
	mime.$(O) \
	compat.$(O)

#------
# Modules belonging unix (local domain sockets)
#
UNIX_OBJS=\
	buffer.$(O) \
	auxiliar.$(O) \
	options.$(O) \
	timeout.$(O) \
	io.$(O) \
	usocket.$(O) \
	unixstream.$(O) \
	unixdgram.$(O) \
	compat.$(O) \
	unix.$(O)

#------
# Modules belonging to serial (device streams)
#
SERIAL_OBJS=\
	buffer.$(O) \
	compat.$(O) \
	auxiliar.$(O) \
	options.$(O) \
	timeout.$(O) \
	io.$(O) \
	usocket.$(O) \
	serial.$(O)

#------
# Files to install
#
TO_SOCKET_LDIR= \
	http.lua \
	url.lua \
	tp.lua \
	ftp.lua \
	headers.lua \
	smtp.lua

TO_TOP_LDIR= \
	ltn12.lua \
	socket.lua \
	mime.lua

#------
# Targets
#
default: $(PLAT)


freebsd:
	$(MAKE) all-unix PLAT=freebsd

macosx:
	$(MAKE) all-unix PLAT=macosx

win32:
	$(MAKE) all PLAT=win32

win64:
	$(MAKE) all PLAT=win64

linux:
	$(MAKE) all-unix PLAT=linux

mingw:
	$(MAKE) all PLAT=mingw

solaris:
	$(MAKE) all-unix PLAT=solaris

none:
	@echo "Please run"
	@echo "   make PLATFORM"
	@echo "where PLATFORM is one of these:"
	@echo "   $(PLATS)"

all: $(SOCKET_SO) $(MIME_SO)

$(SOCKET_SO): $(SOCKET_OBJS)
	$(LD) $(SOCKET_OBJS) $(LDFLAGS)$@

$(MIME_SO): $(MIME_OBJS)
	$(LD) $(MIME_OBJS) $(LDFLAGS)$@

all-unix: all $(UNIX_SO) $(SERIAL_SO)

$(UNIX_SO): $(UNIX_OBJS)
	$(LD) $(UNIX_OBJS) $(LDFLAGS)$@

$(SERIAL_SO): $(SERIAL_OBJS)
	$(LD) $(SERIAL_OBJS) $(LDFLAGS)$@

install:
	$(INSTALL_DIR) $(INSTALL_TOP_LDIR)
	$(INSTALL_DATA) $(TO_TOP_LDIR) $(INSTALL_TOP_LDIR)
	$(INSTALL_DIR) $(INSTALL_SOCKET_LDIR)
	$(INSTALL_DATA) $(TO_SOCKET_LDIR) $(INSTALL_SOCKET_LDIR)
	$(INSTALL_DIR) $(INSTALL_SOCKET_CDIR)
	$(INSTALL_EXEC) $(SOCKET_SO) $(INSTALL_SOCKET_CDIR)/core.$(SO)
	$(INSTALL_DIR) $(INSTALL_MIME_CDIR)
	$(INSTALL_EXEC) $(MIME_SO) $(INSTALL_MIME_CDIR)/core.$(SO)

install-unix: install
	$(INSTALL_EXEC) $(UNIX_SO) $(INSTALL_SOCKET_CDIR)/$(UNIX_SO)
	$(INSTALL_EXEC) $(SERIAL_SO) $(INSTALL_SOCKET_CDIR)/$(SERIAL_SO)

local:
	$(MAKE) install INSTALL_TOP_CDIR=.. INSTALL_TOP_LDIR=..

clean:
	rm -f $(SOCKET_SO) $(SOCKET_OBJS) $(SERIAL_OBJS)
	rm -f $(MIME_SO) $(UNIX_SO) $(SERIAL_SO) $(MIME_OBJS) $(UNIX_OBJS)

.PHONY: all $(PLATS) default clean echo none

#------
# List of dependencies
#
compat.$(O): compat.c compat.h
auxiliar.$(O): auxiliar.c auxiliar.h
buffer.$(O): buffer.c buffer.h io.h timeout.h
except.$(O): except.c except.h
inet.$(O): inet.c inet.h socket.h io.h timeout.h usocket.h
io.$(O): io.c io.h timeout.h
luasocket.$(O): luasocket.c luasocket.h auxiliar.h except.h \
	timeout.h buffer.h io.h inet.h socket.h usocket.h tcp.h \
	udp.h select.h
mime.$(O): mime.c mime.h
options.$(O): options.c auxiliar.h options.h socket.h io.h \
	timeout.h usocket.h inet.h
select.$(O): select.c socket.h io.h timeout.h usocket.h select.h
serial.$(O): serial.c auxiliar.h socket.h io.h timeout.h usocket.h \
  options.h unix.h buffer.h
tcp.$(O): tcp.c auxiliar.h socket.h io.h timeout.h usocket.h \
	inet.h options.h tcp.h buffer.h
timeout.$(O): timeout.c auxiliar.h timeout.h
udp.$(O): udp.c auxiliar.h socket.h io.h timeout.h usocket.h \
	inet.h options.h udp.h
unix.$(O): unix.c auxiliar.h socket.h io.h timeout.h usocket.h \
	options.h unix.h buffer.h
usocket.$(O): usocket.c socket.h io.h timeout.h usocket.h
wsocket.$(O): wsocket.c socket.h io.h timeout.h usocket.h
