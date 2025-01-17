# Changelog

## [v3.1.0](https://github.com/lunarmodules/luasocket/releases/v3.1.0) — 2022-07-27

* Add support for TCP Defer Accept – @Zash
* Add support for TCP Fast Open – @Zash
* Fix Windows (mingw32) builds – @goldenstein64
* Avoid build warnings on 64-bit Windows – @rpatters1

## [v3.0.0](https://github.com/lunarmodules/luasocket/releases/v3.0.0) — 2022-03-25

The last time LuaSocket had a stable release tag was 14 years ago when 2.0.2 was tagged.
A v3 release candidate was tagged 9 years ago.
Since then it has been downloaded over 3 million times.
Additionally the Git repository regularly gets several hundred clones a day.
But 9 years is a long time and even the release candidate has grown a bit long in the tooth.
Many Linux distros have packaged the current Git HEAD or some specific tested point as dated or otherwise labeled releases.
256 commits later and having been migrated to the @lunarmodules org namespace on GitHub, please welcome v3.

This release is a "safe-harbor" tag that represents a minimal amount of changes to get a release tagged.
Beyond some CI tooling, very little code has changed since migration to @lunarmodules ([5b18e47..e47d98f](https://github.com/lunarmodules/luasocket/compare/5b18e47..e47d98f?w=1)):

* Lua 5.4.3+ support – @pkulchenko, @Zash
* Cleanup minor issues to get a code linter to pass – @Tieske, @jyoui, @alerque
* Update Visual Studio build rules for Lua 5.1 – @ewestbrook
* Set http transfer-encoding even without content-length – @tokenrove

Prior to migration to @lunarmodules ([v3.0-rc1..5b18e47](https://github.com/lunarmodules/luasocket/compare/v3.0-rc1..5b18e47?w=1)) many things happened of which the author of this changelog is not fully apprised.
Your best bet if it affects your project somehow is to read the commit log & diffs yourself.

## [v3.0-rc1](https://github.com/lunarmodules/luasocket/releases/v3.0-rc1) — 2013-06-14

Main changes for LuaSocket 3.0-rc1 are IPv6 support and Lua 5.2 compatibility.

* Added: Compatible with Lua 5.2
  - Note that unless you define LUA_COMPAT_MODULE, package tables will not be exported as globals!
* Added: IPv6 support;
  - Socket.connect and socket.bind support IPv6 addresses;
  - Getpeername and getsockname support IPv6 addresses, and return the socket family as a third value;
  - URL module updated to support IPv6 host names;
  - New socket.tcp6 and socket.udp6 functions;
  - New socket.dns.getaddrinfo and socket.dns.getnameinfo functions;
* Added: getoption method;
* Fixed: url.unescape was returning additional values;
* Fixed: mime.qp, mime.unqp, mime.b64, and mime.unb64 could mistaking their own stack slots for functions arguments;
* Fixed: Receiving zero-length datagram is now possible;
* Improved: Hidden all internal library symbols;
* Improved: Better error messages;
* Improved: Better documentation of socket options.
* Fixed: manual sample of HTTP authentication now uses correct "authorization" header (Alexandre Ittner);
* Fixed: failure on bind() was destroying the socket (Sam Roberts);
* Fixed: receive() returns immediatelly if prefix can satisfy bytes requested (M Joonas Pihlaja);
* Fixed: multicast didn't work on Windows, or anywhere else for that matter (Herbert Leuwer, Adrian Sietsma);
* Fixed: select() now reports an error when called with more sockets than FD_SETSIZE (Lorenzo Leonini);
* Fixed: manual links to home.html changed to index.html (Robert Hahn);
* Fixed: mime.unb64() would return an empty string on results that started with a null character (Robert Raschke);
* Fixed: HTTP now automatically redirects on 303 and 307 (Jonathan Gray);
* Fixed: calling sleep() with negative numbers could block forever, wasting CPU. Now it returns immediately (MPB);
* Improved: FTP commands are now sent in upper case to help buggy servers (Anders Eurenius);
* Improved: known headers now sent in canonic capitalization to help buggy servers (Joseph Stewart);
* Improved: Clarified tcp:receive() in the manual (MPB);
* Improved: Decent makefiles (LHF).
* Fixed: RFC links in documentation now point to IETF (Cosmin Apreutesei).

## [v2.0.2](https://github.com/lunarmodules/luasocket/releases/v2.0.2) — 2007-09-11
