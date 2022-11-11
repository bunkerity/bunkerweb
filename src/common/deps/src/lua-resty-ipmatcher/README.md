# lua-resty-ipmatcher

High performance match IP address for OpenResty Lua.

## API

```lua
local ipmatcher = require("resty.ipmatcher")
local ip = ipmatcher.new({
    "127.0.0.1",
    "192.168.0.0/16",
    "::1",
    "fe80::/32",
})

ngx.say(ip:match("127.0.0.1"))
ngx.say(ip:match("192.168.1.100"))
ngx.say(ip:match("::1"))
```

## ipmatcher.new

`syntax: ok, err = ipmatcher.new(ips)`

The `ips` is a array table, like `{ip1, ip2, ip3, ...}`,
each element in the array is a string IP address.

```lua
local ip, err = ipmatcher.new({"127.0.0.1", "192.168.0.0/16"})
```

Returns `nil` and error message if failed to create new `ipmatcher` instance.

It supports any CIDR format for IPv4 and IPv6.

```lua
local ip, err = ipmatcher.new({
        "127.0.0.1", "192.168.0.0/16",
        "::1", "fe80::/16",
    })
```

## ipmatcher.new_with_value

`syntax: matcher, err = ipmatcher.new_with_value(ips)`

The `ips` is a hash table, like `{[ip1] = val1, [ip2] = val2, ...}`,
each key in the hash is a string IP address.

When the `matcher` is created by `new_with_value`, calling `match` or `match_bin`
on it will return the corresponding value of matched CIDR range instead of `true`.

```lua
local ip, err = ipmatcher.new_with_value({
    ["127.0.0.1"] = {info = "a"},
    ["192.168.0.0/16"] = {info = "b"},
})
local data, err = ip:match("192.168.0.1")
print(data.info) -- the value is "b"
```

Returns `nil` and error message if failed to create new `ipmatcher` instance.

It supports any CIDR format for IPv4 and IPv6.

```lua
local ip, err = ipmatcher.new_with_value({
    ["127.0.0.1"] = {info = "a"},
    ["192.168.0.0/16"] = {info = "b"},
    ["::1"] = 1,
    ["fe80::/32"] = "xx",
})
```

If the ip address can be satified by multiple CIDR ranges, the returned value
is undefined (depended on the internal implementation). For instance,

```lua
local ip, err = ipmatcher.new_with_value({
    ["192.168.0.1"] = {info = "a"},
    ["192.168.0.0/16"] = {info = "b"},
})
local data, err = ip:match("192.168.0.1")
print(data.info) -- the value can be "a" or "b"
```

## ip.match

`syntax: ok, err = ip:match(ip)`

Returns a `true` if the IP exists within any of the specified IP list.
Returns a `false` if the IP doesn't exist within any of the specified IP list.
Returns `false` and an error message with an invalid IP address.

```lua
local ok, err = ip:match("127.0.0.1")
```

## ip.match_bin

`syntax: ok, err = ip:match_bin(bin_ip)`

Returns a `true` if the binary format IP exists within any of the specified IP list.

Returns `nil` and an error message with an invalid binary IP address.

```lua
local ok, err = ip:match_bin(ngx.var.binary_remote_addr)
```

## ipmatcher.parse_ipv4

`syntax: res = ipmatcher.parse_ipv4(ip)`

Tries to parse an IPv4 address to a host byte order FFI uint32_t type integer.

Returns a `false` if the ip is not a valid IPv4 address.


## ipmatcher.parse_ipv6

`syntax: res = ipmatcher.parse_ipv6(ip)`

Tries to parse an IPv6 address to a table with four host byte order FFI uint32_t
type integer.  The given IPv6 address can be wrapped by square brackets
like `[::1]`.

Returns a `false` if the ip is not a valid IPv6 address.
