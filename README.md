
# LuaJIT bindings to MaxMind's GeoIP and GeoIP2 (libmaxminddb) libraries

* https://github.com/maxmind/libmaxminddb
* https://github.com/maxmind/geoip-api-c &mdash; legacy library

In order to use this library you'll need LuaJIT, the GeoIP library you're
trying to use, and the databases files for the appropriate library. You should
be able to find these in your package manager.

**I recommend using libmaxminddb**, as the legacy GeoIP databases are no
longer updated.

## Install

```bash
luarocks install --server=http://luarocks.org/manifests/leafo geoip
```

# Reference

## libmaxminddb

The module is named `geoip.mmdb`

```lua
local geoip = require "geoip.mmdb"
```

This module works great in OpenResty. You'll want to keep references to loaded
GeoIP DB objects at the module level, in order avoid reloading the DB on every
request. 

<details>

<summary>See OpenResty example</summary>

Create a new module for your GeoIP databases:

**`geoip_helper.lua`**

```lua
local geoip = require "geoip.mmdb"

return {
  country_db = assert(geoip.load_database("/var/lib/GeoIP/GeoLite2-Country.mmdb")),
  -- load more databases if necessary:
  -- asnum_db = ...
  -- etc.
}
```

**OpenResty request handler:**

```lua
-- this module will be cached in `package.loaded`, and the databases will only be loaded on first access
local result = require("geoip_helper").country_db.lookup_addr(ngx.var.remote_addr)
if result then
  ngx.say("Your country:" .. result.country.iso_code)
end
```

> **Note:** If you're using a proxy with x-forwarded-for you'll need to adjust
> how you access the user's IP address

</details>


### `db, err = load_database(file_name)`

Load the database from the file path. Returns `nil` and error message if the
database could not be loaded.

The location of database files vary depending on the system and type of
database. For this example we'll use the country database located at
`/var/lib/GeoIP/GeoLite2-Country.mmdb`.


```lua
local mmdb = assert(geoip.load_database("/var/lib/GeoIP/GeoLite2-Country.mmdb"))
```

The database object has the following methods:


### `object, err = mmdb:lookup(address)`

```lua
local result = assert(mmdb:lookup("8.8.8.8"))

-- print the country code 
print(result.country.iso_code) --> US
```

Look up an address (as a string), and return all data about it as a Lua table.
Returns `nil` and an error if the address could not be looked up, or there was
no information for that address.

> Note: You can lookup both ipv4 and ipv6 addresses

The structure of the output depends on the database used. (It matches the
structure of the out from the `mmdblookup` utility, if you need a quick way to
check)

### `value, err = mmdb:lookup_value(address, ...)`

```lua
-- prints the country code
print(assert(mmdb:lookup_value("8.8.8.8", "country", "iso_code"))) --> US
```

Looks up a single value for an address using the path specified in the varargs
`...`. Returns `nil` and an error if the address is invalid or a value was not
located at the path. This method avoids scanning the entire object for an
address's entry, so it may be more efficient if a specific value from the
database is needed.


## geoip &mdash; legacy

*The databases for this library are no longer updated, I strongly recommend
using the mmdb functionality above*

The module is named `geoip`

```lua
local geoip = require "geoip"
```

GeoIP has support for many different database types.  The available lookup
databases are automatically loaded from the system location.

Only the country and ASNUM databases are supported. Feel free to create a pull
request with support for more.

### `res, err = lookup_addr(ip_address)`

Look up information about an address. Returns an table with properties about
that address extracted from all available databases.


```lua
local geoip = require "geoip"
local res = geoip.lookup_addr("8.8.8.8")

print(res.country_code)
```

The structure of the return value looks like this:

```lua
{
  country_code = "US",
  country_name = "United States",
  asnum = "AS15169 Google Inc."
}
```

### Controlling database caching

You can control how the databases are loaded by manually instantiating a
`GeoIP` object and calling the `load_databases` method directly. `lookup_addr`
will automatically load databases only if they haven't been loaded yet.

```lua
local geoip = require("geoip")

local gi = geoip.GeoIP()
gi:load_databases("memory")

local res = gi:lookup_addr("8.8.8.8")
```

> By default the STANDARD mode is used, which reads from disk for each lookup


# Version history


* **2.1** *(Aug 28, 2020)* &mdash; Fix bug with parsing booleans from mmdb ([#3](https://github.com/leafo/luajit-geoip/pull/3)) michaeljmartin 
* **2.0** *(Apr 6, 2020)* &mdash; Support for mmdb (libmaxminddb), fix memory leak in geoip
* **1.0** *(Apr 4, 2018)* &mdash; Initial release, support for geoip

# Contact

License: MIT, Copyright 2020
Author: Leaf Corcoran (leafo) ([@moonscript](http://twitter.com/moonscript))  
Email: leafot@gmail.com  
Homepage: <http://leafo.net>  

