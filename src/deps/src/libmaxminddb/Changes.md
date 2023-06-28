## 1.7.1 - 2022-09-30

* The external symbols test now only runs on Linux. It assumes a Linux
  environment. Reported by Carlo Cabrera. GitHub #304.

## 1.7.0 - 2022-09-28

* `FD_CLOEXEC` is now set on platforms that do not support `O_CLOEXEC`.
  Reported by rittneje. GitHub #273.
* When building with Visual Studio, you may now build a static runtime with
  CMake by setting `MSVC_STATIC_RUNTIME` to `ON`. Pull request by Rafael
  Santiago. GitHub #269.
* The CMake build now works on iOS. Pull request by SpaceIm. GitHub #271.
* The CMake build now uses the correct library directory on Linux systems
  using alternate directory structures. Pull request by Satadru Pramanik.
  GitHub #284.
* File size check now correctly compares the size to `SSIZE_MAX`. Reported
  by marakew. GitHub #301.

## 1.6.0 - 2021-04-29

* This release includes several improvements to the CMake build. In
  particular:
  * C99 support is now properly enabled, fixing builds on older `gcc`
    versions. Pull request by Jan Včelák. GitHub #257.
  * `CMAKE_SHARED_LIBRARY_PREFIX` and `CMAKE_STATIC_LIBRARY_PREFIX` are
    no longer explicitly set and now use the default values for the platform.
    Pull request by Jan Včelák. GitHub #258.
  * `target_include_directories` now works as expected. Pull request by Jan
    Včelák. GitHub #259.
  * DLLs are now installed on Windows when `libmaxminddb` is built as a
    shared library. Pull request by Jan Včelák. GitHub #261.
  * When built as a dynamic library on Windows, all symbols are now exported.
    Pull request by Jan Včelák. GitHub #262.


## 1.5.2 - 2021-02-18

* With `libmaxminddb` on Windows and `mmdblookup` generally, there were
  instances where the return value of `calloc` was not checked, which could
  lead to issues in low memory situations or when resource limits had been
  set. Reported by cve-reporting. GitHub #252.


## 1.5.1 - 2021-02-18

* The formatting of the manpages has been improved and the script that
  generates them now supports `lowdown` in addition to `pandoc`. Pull request
  by Faidon Liambotis. GitHub #248.


## 1.5.0 - 2021-01-05

* A CMake build script has been added for Windows builds. The Visual
  Studio project files in `projects` are now considered deprecated and will
  be removed in a future release.


## 1.4.3 - 2020-08-06

* On Windows, always call `CreateFileW` instead of `CreateFile`.
  `CreateFile` could be mapped to `CreateFileA` and not work as expected.
  Pull request by Sandu Liviu Catalin. GitHub #228.
* Fixed use of uninitialized memory in `dump_entry_data_list()` that could
  cause a heap buffer overflow in `mmdblookup`. As part of this fix, most
  uses of `malloc` were replaced with `calloc`. Reported by azhou. GitHub
  #236.


## 1.4.2 - 2019-11-02

* The 1.4.0 release introduced a change that increased the size of `MMDB_s`,
  unintentionally causing an ABI break. This release reverts the relevant
  commit.


## 1.4.1 - 2019-11-01

* The man page links for function calls were not generated correctly in
  1.4.0. This has been corrected.


## 1.4.0 - 2019-11-01

* A negative array index may now be used with `MMDB_get_value`,
  `MMDB_vget_value`, and `MMDB_aget_value`. This specifies the element
  from the end of the array. For instance, `-1` would refer to the
  last element of the array. PR by Kyle Box. GitHub #205.
* On Windows, the file name passed to `MMDB_open` is now expected to be
  UTF-8 encoded. This allows Unicode characters to be used in file names.
  As part of this change, `mmdblookup` on Windows now converts its
  arguments to UTF-8. PR by Gerald Combs. GitHub #189 & #191.
* Fix a memory leak that occurred when freeing an `MMDB_s` where the
  database had no languages defined in the metadata. If you are using an
  official MaxMind database, this leak does not affect you. Pull request
  by Kókai Péter. GitHub #180.
* Add `--disable-binaries` option to `configure`. Pull request by Fabrice
  Fontaine. GitHub #166.
* Previous releases incorrectly included `*.Po` files in the `t` directory.
  This has been corrected. Reported by Daniel Macks. GitHub #168.
* The internal use of the `MMDB_s` now has the `const` modifier. Public
  functions that accepted an `MMDB_s` as an argument now also declare it as
  `const`. Pull request by Kurt Johnson. GitHub #199.
* `mmdblookup` now displays the prefix length for the record when using
  the verbose flag. GitHub #172.


## 1.3.2 - 2018-01-17

* Allocate memory for `MMDB_entry_data_list_s` structs in separate chunks
  rather than one large chunk. This simplifies accessing memory in
  `MMDB_get_entry_data_list()` and increases performance. It builds on the
  changes in 1.3.0 and 1.3.1.
* We no longer export `data_pool_*` symbols. These are internal functions
  but we were previously exporting them. Pull request by Faidon Liambotis.
  GitHub #162.
* Build with POSIX.1-2008 by default if the system supports it. This allows
  use of `open()` with `O_CLOEXEC`. We retain support for systems that
  provide only POSIX.1-2001.
* Open the database with the `O_CLOEXEC` flag if the system provides it.
  This avoids cases where we could leak fds when called in multi-threaded
  programs that `fork()` and `exec()`. Original report and PR by Brandon L
  Black.
* Added a test to ensure we export only intended symbols (e.g. MMDB_*).


## 1.3.1 - 2017-11-24

* Fix build problems related to `rpl_malloc()`. Pull request by Rainer
  Gerhards. GitHub #152.
* Fix a race to set and read data in a field on the `MMDB_s` struct
  (`ipv4_start_node`). GitHub #153.
* Fix cases of invalid memory access when using
  `MMDB_get_entry_data_list()`. This was introduced in 1.3.0 and occurred
  when performing large lookups. GitHub #153.


## 1.3.0 - 2017-11-10

* Perform fewer memory allocations in `MMDB_get_entry_data_list()`. This
  significantly improves its performance. GitHub #147.
* Fix `mmdblookup`'s build epoch reporting on some systems. Big endian
  systems with a 32-bit `time_t` no longer show a database build date of
  1970-01-01 00:00:00. Pull request by Rainer Jung. GitHub #143.


## 1.2.1 - 2017-05-15

* Use autoconf to check the system's endianness rather than trying to do this
  with compiler-defined macros like `__BYTE_ORDER__`. Apparently this didn't
  work properly on a Sparc system. GitHub #120.
* Several compiler warnings on Visual C++ were fixed. Pull request by Marcel
  Raad. GitHub #130.
* Fix segmentation faults found in `MMDB_open()` using afl-fuzz. This
  occurred on corrupt databases that had a data pointer large enough to
  cause an integer overflow when doing bound checking. Reported by Ryan
  Whitworth. GitHub #140.
* Add --disable-tests option to `configure`. Pull request by Fabrice
  Fontaine. GitHub #136.


## 1.2.0 - 2016-03-23

* Four additional fields were added to the end of the `MMDB_search_node_s`
  struct returned by `MMDB_read_node`. These fields allow the user to iterate
  through the search tree without making undocumented assumptions about how
  this library works internally and without knowing the specific details of
  the database format. GitHub #110.


## 1.1.5 - 2016-03-20

* Previously, reading a database with a pointer in the metadata would cause an
  `MMDB_INVALID_METADATA_ERROR` to be returned. This was due to an invalid
  offset being used when calculating the pointer. The `data_section` and
  `metadata_section` fields now both point to the beginning of the data
  section. Previously, `data_section` pointed to the beginning of the data
  separator. This will not affect anyone using only documented fields from
  `MMDB_s`.
* `MMDB_lookup_sockaddr` will set `mmdb_error` to
  `MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR` if an IPv6 `sockaddr` is looked up
  in an IPv4-only database. Previously only `MMDB_lookup_string` would set
  this error code.
* When resolving an address, this library now relies on `getaddrinfo` to
  determine the address family rather than trying to guess it itself.


## 1.1.4 - 2016-01-06

* Packaging fixes. The 1.1.3 tarball release contained a lot of extra junk in
  the t/ directory.


## 1.1.3 - 2016-01-05

* Added several additional checks to make sure that we don't attempt to read
  past the end of the databases's data section. Implemented by Tobias
  Stoeckmann. GitHub #103.
* When searching for the database metadata, there was a bug that caused the
  code to think it had found valid metadata when none existed. In addition,
  this could lead to an attempt to read past the end of the database
  entirely. Finally, if there are multiple metadata markers in the database,
  we treat the final one as the start of the metdata, instead of the first.
  Implemented by Tobias Stoeckmann. GitHub #102.
* Don't attempt to mmap a file that is too large to be mmapped on the
  system. Implemented by Tobias Stoeckmann. GitHub #101.
* Added a missing out of memory check when reading a file's
  metadata. Implemented by Tobias Stoeckmann. GitHub #101.
* Added several additional checks to make sure that we never attempt to
  `malloc` more than `SIZE_MAX` memory, which would lead to integer
  overflow. This could only happen with pathological databases. Implemented by
  Tobias Stoeckmann. GitHub #101.


## 1.1.2 - 2015-11-16

* IMPORTANT: This release includes a number of important security fixes. Among
  these fixes is improved validation of the database metadata. Unfortunately,
  MaxMind GeoIP2 and GeoLite2 databases created earlier than January 28, 2014
  had an invalid data type for the `record_size` in the metadata. Previously
  these databases worked on little endian machines with libmaxminddb but did
  not work on big endian machines. Due to increased safety checks when reading
  the file, these databases will no longer work on any platform. If you are
  using one of these databases, we recommend that you upgrade to the latest
  GeoLite2 or GeoIP2 database
* Added pkg-config support. If your system supports it, then running `make
  install` now installs a `libmaxminddb.pc` file for pkgconfig. Implemented by
  Jan Vcelak.
* Several segmentation faults found with afl-fuzz were fixed. These were
  caused by missing bounds checking and missing data type verification checks.
* `MMDB_get_entry_data_list` will now fail on data structures with a depth
  greater than 512 and data structures that are cyclic. This should not
  affect any known MaxMind DB in production. All databases produced by
  MaxMind have a depth of less than five.


## 1.1.1 - 2015-07-22

* Added `maxminddb-compat-util.h` as a source file to dist.


## 1.1.0 - 2015-07-21

* Previously, when there was an error in `MMDB_open()`, `errno` would
  generally be overwritten during cleanup, preventing a useful value from
  being returned to the caller. This was changed so that the `errno` value
  from the function call that caused the error is restored before returning to
  the caller. In particular, this is important for `MMDB_IO_ERROR` errors as
  checking `errno` is often the only way to determine what actually failed.
* If `mmap()` fails due to running out of memory space, an
  `MMDB_OUT_OF_MEMORY_ERROR` is now returned from `MMDB_open` rather than an
  `MMDB_IO_ERROR`.
* On Windows, the `CreateFileMappingA()` handle was not properly closed if
  opening the database succeeded. Fixed by Bly Hostetler. GitHub #75 & #76.
* On Windows, we were not checking the return value of `CreateFileMappingA()`
  properly for errors. Fixed by Bly Hotetler. GitHub #78.
* Several warnings from Clang's scan-build were fixed. GitHub #86.
* All headers are now installed in `$(includedir)`. GitHub #89.
* We no longer install `maxminddb-compat-util.h`. This header was intended for
  internal use only.


## 1.0.4 - 2015-01-02

* If you used a non-integer string as an array index when doing a lookup with
  `MMDB_get_value()`, `MMDB_vget_value()`, or `MMDB_aget_value()`, the first
  element of the array would be returned rather than an error. A
  `MMDB_LOOKUP_PATH_DOES_NOT_MATCH_DATA_ERROR` error will now be returned.
  GitHub #61.
* If a number larger than `LONG_MAX` was used in the same functions,
  `LONG_MAX` would have been used in the lookup. Now a
  `MMDB_INVALID_LOOKUP_PATH_ERROR` error will be returned.
* Visual Studio build files were added for unit tests and some compatibility
  issues with the tests were fixed.
* Visual Studio project was updated to use property pages. Patch by Andre.
  GitHub #69.
* A test failure in `t/compile_c++_t.pl` on new installs was fixed.


## 1.0.3 - 2014-12-02

* A memory and file handle leak on Win32 was fixed when getting the database
  size fails. Patch by Federico G. Schwindt. GitHub PR #49.
* Documentation fix. Federico G. Schwindt. GitHub PR #50.
* Added Visual Studio build files and fixed incorrect CreateFileMappingA
  usage. Patch by Andre. GitHub #52.
* The includes for the Windows header files were made lowercase in order to
  match the actual file names on case-sensitive file systems. GitHub PR #57.
* Removed `realloc()` calls that caused warnings on Windows and generally
  cleaned up memory allocation in `MMDB_vget_value()`. See relevant discussion
  in GitHub #52.
* Added an `extern "C" { ... }` wrapper to maxminddb.h when compiling with a
  C++ compiler. GitHub #55.


## 1.0.2 - 2014-09-22

* Fixed a number of small issues found by Coverity.
* When freeing the MMDB struct in `MMDB_close()` we make sure to set the
  pointers to NULL after freeing the memory they point to. This makes it safe
  to call `MMDB_close` more than once on the same `MMDB_s` struct
  pointer. Before this change, calling this function twice on the same pointer
  could cause the code to free memory that belonged to something else in the
  process. Patch by Shuxin Yang. GitHub PR #41.


## 1.0.1 - 2014-09-03

* Added missing LICENSE and NOTICE files to distribution. No code changes.


## 1.0.0 - 2014-09-02

* Bumped version to 1.0.0. No code changes.


## 0.5.6 - 2014-07-21

* There was a leak in the `MMDB_open()` sub when it was called against a file
  which did not contain any MMDB metadata. Reported by Federico
  G. Schwindt. GitHub issue #36.
* Fixed an error that occurred when passing AI_V4MAPPED to `getaddrinfo()` on
  FreeBSD. Apparently this macro is defined but doesn't work the way we
  expected it to on that platform.
* Made sure to call `freeaddrinfo()` when a call to `getaddrinfo()` fails but
  still allocated memory.
* Fixed a segfault in the tests that occurred on FreeBSD if we passed a NULL
  value to `freeaddrinfo()`.
* Added a missing step to the README.md file for installing from our GitHub
  repository. Patch by Yasith Fernando.
* Added instructions for installing via Homebrew. Patch by Yasith Fernando.


## 0.5.5 - 2014-03-11

* The previous tarball failed to compile because it was missing the
  src/maxminddb-compat-util.h file. Reported by Günter Grodotzki. GitHub issue
  #18.


## 0.5.4 - 2014-03-03

* Added support for compiling in the MinGW environment. Patch by Michael
  Eisendle.
* Added const declarations to many spots in the public API. None of these
  should require changes to existing code.
* Various documentation improvements.
* Changed the license to the Apache 2.0 license.


## 0.5.3 - 2013-12-23

* The internal value_for_key_as_uint16 method was returning a uint32_t instead
  of a uint16_t. Reported by Robert Wells. GitHub issue #11.
* The ip_version member of the MMDB_metadata_s struct was a uint8_t, even
  though the docs and spec said it should be a uint16_t. Reported by Robert
  Wells. GitHub issue #11.
* The mmdblookup_t.pl test now reports that it needs IPC::Run3 to run (which
  it always did, but it didn't tell you this). Patch by Elan Ruusamäe. GitHub
  issue #10.


## 0.5.2 - 2013-11-20

* Running `make` from the tarball failed. This is now fixed.


## 0.5.1 - 2013-11-20

* Renamed MMDB_LOOKUP_PATH_DOES_NOT_MATCH_DATA define to
  MMDB_LOOKUP_PATH_DOES_NOT_MATCH_DATA_ERROR for consistency. Fixes github
  issue #5. Reported by Albert Strasheim.
* Updated README.md to show git clone with --recursive flag so you get the
  needed submodules. Fixes github issue #4. Reported by Ryan Peck.
* Fixed some bugs with the MMDB_get_*value functions when navigating a data
  structure that included pointers. Fixes github issue #3. Reported by
  bagadon.
* Fixed compilation problems on OSX and OpenBSD. We have tested this on OSX
  and OpenBSD 5.4. Fixes github issue #6.
* Removed some unneeded memory allocations and added const to many variable
  declarations. Based on patches by Timo Teräs. Github issue #8.
* Added a test that uses threads to check for thread safety issue in the
  library.
* Distro tarball now includes man pages, tests, and test data
