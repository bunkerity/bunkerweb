LuaLogging
==========

[![Test](https://img.shields.io/github/actions/workflow/status/lunarmodules/lualogging/test.yml?label=Test&branch=master&logo=linux)](https://github.com/lunarmodules/lualogging/actions?workflow=Test)
[![Luacheck](https://img.shields.io/github/actions/workflow/status/lunarmodules/lualogging/luacheck.yml?label=Luacheck&logo=Lua&branch=master)](https://github.com/lunarmodules/lualogging/actions?workflow=Luacheck)
[![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/lunarmodules/lualogging?logo=semver)](https://github.com/lunarmodules/lualogging/releases)
[![Luarocks](https://img.shields.io/luarocks/v/tieske/lualogging?label=Luarocks&logo=Lua)](https://luarocks.org/modules/tieske/lualogging)

https://lunarmodules.github.io/lualogging/

LuaLogging provides a simple API to use logging features in Lua.
Its design was based on log4j. LuaLogging currently supports,
through the use of appenders, console, file, rolling file, email, socket and sql outputs.

LuaLogging is free software and uses the same license as Lua. It is part of the Kepler Project.

Please see docs at https://lunarmodules.github.io/lualogging/ for more details

Installation
============

With LuaRocks:

```sh
luarocks install lualogging
```

Latest Git revision
-------------------

With LuaRocks:

```sh
luarocks install lualogging --dev
```

With make:

```sh
sudo make
```

Copyright
=========

See [LICENSE file](https://github.com/lunarmodules/lualogging/blob/master/COPYRIGHT)

History and changelog
=====================

For the changelog see the [online documentation](https://lunarmodules.github.io/lualogging/index.html#history).

### Releasing a new version

 - update changelog in docs (`index.html`, update `history` and `status` sections)
 - update version in `logging.lua`
 - update copyright years if needed
 - update rockspec
 - commit as `release X.Y.Z`
 - tag as `vX.Y.Z`
 - push commit and tag
 - upload to luarocks
 - test luarocks installation
