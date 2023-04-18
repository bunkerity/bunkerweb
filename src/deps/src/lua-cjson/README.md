Name
====

lua-cjson - Fast JSON encoding/parsing

Table of Contents
=================

* [Name](#name)
* [Description](#description)
* [Additions to mpx/lua](#additions)
    * [encode_empty_table_as_object](#encode_empty_table_as_object)
    * [empty_array](#empty_array)
    * [array_mt](#array_mt)
    * [empty_array_mt](#empty_array_mt)
    * [encode_number_precision](#encode_number_precision)
    * [encode_escape_forward_slash](#encode_escape_forward_slash)
    * [decode_array_with_array_mt](#decode_array_with_array_mt)

Description
===========

This fork of [mpx/lua-cjson](https://github.com/mpx/lua-cjson) is included in
the [OpenResty](https://openresty.org/) bundle and includes a few bugfixes and
improvements, especially to facilitate the encoding of empty tables as JSON Arrays.

Please refer to the [lua-cjson documentation](http://www.kyne.com.au/~mark/software/lua-cjson.php)
for standard usage, this README only provides informations regarding this fork's additions.

See [`mpx/master..openresty/master`](https://github.com/mpx/lua-cjson/compare/master...openresty:master)
for the complete history of changes.

[Back to TOC](#table-of-contents)

Additions
=========

encode_empty_table_as_object
----------------------------
**syntax:** `cjson.encode_empty_table_as_object(true|false|"on"|"off")`

Change the default behavior when encoding an empty Lua table.

By default, empty Lua tables are encoded as empty JSON Objects (`{}`). If this is set to false,
empty Lua tables will be encoded as empty JSON Arrays instead (`[]`).

This method either accepts a boolean or a string (`"on"`, `"off"`).

[Back to TOC](#table-of-contents)

empty_array
-----------
**syntax:** `cjson.empty_array`

A lightuserdata, similar to `cjson.null`, which will be encoded as an empty JSON Array by
`cjson.encode()`.

For example, since `encode_empty_table_as_object` is `true` by default:

```lua
local cjson = require "cjson"

local json = cjson.encode({
    foo = "bar",
    some_object = {},
    some_array = cjson.empty_array
})
```

This will generate:

```json
{
    "foo": "bar",
    "some_object": {},
    "some_array": []
}
```

[Back to TOC](#table-of-contents)

array_mt
--------
**syntax:** `setmetatable({}, cjson.array_mt)`

When lua-cjson encodes a table with this metatable, it will systematically
encode it as a JSON Array. The resulting, encoded Array will contain the array
part of the table, and will be of the same length as the `#` operator on that
table. Holes in the table will be encoded with the `null` JSON value.

Example:

```lua
local t = { "hello", "world" }
setmetatable(t, cjson.array_mt)
cjson.encode(t) -- ["hello","world"]
```

Or:

```lua
local t = {}
t[1] = "one"
t[2] = "two"
t[4] = "three"
t.foo = "bar"
setmetatable(t, cjson.array_mt)
cjson.encode(t) -- ["one","two",null,"three"]
```

This value was introduced in the `2.1.0.5` release of this module.

[Back to TOC](#table-of-contents)

empty_array_mt
--------------
**syntax:** `setmetatable({}, cjson.empty_array_mt)`

A metatable which can "tag" a table as a JSON Array in case it is empty (that is, if the
table has no elements, `cjson.encode()` will encode it as an empty JSON Array).

Instead of:

```lua
local function serialize(arr)
    if #arr < 1 then
        arr = cjson.empty_array
    end

    return cjson.encode({some_array = arr})
end
```

This is more concise:

```lua
local function serialize(arr)
    setmetatable(arr, cjson.empty_array_mt)

    return cjson.encode({some_array = arr})
end
```

Both will generate:

```json
{
    "some_array": []
}
```

[Back to TOC](#table-of-contents)

encode_number_precision
-----------------------
**syntax:** `cjson.encode_number_precision(precision)`

This fork allows encoding of numbers with a `precision` up to 16 decimals (vs. 14 in mpx/lua-cjson).

[Back to TOC](#table-of-contents)

encode_escape_forward_slash
---------------------------
**syntax:** `cjson.encode_escape_forward_slash(enabled)`

**default:** true

If enabled, forward slash '/' will be encoded as '\\/'.

If disabled, forward slash '/' will be encoded as '/' (no escape is applied).

[Back to TOC](#table-of-contents)

decode_array_with_array_mt
--------------------------
**syntax:** `cjson.decode_array_with_array_mt(enabled)`

**default:** false

If enabled, JSON Arrays decoded by `cjson.decode` will result in Lua
tables with the [`array_mt`](#array_mt) metatable. This can ensure a 1-to-1
relationship between arrays upon multiple encoding/decoding of your
JSON data with this module.

If disabled, JSON Arrays will be decoded to plain Lua tables, without
the `array_mt` metatable.

The `enabled` argument is a boolean.

Example:

```lua
local cjson = require "cjson"

-- default behavior
local my_json = [[{"my_array":[]}]]
local t = cjson.decode(my_json)
cjson.encode(t) -- {"my_array":{}} back to an object

-- now, if this behavior is enabled
cjson.decode_array_with_array_mt(true)

local my_json = [[{"my_array":[]}]]
local t = cjson.decode(my_json)
cjson.encode(t) -- {"my_array":[]} properly re-encoded as an array
```

[Back to TOC](#table-of-contents)
