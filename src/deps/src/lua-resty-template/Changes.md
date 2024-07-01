# Changelog

All notable changes to `lua-resty-template` will be documented in this file.


## [2.0] - 2020-02-24
### Added
- Support for `template.new()`, `template.new(options)` and `template.new(safe)` (a `boolean`)
- Added `safe` implementation `require "resty.template.safe"`
- Added `echo` helper function to template (#28)
- Added `template.load_file` and `template.load_string` functions
- Added `template.compile_file` and `template.compile_string` functions
- Added `template.parse_file` and `template.parse_string` functions
- Added `template.render_file` and `template.render_string` functions
- Added `template.precompile_file` and `template.precompile_string` functions
- Added `template.process`, `template.process_file` and `template.process_string` functions
- Added `template.root` and `template.location` properties
- Added `template.visit` function (#36)

### Changed
- When `plain` equals to `false` the file io issues are considered
  fatal, and assertions are thrown (#32)

### Fixed
- Wrong template returned when using multiple server blocks (#25)
- Add a pure lua configure method (#23, #7)


## [1.9] - 2016-09-29
### Added
- Support for the official OpenResty package manager (opm).

### Changed
- Changed the change log format to keep-a-changelog.


## [1.8] - 2016-06-14
### Added
- Allow pass layout as a template object to template.new.


## [1.7] - 2016-05-11
### Fixed
- The loadngx was not working properly on non-file input.
  See also: https://github.com/bungle/lua-resty-template/pull/19
  Thanks @zhoukk


## [1.6] - 2016-04-25
### Added
- Added short escaping syntax.


## [1.5] - 2015-02-10
### Added 
- Support for {-verbatim-}...{-verbatim-}, and {-raw-}...{-raw-} blocks
  (contents is not processed by template).
  Please note that this could break your templates if you have used
  blocks with names "verbatim" or "raw".

### Fixed
- Issue #8: not returning value when using template.new and its render
  function.


## [1.4] - 2014-12-03
### Added
- Added support for {[expression include]} syntax.

### Changed
- Rewrote template.parse (cleaned up, less repetition of code, and
  better handling of new lines - i.e. doesn't eat newlines anymore.
  Also some adjustments to preceding spaces (space, tab, NUL-byte,
  and vertical tabs) on some tags ({% ... %}, {-block-} ... {-block-},
  and {# ... #}) for a cleaner output.


## [1.3] - 2014-11-06
### Added
- Small modification to html helper example to handle valueless tag
  attributess in HTML5 style.

### Fixed
- Fixed a bug when a view was missing from context when using layouts.


## [1.2] - 2014-09-29
### Fixed
- Fixes nasty recursion bug (reported in bug #5) where sub-templates
  modify the context table. Thank you for reporting this @DDarko.

  
## [1.1] - 2014-09-10
### Added
- Added _VERSION information to the module.
- Added CHANGES file to the project (this file).

### Changed
- Lua > 5.1 uses _ENV instead of _G (Lua 5.1 uses _G). Future Proofing
  if Lua is deprecating _G in Lua 5.3.


## [1.0] - 2014-08-28
### Added
- LuaRocks Support via MoonRocks.
