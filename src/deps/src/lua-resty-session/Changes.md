# Changelog

All notable changes to `lua-resty-session` will be documented in this file.

## [4.0.3] - 2023-02-21
### Fixed
- fix(*): redis authorization

## [4.0.2] - 2023-02-15
### Fixed
- fix(*): hkdf is not approved by FIPS, use PBKDF2 instead on FIPS-mode


## [4.0.1] - 2023-02-05
### Fixed
- fix(session): clear_request cookie to check remember_meta correctly before using it

### Added
- feat(opm): add more dependencies in requires
- feat(opm): add right version number requirements
- docs(readme): add remark on dependencies on installation section


## [4.0.0] - 2023-02-01
- Full rewrite of the library, and is not backwards compatible. Refer new
  documentation on this new library.


## [3.10] - 2022-01-14
### Fixed
- 3.9 introduced an issue where calling session:regenerate with flush=true,
  didn't really flush if the session strategy was `regenerate`.


## [3.9] - 2022-01-14
### Fixed
- Fix #138 issue of chunked cookies are not expired when session shrinks,
  thanks @alexdowad.
- Fix #134 where regenerate strategy destroyed previous session when calling
  `session:regenerate`, it should just `ttl` the old session.

### Added
- AES GCM mode support was added to AES cipher.
  This is recommended, but for backward compatibility it was not set as default.
  It will be changed in 4.0 release.
- Redis ACL authentication is now available.
  - Add `session_redis_username`
  - Add `session_redis_password`
  - Deprecate `session_redis_auth`; use `session_redis_password`

### Changed
- Optimize Redis and Memcache storage adapters to not connect to database
  when not needed.
  

## [3.8] - 2021-01-04
### Added
- Connection options are now passed to `redis cluster client` as well.


## [3.7] - 2020-10-27
### Fixed
- Fix #107 where `session.start` could release a lock for a short period

### Added
- Add `keep_lock` argument to `session.open`
- Add pluggable compressors, and implement `none` and `zlib` compressor


## [3.6] - 2020-06-24
### Fixed
- Fix `session:hide()` to only send a single `Cookie` header at most as
  reported by @jharriman who also provided a fix with #103. Thank you!


## [3.5] - 2020-05-22
### Fixed
- Fix `session:hide()` to not clear non-session request cookies that it
  seemed to do in some cases as reported by @altexy who also provided
  initial fix with #100. Thank you!


## [3.4] - 2020-05-08
### Fixed
- Fix session_cookie_maxsize - error attempt to compare string with number,
  fixes #98, thank you @vavra5

### Changed
- More robust and uniform configuration parsing


## [3.3] - 2020-05-06
### Fixed
- Fix `set_timeouts` is only called if all parameters are available,
  should fix #96, thank you @notdodo.
### Added
- Add `$session_memcache_connect_timeout` configuration option
- Add `$session_memcache_read_timeout` configuration option
- Add `$session_memcache_send_timeout` configuration option
- Add `$session_memcache_pool_name` configuration option
- Add `$session_memcache_pool_backlog` configuration option
- Add `$session_dshm_connect_timeout` configuration option
- Add `$session_dshm_read_timeout` configuration option
- Add `$session_dshm_send_timeout` configuration option
- Add `$session_dshm_pool_name` configuration option
- Add `$session_dshm_pool_backlog` configuration option


## [3.2] - 2020-04-30
### Added
- Support for Redis clusters
- Add `$session_redis_connect_timeout` configuration option
- Add `$session_redis_read_timeout` configuration option
- Add `$session_redis_send_timeout` configuration option
- Add `$session_redis_pool_name` configuration option
- Add `$session_redis_pool_backlog` configuration option
- Add `$session_redis_cluster_name` configuration option
- Add `$session_redis_cluster_dict` configuration option
- Add `$session_redis_cluster_maxredirections` configuration option
- Add `$session_redis_cluster_nodes` configuration option


## [3.1] - 2020-03-28
### Added
- A more flexible way to specify custom implementations:
  `require "resty.session".new { storage = require "my.storage" }`


## [3.0] - 2020-03-27
### Fixed
- Lock releasing is a lot more robust now

### Added
- Add idletime setting (thanks @Tieske), see `session.cookie.idletime`
- Add support for Cookie prefixes `__Host-` and `__Secure-` on Cookie
  name (see: https://tools.ietf.org/html/draft-ietf-httpbis-rfc6265bis-05#section-4.1.3)

### Changed
- The whole codebase was refactored and simplified, especially implementing
  new storage adapters is now a lot easier
- Redis and Memcached `spinlockwait` was changed from microseconds to milliseconds and default
  is set to `150` milliseconds,
- Redis and Memcache will only release locks that current session instance holds
- DSHM `session_dshm_store` was renamed to `session_dshm_region`
- BASE64 encoding now strips the padding


## [2.26] - 2020-02-11
### Added
- Add support for `SameSite=None` (#83) (thanks @bodewig)
- Style changes (#77) (thanks @Tieske)


## [2.25] - 2019-11-06
### Added
- Add SSL support for the Redis storage option (#75) (thanks @tieske)
- DSHM storage adapter (a distributed SHM storage based on Hazelcast for Nginx)
  (thanks @grrolland)


## [2.24] - 2019-07-09
### Fixed
- Avoid use unix socket and redis password with empty string
- Provide session id when closing, otherwise the lock is not deleted

### Added
- Added a configuration for session cookie max size (`session.cookie.maxsize`)


## [2.23] - 2018-12-12
### Added
- Added pluggable strategies with `default` and a new `regenerate` strategy
- Added pluggable `hmac`s
- Added `session.close`
- Added `ttl` to `storages`
- Added `session.cookie.discard`, a `ttl` how long to keep old sessions when
  renewing (used by `regenerate` strategy


## [2.22] - 2018-03-17
### Fixed
- Only sets self.cookie.secure if not defined.


## [2.21] - 2018-03-16
### Screwed
- Forgot to bump version number.


## [2.20] - 2018-03-16
### Fixed
- Fixes issue where check addr and check scheme could be faked.
  See also: https://github.com/bungle/lua-resty-session/issues/47
  Thanks @nielsole


## [2.19] - 2017-09-19
### Fixed
- Fixes small bug where aes could generate invalid salt on invalid input
  that further crashes Lua with error: bad argument #2 to 'salt' (number
  expected, got no value)


## [2.18] - 2017-07-10
### Fixed
- Automatically creates exactly 64 bits salt as required by the latest
  lua-resty-string.
  See also: https://github.com/bungle/lua-resty-session/issues/40
  Thanks @peturorri


## [2.17] - 2017-06-12
### Added
- Added session.hide() function to hide session cookies from upstream
  on reverse proxy scenarios.


## [2.16] - 2017-05-31
### Changed
- Delays setting the defaults until needed, allowing users to safely
  require "resty.session" in different contexts.


## [2.15] - 2017-02-13
## Added
- Added a support for chunked cookies.
  See also: https://github.com/bungle/lua-resty-session/issues/35
  Thanks @zandbelt


## [2.14] - 2016-12-16
### Fixed
- Lua code configuration parsing corrections (especially on boolean
  options).

## Added
- Added a more natural way to pass config arguments to storage
  adapters and ciphers in Lua code.
  See also: https://github.com/bungle/lua-resty-session/issues/34
  Thanks @hanxi


## [2.13] - 2016-11-21
### Changed
- On start we do send cookie now also if the settings have changed
  and the cookie expiry time needs to be reduced.

### Fixed
- Memcache storage adapter had a missing ngx.null.


## [2.12] - 2016-11-21
### Added
- Implemented pluggable session identifier generators.
- Implemented random session idenfier generator.

### Changed
- Now checks if headers were already sent before trying to set the
  cookie headers.
- SSL session identifier is not checked by default anymore.
- Lua session.identifier.length changed to session.random.length.
- Nginx $session_identifier_length changed to $session_random_length.


## [2.11] - 2016-09-30
### Changed
- Just another OPM release to correct the name.


## [2.10] - 2016-09-29
### Added
- Support for the official OpenResty package manager (opm).

### Changed
- Changed the change log format to keep-a-changelog.


## [2.9] - 2016-09-01
### Fixed
- Bugfix: Weird bug where RAND_bytes was not working on Windows platform.
  Code changed to use resty.random. See Also:
  https://github.com/bungle/lua-resty-session/issues/31
  Thanks @gtuxyco


## [2.8] - 2016-07-05
### Fixed
- Bugfix: AES Cipher used a wrong table for cipher sizes.
  See Also: https://github.com/bungle/lua-resty-session/issues/30
  Thanks @pronan


## [2.7] - 2016-05-18
### Added
- Redis storage adapter now supports Redis authentication.
  See Also: https://github.com/bungle/lua-resty-session/pull/28
  Thanks @cheng5533062


## [2.6] - 2016-04-18
### Changed
- Just cleanups and changed _VERSION to point correct version.


## [2.5] - 2016-04-18
### Fixed
- session.save close argument was not defaulting to true.


## [2.4] - 2016-04-17
### Added
- Cookie will now have SameSite attribute set as "Lax" by default.
  You can turn it off or set to "Strict" by configuration.

### Changed
- Calling save will now also set session.id if the save was called
  without calling start first.
  See Also: https://github.com/bungle/lua-resty-session/issues/27
  Thanks @hcaihao


## [2.3] - 2015-10-16
### Fixed
- Fixes issue #19 where regenerating session would throw an error
  when using cookie storage.
  See Also: https://github.com/bungle/lua-resty-session/issues/19
  Thanks @hulu1522


## [2.2] - 2015-09-17
### Changed
- Removed all session_cipher_* deprecated settings (it was somewhat
  broken in 2.1).
- Changed session secret to be by default 32 bytes random data
  See Also: https://github.com/bungle/lua-resty-session/issues/18
  Thanks @iain-buclaw-sociomantic

### Added
- Added documentation about removed features and corrected about
  session secret size accordingly.


## [2.1] - 2015-09-07
### Added
- Added architecture for Cipher adapter plugins.
  See Also: https://github.com/bungle/lua-resty-session/issues/16
  Thanks @mingfang
- Implemented AES cipher adapter (just like it was before)
- Implemented None cipher adapter (no encryption)
- Added documentation about pluggable ciphers

### Changed
- Changed JSON serializer to use cjson.safe instead


## [2.0] - 2015-08-31
### Added
- Added architecture for Storage adapter plugins.
  See Also: https://github.com/bungle/lua-resty-session/issues/13
- Implemented Client Side Cookie storage adapter.
- Implemented Memcache storage adapter.
  See Also: https://github.com/bungle/lua-resty-session/pull/14
  Thanks @zandbelt
- Implemented Redis storage adapter.
- Implemented Shared Dictionary (shm) storage adapter.
- Added architecture for Encoder and Decoder plugins.
- Implemented Base 64 encoder / decoder.
- Implemented Base 16 (hex) encoder / decoder.
- Added architecture for Serializer plugins
- Implemented JSON serializer.
- Persistent cookies will now also contain Max-Age in addition to Expires.
- Cookie domain attribute is not set anymore if not specified.
- Added notes about using lua-resty-session with Lua code cache turned off.
  See also: https://github.com/bungle/lua-resty-session/issues/15
  Thanks @BizShuk


## [1.7] - 2015-08-03
### Added
- Added session.open() function that only opens a session but doesn't send
  the cookie (until start is called).
  See also: https://github.com/bungle/lua-resty-session/issues/12
  Thanks @junhanamaki

### Fixed
- Fixed cookie expiration time format on Firefox bug:
  https://github.com/bungle/lua-resty-session/pull/10
  Thanks @junhanamaki
- Bugfix: Fixed an issue of overwriting a variable:
  https://github.com/bungle/lua-resty-session/pull/11
  Thanks @junhanamaki


## [1.6] - 2015-05-05
### Fixed
- Fixed truncated cookie value bug:
  https://github.com/bungle/lua-resty-session/pull/8
  Thanks @kipras


## [1.5] - 2014-11-27
### Fixed
- Cookies are not always "secure":
  https://github.com/bungle/lua-resty-session/issues/5
  Thanks @vladimir-smirnov-sociomantic

### Added
- Added documentation about Nginx SSL/TLS configuration settings related
  to session lifetime and ssl session ids.


## [1.4] - 2014-11-26
### Fixed
- Bugfix: Fixed an issue where session configurations did get cached
  on a module level. This issue is discussed in pull-request #4:
  https://github.com/bungle/lua-resty-session/pull/4
  Thanks @kipras.

### Added
- Added session.new function.
- Added documentation about Nginx configuration used as defaults (not read
  on every request), and documented session.new.

### Changed
- session.start{ ... } (a call with config parameters) works now as expected.
- session.start now returns additional extra boolean parameter that can be
  used to check if the session is s new session (false) or a previously
  started one (true).


## [1.3] - 2014-11-14
### Added
- Added support for persistent sessions. See issue #2.
- Added session.check.ssi, session.cookie.persistent and the related Nginx
  configuration variables.
- Added Max-Age=0 to expiration code.


## [1.2] - 2014-10-12
### Fixed
- Changed encode and decode functions to operate with correct number of
  arguments. See issue #1.


## [1.1] - 2014-10-03
### Security
- There was a bug where additional user agent, scheme, and remote addr
  (disabled by default) was not checked.

### Added
- Added _VERSION field.

### Changed
- Simplied a code a lot (e.g. internal setcookie and getcookie functions are
  now cleaner). Removed a lot of unneccessary lines from session.start by
  adding configs directly to session prototype.


## [1.0] - 2014-09-24
### Added
- LuaRocks Support via MoonRocks.
