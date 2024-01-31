# Table of Contents

- [2.6.0](#2.6.0)
- [2.5.0](#2.5.0)
- [2.4.1](#2.4.1)
- [2.4.0](#2.4.0)
- [2.3.0](#2.3.0)
- [2.2.1](#2.2.1)
- [2.2.0](#2.2.0)
- [2.1.0](#2.1.0)
- [2.0.2](#2.0.2)
- [2.0.1](#2.0.1)
- [2.0.0](#2.0.0)
- [1.0.1](#1.0.1)
- [1.0.0](#1.0.0)

## [2.6.0]

> Released on: 2022/08/22

#### Added

- Use the new LuaJIT `string.buffer` API for L2 (shm layer) encoding/decoding
  when available.
  [#110](https://github.com/thibaultcha/lua-resty-mlcache/pull/110)

[Back to TOC](#table-of-contents)

## [2.5.0]

> Released on: 2020/11/18

#### Added

- `get()` callback functions are now optional. Without a callback, `get()` now
  still performs on-cpu L1/L2 lookups (no yielding). This allows implementing
  new cache lookup patterns guaranteed to be on-cpu for a more constant,
  smoother latency tail end (e.g. values are refreshed in background timers with
  `set()`).
  Thanks Hamish Forbes and Corina Purcarea for proposing this feature and
  participating in its development!
  [#96](https://github.com/thibaultcha/lua-resty-mlcache/pull/96)

#### Fixed

- Improve `update()` robustness to worker crashes. Now, the library behind
  `cache:update()` is much more robust to re-spawned workers when initialized in
  the `init_by_lua` phase.
  [#97](https://github.com/thibaultcha/lua-resty-mlcache/pull/97)
- Document the `peek()` method `stale` argument which was not mentioned, as well
  as the possibility of negative TTL return values for expired items.

[Back to TOC](#table-of-contents)

## [2.4.1]

> Released on: 2020/01/17

#### Fixed

- The IPC module now avoids replaying all events when spawning new workers, and
  gets initialized with the latest event index instead.
  [#88](https://github.com/thibaultcha/lua-resty-mlcache/pull/88)

[Back to TOC](#table-of-contents)

## [2.4.0]

> Released on: 2019/03/28

#### Added

- A new `get_bulk()` API allows for fetching several values from the layered
  caches in a single call, and will execute all L3 callback functions
  concurrently, in a configurable pool of threads.
  [#77](https://github.com/thibaultcha/lua-resty-mlcache/pull/77)
- `purge()` now clears the L1 LRU cache with the new `flush_all()` method when
  used in OpenResty >= 1.13.6.2.
  Thanks [@Crack](https://github.com/Crack) for the patch!
  [#78](https://github.com/thibaultcha/lua-resty-mlcache/pull/78)

#### Fixed

- `get()` is now resilient to L3 callback functions calling `error()` with
  non-string arguments. Such functions could result in a runtime error when
  LuaJIT is compiled with `-DLUAJIT_ENABLE_LUA52COMPAT`.
  Thanks [@MartinAmps](https://github.com/MartinAmps) for the patch!
  [#75](https://github.com/thibaultcha/lua-resty-mlcache/pull/75)
- Instances using a custom L1 LRU cache in OpenResty < 1.13.6.2 are now
  restricted from calling `purge()`, since doing so would result in the LRU
  cache being overwritten.
  [#79](https://github.com/thibaultcha/lua-resty-mlcache/pull/79)

[Back to TOC](#table-of-contents)

## [2.3.0]

> Released on: 2019/01/17

#### Added

- Returning a negative `ttl` value from the L3 callback will now make the
  fetched data bypass the cache (it will still be returned by `get()`).
  This is useful when some fetched data indicates that it is not cacheable.
  Thanks [@eaufavor](https://github.com/eaufavor) for the patch!
  [#68](https://github.com/thibaultcha/lua-resty-mlcache/pull/68)

[Back to TOC](#table-of-contents)

## [2.2.1]

> Released on: 2018/07/28

#### Fixed

- When `get()` returns a value from L2 (shm) during its last millisecond of
  freshness, we do not erroneously cache the value in L1 (LRU) indefinitely
  anymore. Thanks [@jdesgats](https://github.com/jdesgats) and
  [@javierguerragiraldez](https://github.com/javierguerragiraldez) for the
  report and initial fix.
  [#58](https://github.com/thibaultcha/lua-resty-mlcache/pull/58)
- When `get()` returns a previously resurrected value from L2 (shm), we now
  correctly set the `hit_lvl` return value to `4`, instead of `2`.
  [307feca](https://github.com/thibaultcha/lua-resty-mlcache/commit/307fecad6adac8755d4fcd931bbb498da23d069c)

[Back to TOC](#table-of-contents)

## [2.2.0]

> Released on: 2018/06/29

#### Added

- Implement a new `resurrect_ttl` option. When specified, `get()` will behave
  in a more resilient way upon errors, and in particular callback errors.
  [#52](https://github.com/thibaultcha/lua-resty-mlcache/pull/52)
- New `stale` argument to `peek()`. When specified, `peek()` will return stale
  shm values.
  [#52](https://github.com/thibaultcha/lua-resty-mlcache/pull/52)

[Back to TOC](#table-of-contents)

## [2.1.0]

> Released on: 2018/06/14

#### Added

- Implement a new `shm_locks` option. This option receives the name of a
  lua_shared_dict, and, when specified, the mlcache instance will store
  lua-resty-lock objects in it instead of storing them in the cache hits
  lua_shared_dict. This can help reducing LRU churning in some workloads.
  [#55](https://github.com/thibaultcha/lua-resty-mlcache/pull/55)
- Provide stack traceback in `err` return value when the L3 callback throws an
  error.
  [#56](https://github.com/thibaultcha/lua-resty-mlcache/pull/56)

#### Fixed

- Ensure `no memory` errors returned by shm insertions are properly returned
  by `set()`.
  [#53](https://github.com/thibaultcha/lua-resty-mlcache/pull/53)

[Back to TOC](#table-of-contents)

## [2.0.2]

> Released on: 2018/04/09

#### Fixed

- Make `get()` lookup in shm after lock timeout. This prevents a possible (but
  rare) race condition under high load. Thanks to
  [@jdesgats](https://github.com/jdesgats) for the report and initial fix.
  [#49](https://github.com/thibaultcha/lua-resty-mlcache/pull/49)

[Back to TOC](#table-of-contents)

## [2.0.1]

> Released on: 2018/03/27

#### Fixed

- Ensure the `set()`, `delete()`, `peek()`, and `purge()` method properly
  support the new `shm_miss` option.
  [#45](https://github.com/thibaultcha/lua-resty-mlcache/pull/45)

[Back to TOC](#table-of-contents)

## [2.0.0]

> Released on: 2018/03/18

This release implements numerous new features. The major version digit has been
bumped to ensure that the changes to the interpretation of the callback return
values (documented below) do not break any dependent application.

#### Added

- Implement a new `purge()` method to clear all cached items in both
  the L1 and L2 caches.
  [#34](https://github.com/thibaultcha/lua-resty-mlcache/pull/34)
- Implement a new `shm_miss` option. This option receives the name
  of a lua_shared_dict, and when specified, will cache misses there instead of
  the instance's `shm` shared dict. This is particularly useful for certain
  types of workload where a large number of misses can be triggered and
  eventually evict too many cached values (hits) from the instance's `shm`.
  [#42](https://github.com/thibaultcha/lua-resty-mlcache/pull/42)
- Implement a new `l1_serializer` callback option. It allows the
  deserialization of data from L2 or L3 into arbitrary Lua data inside the LRU
  cache (L1). This includes userdata, cdata, functions, etc...
  Thanks to [@jdesgats](https://github.com/jdesgats) for the contribution.
  [#29](https://github.com/thibaultcha/lua-resty-mlcache/pull/29)
- Implement a new `shm_set_tries` option to retry `shm:set()`
  operations and ensure LRU eviction when caching values of disparate sizes.
  [#41](https://github.com/thibaultcha/lua-resty-mlcache/issues/41)
- The L3 callback can now return `nil + err`, which will be bubbled up
  to the caller of `get()`. Prior to this change, the second return value of
  callbacks was ignored, and users had to throw hard Lua errors from inside
  their callbacks.
  [#35](https://github.com/thibaultcha/lua-resty-mlcache/pull/35)
- Support for custom IPC module.
  [#31](https://github.com/thibaultcha/lua-resty-mlcache/issues/31)

#### Fixed

- In the event of a `no memory` error returned by the L2 lua_shared_dict cache
  (after the number of `shm_set_tries` failed), we do not interrupt the `get()`
  flow to return an error anymore. Instead, the retrieved value is now bubbled
  up for insertion in L1, and returned to the caller. A warning log is (by
  default) printed in the nginx error logs.
  [#41](https://github.com/thibaultcha/lua-resty-mlcache/issues/41)

[Back to TOC](#table-of-contents)

## [1.0.1]

> Released on: 2017/08/26

#### Fixed

- Do not rely on memory address of mlcache instance in invalidation events
  channel names. This ensures invalidation events are properly broadcasted to
  sibling instances in other workers.
  [#27](https://github.com/thibaultcha/lua-resty-mlcache/pull/27)

[Back to TOC](#table-of-contents)

## [1.0.0]

> Released on: 2017/08/23

Initial release.

[Back to TOC](#table-of-contents)

[2.6.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.5.0...2.6.0
[2.5.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.4.1...2.5.0
[2.4.1]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.4.0...2.4.1
[2.4.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.3.0...2.4.0
[2.3.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.2.1...2.3.0
[2.2.1]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.2.0...2.2.1
[2.2.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.1.0...2.2.0
[2.1.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.0.2...2.1.0
[2.0.2]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.0.1...2.0.2
[2.0.1]: https://github.com/thibaultcha/lua-resty-mlcache/compare/2.0.0...2.0.1
[2.0.0]: https://github.com/thibaultcha/lua-resty-mlcache/compare/1.0.1...2.0.0
[1.0.1]: https://github.com/thibaultcha/lua-resty-mlcache/compare/1.0.0...1.0.1
[1.0.0]: https://github.com/thibaultcha/lua-resty-mlcache/tree/1.0.0
