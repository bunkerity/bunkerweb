# vim:ft=

use lib '.';
use TestLua;

plan tests => 2 * blocks();

run_tests();

__DATA__

=== TEST 1: empty tables as objects
--- lua
local cjson = require "cjson"
print(cjson.encode({}))
print(cjson.encode({dogs = {}}))
--- out
{}
{"dogs":{}}



=== TEST 2: empty tables as arrays
--- lua
local cjson = require "cjson"
cjson.encode_empty_table_as_object(false)
print(cjson.encode({}))
print(cjson.encode({dogs = {}}))
--- out
[]
{"dogs":[]}



=== TEST 3: empty tables as objects (explicit)
--- lua
local cjson = require "cjson"
cjson.encode_empty_table_as_object(true)
print(cjson.encode({}))
print(cjson.encode({dogs = {}}))
--- out
{}
{"dogs":{}}



=== TEST 4: empty_array userdata
--- lua
local cjson = require "cjson"
print(cjson.encode({arr = cjson.empty_array}))
--- out
{"arr":[]}



=== TEST 5: empty_array_mt
--- lua
local cjson = require "cjson"
local empty_arr = setmetatable({}, cjson.empty_array_mt)
print(cjson.encode({arr = empty_arr}))
--- out
{"arr":[]}



=== TEST 6: empty_array_mt and empty tables as objects (explicit)
--- lua
local cjson = require "cjson"
local empty_arr = setmetatable({}, cjson.empty_array_mt)
print(cjson.encode({obj = {}, arr = empty_arr}))
--- out
{"arr":[],"obj":{}}



=== TEST 7: empty_array_mt and empty tables as objects (explicit)
--- lua
local cjson = require "cjson"
cjson.encode_empty_table_as_object(true)
local empty_arr = setmetatable({}, cjson.empty_array_mt)
local data = {
  arr = empty_arr,
  foo = {
    obj = {},
    foobar = {
      arr = cjson.empty_array,
      obj = {}
    }
  }
}
print(cjson.encode(data))
--- out
{"foo":{"foobar":{"obj":{},"arr":[]},"obj":{}},"arr":[]}



=== TEST 8: empty_array_mt on non-empty tables
--- lua
local cjson = require "cjson"
cjson.encode_empty_table_as_object(true)
local array = {"hello", "world", "lua"}
setmetatable(array, cjson.empty_array_mt)
local data = {
  arr = array,
  foo = {
    obj = {},
    foobar = {
      arr = cjson.empty_array,
      obj = {}
    }
  }
}
print(cjson.encode(data))
--- out
{"foo":{"foobar":{"obj":{},"arr":[]},"obj":{}},"arr":["hello","world","lua"]}



=== TEST 9: array_mt on empty tables
--- lua
local cjson = require "cjson"
local data = {}
setmetatable(data, cjson.array_mt)
print(cjson.encode(data))
--- out
[]



=== TEST 10: array_mt on non-empty tables
--- lua
local cjson = require "cjson"
local data = { "foo", "bar" }
setmetatable(data, cjson.array_mt)
print(cjson.encode(data))
--- out
["foo","bar"]



=== TEST 11: array_mt on non-empty tables with holes
--- lua
local cjson = require "cjson"
local data = {}
data[1] = "foo"
data[2] = "bar"
data[4] = "last"
data[9] = "none"
setmetatable(data, cjson.array_mt)
print(cjson.encode(data))
--- out
["foo","bar",null,"last"]



=== TEST 12: decode() by default does not set array_mt on empty arrays
--- lua
local cjson = require "cjson"
local json = [[{"my_array":[]}]]
local t = cjson.decode(json)
local has_metatable = getmetatable(t.my_array) == cjson.array_mt
print("decoded JSON array has metatable: " .. tostring(has_metatable))
print(cjson.encode(t))
--- out
decoded JSON array has metatable: false
{"my_array":{}}



=== TEST 13: decode() sets array_mt on non-empty arrays if enabled
--- lua
local cjson = require "cjson"
cjson.decode_array_with_array_mt(true)
local json = [[{"my_array":["hello","world"]}]]
local t = cjson.decode(json)
t.my_array.hash_value = "adding a hash value"
-- emptying the array part
t.my_array[1] = nil
t.my_array[2] = nil
local has_metatable = getmetatable(t.my_array) == cjson.array_mt
print("decoded JSON array has metatable: " .. tostring(has_metatable))
print(cjson.encode(t))
--- out
decoded JSON array has metatable: true
{"my_array":[]}



=== TEST 14: cfg can enable/disable setting array_mt
--- lua
local cjson = require "cjson"
cjson.decode_array_with_array_mt(true)
cjson.decode_array_with_array_mt(false)
local json = [[{"my_array":[]}]]
local t = cjson.decode(json)
local has_metatable = getmetatable(t.my_array) == cjson.array_mt
print("decoded JSON array has metatable: " .. tostring(has_metatable))
print(cjson.encode(t))
--- out
decoded JSON array has metatable: false
{"my_array":{}}



=== TEST 15: array_mt on tables with hash part
--- lua
local cjson = require "cjson"
local data

if jit and string.find(jit.version, "LuaJIT 2.1.0", nil, true) then
    local new_tab = require "table.new"
    data = new_tab(0, 2) -- allocating hash part only

else
    data = {}
end

data.foo = "bar"
data[1] = "hello"
setmetatable(data, cjson.array_mt)
print(cjson.encode(data))
--- out
["hello"]



=== TEST 16: multiple calls to lua_cjson_new (1/3)
--- lua
local cjson = require "cjson"
package.loaded["cjson"] = nil
require "cjson"
local arr = setmetatable({}, cjson.array_mt)
print(cjson.encode(arr))
--- out
[]



=== TEST 17: multiple calls to lua_cjson_new (2/3)
--- lua
local cjson = require "cjson"
package.loaded["cjson"] = nil
require "cjson"
local arr = setmetatable({}, cjson.empty_array_mt)
print(cjson.encode(arr))
--- out
[]



=== TEST 18: multiple calls to lua_cjson_new (3/3)
--- lua
local cjson = require "cjson.safe"
-- load another cjson instance (not in package.loaded)
require "cjson"
local arr = setmetatable({}, cjson.empty_array_mt)
print(cjson.encode(arr))
--- out
[]



=== TEST 19: & in JSON
--- lua
local cjson = require "cjson"
local a="[\"a=1&b=2\"]"
local b=cjson.decode(a)
print(cjson.encode(b))
--- out
["a=1&b=2"]



=== TEST 20: default and max precision
--- lua
local math = require "math"
local cjson = require "cjson"
local double = math.pow(2, 53)
print(cjson.encode(double))
cjson.encode_number_precision(16)
print(cjson.encode(double))
print(string.format("%16.0f", cjson.decode("9007199254740992")))
--- out
9.007199254741e+15
9007199254740992
9007199254740992



=== TEST 21: / in string
--- lua
local cjson = require "cjson"
local a={test = "http://google.com/google"}
local b=cjson.encode(a)
print(b)
cjson.encode_escape_forward_slash(false)
local b=cjson.encode(a)
print(b)
cjson.encode_escape_forward_slash(true)
local b=cjson.encode(a)
print(b)
--- out
{"test":"http:\/\/google.com\/google"}
{"test":"http://google.com/google"}
{"test":"http:\/\/google.com\/google"}
