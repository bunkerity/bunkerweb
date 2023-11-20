# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
#log_level('warn');

#repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 6);

#no_diff();
no_long_string();
#master_on();
#workers(2);

run_tests();

__DATA__

=== TEST 1: string key, int value
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        dogs:set("bah", 10502)
        local val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))
    }
--- stream_response
32 number
10502 number
--- no_error_log
[error]



=== TEST 2: string key, floating-point value
--- stream_config
    lua_shared_dict cats 1m;
--- stream_server_config
    content_by_lua_block {
        local cats = ngx.shared.cats
        cats:set("foo", 3.14159)
        cats:set("baz", 1.28)
        cats:set("baz", 3.96)
        local val = cats:get("foo")
        ngx.say(val, " ", type(val))
        val = cats:get("baz")
        ngx.say(val, " ", type(val))
    }
--- stream_response
3.14159 number
3.96 number
--- no_error_log
[error]



=== TEST 3: string key, boolean value
--- stream_config
    lua_shared_dict cats 1m;
--- stream_server_config
    content_by_lua_block {
        local cats = ngx.shared.cats
        cats:set("foo", true)
        cats:set("bar", false)
        local val = cats:get("foo")
        ngx.say(val, " ", type(val))
        val = cats:get("bar")
        ngx.say(val, " ", type(val))
    }
--- stream_response
true boolean
false boolean
--- no_error_log
[error]



=== TEST 4: number keys, string values
--- stream_config
    lua_shared_dict cats 1m;
--- stream_server_config
    content_by_lua_block {
        local cats = ngx.shared.cats
        ngx.say(cats:set(1234, "cat"))
        ngx.say(cats:set("1234", "dog"))
        ngx.say(cats:set(256, "bird"))
        ngx.say(cats:get(1234))
        ngx.say(cats:get("1234"))
        local val = cats:get("256")
        ngx.say(val, " ", type(val))
    }
--- stream_response
truenilfalse
truenilfalse
truenilfalse
dog
dog
bird string
--- no_error_log
[error]



=== TEST 5: different-size values set to the same key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", "hello")
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello")
        ngx.say(dogs:get("foo"))
    }
--- stream_response
hello
hello, world
hello
--- no_error_log
[error]



=== TEST 6: expired entries (can be auto-removed by get)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32, 0.01)
        ngx.sleep(0.01)
        ngx.say(dogs:get("foo"))
    }
--- stream_response
nil
--- no_error_log
[error]



=== TEST 7: expired entries (can NOT be auto-removed by get)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 56, 0.001)
        dogs:set("baz", 78, 0.001)
        dogs:set("foo", 32, 0.01)
        ngx.sleep(0.012)
        ngx.say(dogs:get("foo"))
    }
--- stream_response
nil
--- no_error_log
[error]



=== TEST 8: not yet expired entries
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32, 0.5)
        ngx.sleep(0.01)
        ngx.say(dogs:get("foo"))
    }
--- stream_response
32
--- no_error_log
[error]



=== TEST 9: forcibly override other valid entries
--- stream_config
    lua_shared_dict dogs 100k;
--- stream_server_config
    content_by_lua_file html/a.lua;
--- stream_server_config2
    content_by_lua_file html/a.lua;
--- user_files
>>> a.lua
local dogs = ngx.shared.dogs
local i = 0
while i < 1000 do
    i = i + 1
    local val = string.rep(" hello", 10) .. i
    local res, err, forcible = dogs:set("key_" .. i, val)
    if not res or forcible then
        ngx.say(res, " ", err, " ", forcible)
        break
    end
end
ngx.say("abort at ", i)
ngx.say("cur value: ", dogs:get("key_" .. i))
if i > 1 then
    ngx.say("1st value: ", dogs:get("key_1"))
end
if i > 2 then
    ngx.say("2nd value: ", dogs:get("key_2"))
end

--- stream_response eval
my $a = "true nil true\nabort at (353|705)\ncur value: " . (" hello" x 10) . "\\1\n1st value: nil\n2nd value: " . (" hello" x 10) . "2\n";
[qr/$a/,
"true nil true\nabort at 1\ncur value: " . (" hello" x 10) . "1\n"
]
--- no_error_log
[error]



=== TEST 10: forcibly override other valid entries and test LRU
--- stream_config
    lua_shared_dict dogs 100k;
--- stream_server_config
    content_by_lua_file html/a.lua;
--- stream_server_config2
    content_by_lua_file html/a.lua;
--- user_files
>>> a.lua
local dogs = ngx.shared.dogs
local i = 0
while i < 1000 do
    i = i + 1
    local val = string.rep(" hello", 10) .. i
    if i == 10 then
        dogs:get("key_1")
    end
    local res, err, forcible = dogs:set("key_" .. i, val)
    if not res or forcible then
        ngx.say(res, " ", err, " ", forcible)
        break
    end
end
ngx.say("abort at ", i)
ngx.say("cur value: ", dogs:get("key_" .. i))
if i > 1 then
    ngx.say("1st value: ", dogs:get("key_1"))
end
if i > 2 then
    ngx.say("2nd value: ", dogs:get("key_2"))
end
--- stream_response eval
my $a = "true nil true\nabort at (353|705)\ncur value: " . (" hello" x 10) . "\\1\n1st value: " . (" hello" x 10) . "1\n2nd value: nil\n";
[qr/$a/,
"true nil true\nabort at 2\ncur value: " . (" hello" x 10) . "2\n1st value: " . (" hello" x 10) . "1\n"
]
--- no_error_log
[error]



=== TEST 11: dogs and cats dicts
--- stream_config
    lua_shared_dict dogs 1m;
    lua_shared_dict cats 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local cats = ngx.shared.cats
        dogs:set("foo", 32)
        cats:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
        ngx.say(cats:get("foo"))
        dogs:set("foo", 56)
        ngx.say(dogs:get("foo"))
        ngx.say(cats:get("foo"))
    }
--- stream_response
32
hello, world
56
hello, world
--- no_error_log
[error]



=== TEST 12: get non-existent keys
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        ngx.say(dogs:get("foo"))
        ngx.say(dogs:get("foo"))
    }
--- stream_response
nil
nil
--- no_error_log
[error]



=== TEST 13: not feed the object into the call
--- SKIP
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local rc, err = pcall(dogs.set, "foo", 3, 0.01)
        ngx.say(rc, " ", err)
        rc, err = pcall(dogs.set, "foo", 3)
        ngx.say(rc, " ", err)
        rc, err = pcall(dogs.get, "foo")
        ngx.say(rc, " ", err)
    }
--- stream_response
false bad argument #1 to '?' (userdata expected, got string)
false expecting 3, 4 or 5 arguments, but only seen 2
false expecting exactly two arguments, but only seen 1
--- no_error_log
[error]



=== TEST 14: too big value
--- stream_config
    lua_shared_dict dogs 50k;
--- stream_server_config
    content_by_lua_block {
        collectgarbage("collect")
        local dogs = ngx.shared.dogs
        local res, err, forcible = dogs:set("foo", string.rep("helloworld", 10000))
        ngx.say(res, " ", err, " ", forcible)
    }
--- stream_response
false no memory false
--- log_level: info
--- no_error_log
[error]
[crit]
ngx_slab_alloc() failed: no memory in lua_shared_dict zone



=== TEST 15: set too large key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local key = string.rep("a", 65535)
        local rc, err = dogs:set(key, "hello")
        ngx.say(rc, " ", err)
        ngx.say(dogs:get(key))

        key = string.rep("a", 65536)
        ok, err = dogs:set(key, "world")
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")

    }
--- stream_response
true nil
hello
not ok: key too long
--- no_error_log
[error]



=== TEST 16: bad value type
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", dogs)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: bad value type
--- no_error_log
[error]



=== TEST 17: delete after setting values
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        ngx.say(dogs:get("foo"))
        dogs:delete("foo")
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
    }
--- stream_response
32
nil
hello, world
--- no_error_log
[error]



=== TEST 18: delete at first
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:delete("foo")
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
    }
--- stream_response
nil
hello, world
--- no_error_log
[error]



=== TEST 19: set nil after setting values
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        ngx.say(dogs:get("foo"))
        dogs:set("foo", nil)
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
    }
--- stream_response
32
nil
hello, world
--- no_error_log
[error]



=== TEST 20: set nil at first
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", nil)
        ngx.say(dogs:get("foo"))
        dogs:set("foo", "hello, world")
        ngx.say(dogs:get("foo"))
    }
--- stream_response
nil
hello, world
--- no_error_log
[error]



=== TEST 21: fail to allocate memory
--- stream_config
    lua_shared_dict dogs 100k;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local i = 0
        while i < 1000 do
            i = i + 1
            local val = string.rep("hello", i )
            local res, err, forcible = dogs:set("key_" .. i, val)
            if not res or forcible then
                ngx.say(res, " ", err, " ", forcible)
                break
            end
        end
        ngx.say("abort at ", i)
    }
--- stream_response_like
^true nil true\nabort at (?:139|140|141)$
--- no_error_log
[error]



=== TEST 22: too big value (forcible)
--- stream_config
    lua_shared_dict dogs 50k;
--- stream_server_config
    content_by_lua_block {
        collectgarbage("collect")
        local dogs = ngx.shared.dogs
        dogs:set("bah", "hello")
        local res, err, forcible = dogs:set("foo", string.rep("helloworld", 10000))
        ngx.say(res, " ", err, " ", forcible)
    }
--- stream_response
false no memory true
--- log_level: info
--- no_error_log
[error]
[crit]
ngx_slab_alloc() failed: no memory in lua_shared_dict zone



=== TEST 23: add key (key exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err, forcible = dogs:add("foo", 10502)
        ngx.say("add: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
add: false exists false
foo = 32
--- no_error_log
[error]



=== TEST 24: add key (key not exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bah", 32)
        local res, err, forcible = dogs:add("foo", 10502)
        ngx.say("add: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
add: true nil false
foo = 10502
--- no_error_log
[error]



=== TEST 25: add key (key expired)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 32, 0.001)
        dogs:set("baz", 32, 0.001)
        dogs:set("foo", 32, 0.001)
        ngx.sleep(0.002)
        local res, err, forcible = dogs:add("foo", 10502)
        ngx.say("add: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
add: true nil false
foo = 10502
--- no_error_log
[error]



=== TEST 26: add key (key expired and value size unmatched)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 32, 0.001)
        dogs:set("baz", 32, 0.001)
        dogs:set("foo", "hi", 0.001)
        ngx.sleep(0.002)
        local res, err, forcible = dogs:add("foo", "hello")
        ngx.say("add: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
add: true nil false
foo = hello
--- no_error_log
[error]



=== TEST 27: incr key (key exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err, forcible = dogs:replace("foo", 10502)
        ngx.say("replace: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))

        local res, err, forcible = dogs:replace("foo", "hello")
        ngx.say("replace: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))

    }
--- stream_response
replace: true nil false
foo = 10502
replace: true nil false
foo = hello
--- no_error_log
[error]



=== TEST 28: replace key (key not exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bah", 32)
        local res, err, forcible = dogs:replace("foo", 10502)
        ngx.say("replace: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
replace: false not found false
foo = nil
--- no_error_log
[error]



=== TEST 29: replace key (key expired)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 3, 0.001)
        dogs:set("baz", 2, 0.001)
        dogs:set("foo", 32, 0.001)
        ngx.sleep(0.002)
        local res, err, forcible = dogs:replace("foo", 10502)
        ngx.say("replace: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
replace: false not found false
foo = nil
--- no_error_log
[error]



=== TEST 30: replace key (key expired and value size unmatched)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 32, 0.001)
        dogs:set("baz", 32, 0.001)
        dogs:set("foo", "hi", 0.001)
        ngx.sleep(0.002)
        local rc, err, forcible = dogs:replace("foo", "hello")
        ngx.say("replace: ", rc, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
replace: false not found false
foo = nil
--- no_error_log
[error]



=== TEST 31: incr key (key exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err = dogs:incr("foo", 10502)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: 10534 nil
foo = 10534
--- no_error_log
[error]



=== TEST 32: replace key (key not exists)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bah", 32)
        local res, err = dogs:incr("foo", 2)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: nil not found
foo = nil
--- no_error_log
[error]



=== TEST 33: replace key (key expired)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("bar", 3, 0.001)
        dogs:set("baz", 2, 0.001)
        dogs:set("foo", 32, 0.001)
        ngx.sleep(0.002)
        local res, err = dogs:incr("foo", 10502)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: nil not found
foo = nil
--- no_error_log
[error]



=== TEST 34: incr key (incr by 0)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err = dogs:incr("foo", 0)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: 32 nil
foo = 32
--- no_error_log
[error]



=== TEST 35: incr key (incr by floating point number)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err = dogs:incr("foo", 0.14)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: 32.14 nil
foo = 32.14
--- no_error_log
[error]



=== TEST 36: incr key (incr by negative numbers)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        local res, err = dogs:incr("foo", -0.14)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: 31.86 nil
foo = 31.86
--- no_error_log
[error]



=== TEST 37: incr key (original value is not number)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", true)
        local res, err = dogs:incr("foo", -0.14)
        ngx.say("incr: ", res, " ", err)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
incr: nil not a number
foo = true
--- no_error_log
[error]



=== TEST 38: get and set with flags
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32, 0, 199)
        dogs:set("bah", 10502, 202)
        local val, flags = dogs:get("foo")
        ngx.say(val, " ", type(val))
        ngx.say(flags, " ", type(flags))
        val, flags = dogs:get("bah")
        ngx.say(val, " ", type(val))
        ngx.say(flags, " ", type(flags))
    }
--- stream_response
32 number
199 number
10502 number
nil nil
--- no_error_log
[error]



=== TEST 39: expired entries (can be auto-removed by get), with flags set
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32, 0.01, 255)
        ngx.sleep(0.01)
        local res, flags = dogs:get("foo")
        ngx.say("res = ", res, ", flags = ", flags)
    }
--- stream_response
res = nil, flags = nil
--- no_error_log
[error]



=== TEST 40: flush_all
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        dogs:set("bah", 10502)

        local val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))

        dogs:flush_all()

        val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))
    }
--- stream_response
32 number
10502 number
nil nil
nil nil
--- no_error_log
[error]



=== TEST 41: flush_expires
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", "x", 1)
        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 100)

        ngx.sleep(1.5)

        local num = dogs:flush_expired()
        ngx.say(num)
    }
--- stream_response
1
--- no_error_log
[error]



=== TEST 42: flush_expires with number
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        for i=1,100 do
            dogs:set(tostring(i), "x", 1)
        end

        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 100)

        ngx.sleep(1.5)

        local num = dogs:flush_expired(42)
        ngx.say(num)
    }
--- stream_response
42
--- no_error_log
[error]



=== TEST 43: flush_expires an empty dict
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        local num = dogs:flush_expired()
        ngx.say(num)
    }
--- stream_response
0
--- no_error_log
[error]



=== TEST 44: flush_expires a dict without expired items
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 100)

        local num = dogs:flush_expired()
        ngx.say(num)
    }
--- stream_response
0
--- no_error_log
[error]



=== TEST 45: list all keys in a shdict
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 0)
        local keys = dogs:get_keys()
        ngx.say(#keys)
        table.sort(keys)
        for _,k in ipairs(keys) do
            ngx.say(k)
        end
    }
--- stream_response
2
bah
bar
--- no_error_log
[error]



=== TEST 46: list keys in a shdict with limit
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 0)
        local keys = dogs:get_keys(1)
        ngx.say(#keys)
    }
--- stream_response
1
--- no_error_log
[error]



=== TEST 47: list all keys in a shdict with expires
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", "x", 1)
        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 100)

        ngx.sleep(1.5)

        local keys = dogs:get_keys()
        ngx.say(#keys)
    }
--- stream_response
2
--- no_error_log
[error]



=== TEST 48: list keys in a shdict with limit larger than number of keys
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs

        dogs:set("bah", "y", 0)
        dogs:set("bar", "z", 0)
        local keys = dogs:get_keys(3)
        ngx.say(#keys)
    }
--- stream_response
2
--- no_error_log
[error]



=== TEST 49: list keys in an empty shdict
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local keys = dogs:get_keys()
        ngx.say(#keys)
    }
--- stream_response
0
--- no_error_log
[error]



=== TEST 50: list keys in an empty shdict with a limit
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local keys = dogs:get_keys(4)
        ngx.say(#keys)
    }
--- stream_response
0
--- no_error_log
[error]



=== TEST 51: list all keys in a shdict with all keys expired
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", "x", 1)
        dogs:set("bah", "y", 1)
        dogs:set("bar", "z", 1)

        ngx.sleep(1.5)

        local keys = dogs:get_keys()
        ngx.say(#keys)
    }
--- stream_response
0
--- no_error_log
[error]



=== TEST 52: list all keys in a shdict with more than 1024 keys with no limit set
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        for i=1,2048 do
            dogs:set(tostring(i), i)
        end
        local keys = dogs:get_keys()
        ngx.say(#keys)
    }
--- stream_response
1024
--- no_error_log
[error]



=== TEST 53: list all keys in a shdict with more than 1024 keys with 0 limit set
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        for i=1,2048 do
            dogs:set(tostring(i), i)
        end
        local keys = dogs:get_keys(0)
        ngx.say(#keys)
    }
--- stream_response
2048
--- no_error_log
[error]



=== TEST 54: safe_set
--- stream_config
    lua_shared_dict dogs 100k;
--- stream_server_config
    content_by_lua_file html/a.lua;
--- stream_server_config2
    content_by_lua_file html/a.lua;
--- user_files
>>> a.lua
local dogs = ngx.shared.dogs
local i = 0
while i < 1000 do
    i = i + 1
    local val = string.rep(" hello", 10) .. i
    local res, err = dogs:safe_set("key_" .. i, val)
    if not res then
        ngx.say(res, " ", err)
        break
    end
end
ngx.say("abort at ", i)
ngx.say("cur value: ", dogs:get("key_" .. i))
if i > 1 then
    ngx.say("1st value: ", dogs:get("key_1"))
end
if i > 2 then
    ngx.say("2nd value: ", dogs:get("key_2"))
end
--- stream_response eval
my $a = "false no memory\nabort at (353|705)\ncur value: nil\n1st value: " . (" hello" x 10) . "1\n2nd value: " . (" hello" x 10) . "2\n";
[qr/$a/, qr/$a/]
--- no_error_log
[error]



=== TEST 55: safe_add
--- stream_config
    lua_shared_dict dogs 100k;
--- stream_server_config
    content_by_lua_file html/a.lua;
--- stream_server_config2
    content_by_lua_file html/a.lua;
--- user_files
>>> a.lua
local dogs = ngx.shared.dogs
local i = 0
while i < 1000 do
    i = i + 1
    local val = string.rep(" hello", 10) .. i
    local res, err = dogs:safe_add("key_" .. i, val)
    if not res then
        ngx.say(res, " ", err)
        break
    end
end
ngx.say("abort at ", i)
ngx.say("cur value: ", dogs:get("key_" .. i))
if i > 1 then
    ngx.say("1st value: ", dogs:get("key_1"))
end
if i > 2 then
    ngx.say("2nd value: ", dogs:get("key_2"))
end
--- stream_response eval
my $a = "false no memory\nabort at (353|705)\ncur value: nil\n1st value: " . (" hello" x 10) . "1\n2nd value: " . (" hello" x 10) . "2\n";
[qr/$a/,
q{false exists
abort at 1
cur value:  hello hello hello hello hello hello hello hello hello hello1
}
]
--- no_error_log
[error]



=== TEST 56: get_stale: expired entries can still be fetched
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32, 0.01)
        dogs:set("blah", 33, 0.1)
        ngx.sleep(0.02)
        local val, flags, stale = dogs:get_stale("foo")
        ngx.say(val, ", ", flags, ", ", stale)
        local val, flags, stale = dogs:get_stale("blah")
        ngx.say(val, ", ", flags, ", ", stale)
    }
--- stream_response
32, nil, true
33, nil, false
--- no_error_log
[error]



=== TEST 57: set nil key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set(nil, 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: nil key
--- no_error_log
[error]



=== TEST 58: set bad zone argument
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs.set(nil, "foo", 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 59: set empty string keys
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("", 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: empty key
--- no_error_log
[error]



=== TEST 60: get bad zone argument
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs.get(nil, "foo")
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 61: get nil key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get(nil)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: nil key
--- no_error_log
[error]



=== TEST 62: get empty key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get("")
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: empty key
--- no_error_log
[error]



=== TEST 63: get a too-long key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get(string.rep("a", 65536))
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: key too long
--- no_error_log
[error]



=== TEST 64: set & get large values
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", string.rep("helloworld", 1024))
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")

        local data, err = dogs:get("foo")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        ngx.say("get ok: ", #data)

    }
--- stream_response
set ok
get ok: 10240
--- no_error_log
[error]



=== TEST 65: get_stale nil key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get_stale(nil)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: nil key
--- no_error_log
[error]



=== TEST 66: get_stale empty key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get_stale("")
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: empty key
--- no_error_log
[error]



=== TEST 67: get_stale number key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set(1024, "hello")
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")
        local data, err = dogs:get_stale(1024)
        if not ok then
            ngx.say("get_stale not ok: ", err)
            return
        end
        ngx.say("get_stale: ", data)
    }
--- stream_response
set ok
get_stale: hello
--- no_error_log
[error]



=== TEST 68: get_stale a too-long key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:get_stale(string.rep("a", 65536))
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: key too long
--- no_error_log
[error]



=== TEST 69: get_stale a non-existent key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local data, err = dogs:get_stale("not_found")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        ngx.say("get ok: ", data)
    }
--- stream_response
get ok: nil
--- no_error_log
[error]



=== TEST 70: set & get_stale large values
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", string.rep("helloworld", 1024))
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")

        local data, err, stale = dogs:get_stale("foo")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        ngx.say("get_stale ok: ", #data, ", stale: ", stale)

    }
--- stream_response
set ok
get_stale ok: 10240, stale: false
--- no_error_log
[error]



=== TEST 71: set & get_stale boolean values (true)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", true)
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")

        local data, err, stale = dogs:get_stale("foo")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        ngx.say("get_stale ok: ", data, ", stale: ", stale)

    }
--- stream_response
set ok
get_stale ok: true, stale: false
--- no_error_log
[error]



=== TEST 72: set & get_stale boolean values (false)
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", false)
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")

        local data, err, stale = dogs:get_stale("foo")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        ngx.say("get_stale ok: ", data, ", stale: ", stale)

    }
--- stream_response
set ok
get_stale ok: false, stale: false
--- no_error_log
[error]



=== TEST 73: set & get_stale with a flag
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:set("foo", false, 0, 325)
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")

        local data, err, stale = dogs:get_stale("foo")
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        flags = err
        ngx.say("get_stale ok: ", data, ", flags: ", flags,
                ", stale: ", stale)

    }
--- stream_response
set ok
get_stale ok: false, flags: 325, stale: false
--- no_error_log
[error]



=== TEST 74: incr nil key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:incr(nil, 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: nil key
--- no_error_log
[error]



=== TEST 75: incr bad zone argument
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs.incr(nil, "foo", 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 76: incr empty string keys
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:incr("", 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: empty key
--- no_error_log
[error]



=== TEST 77: incr too long key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local key = string.rep("a", 65536)
        local ok, err = dogs:incr(key, 32)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")

    }
--- stream_response
not ok: key too long
--- no_error_log
[error]



=== TEST 78: incr number key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local key = 56
        local ok, err = dogs:set(key, 1)
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")
        ok, err = dogs:incr(key, 32)
        if not ok then
            ngx.say("incr not ok: ", err)
            return
        end
        ngx.say("incr ok")
        local data, err = dogs:get(key)
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        local flags = err
        ngx.say("get ok: ", data, ", flags: ", flags)

    }
--- stream_response
set ok
incr ok
get ok: 33, flags: nil
--- no_error_log
[error]



=== TEST 79: incr a number-like string key
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local key = 56
        local ok, err = dogs:set(key, 1)
        if not ok then
            ngx.say("set not ok: ", err)
            return
        end
        ngx.say("set ok")
        ok, err = dogs:incr(key, "32")
        if not ok then
            ngx.say("incr not ok: ", err)
            return
        end
        ngx.say("incr ok")
        local data, err = dogs:get(key)
        if data == nil and err then
            ngx.say("get not ok: ", err)
            return
        end
        local flags = err
        ngx.say("get ok: ", data, ", flags: ", flags)

    }
--- stream_response
set ok
incr ok
get ok: 33, flags: nil
--- no_error_log
[error]



=== TEST 80: add nil values
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local ok, err = dogs:add("foo", nil)
        if not ok then
            ngx.say("not ok: ", err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
not ok: attempt to add or replace nil values
--- no_error_log
[error]



=== TEST 81: replace key with exptime
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 2, 0)
        dogs:replace("foo", 32, 0.01)
        local data = dogs:get("foo")
        ngx.say("get foo: ", data)
        ngx.sleep(0.02)
        local res, err, forcible = dogs:replace("foo", 10502)
        ngx.say("replace: ", res, " ", err, " ", forcible)
        ngx.say("foo = ", dogs:get("foo"))
    }
--- stream_response
get foo: 32
replace: false not found false
foo = nil
--- no_error_log
[error]



=== TEST 82: the lightuserdata ngx.null has no methods of shared dicts.
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local lightuserdata = ngx.null
        lightuserdata:set("foo", 1)
    }
--- stream_response
--- grep_error_log chop
attempt to index local 'lightuserdata' (a userdata value)
--- grep_error_log_out
attempt to index local 'lightuserdata' (a userdata value)
--- error_log
[error]
--- no_error_log
bad "zone" argument



=== TEST 83: set bad zone table
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs.set({1}, "foo", 1)
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 84: get bad zone table
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs.get({1}, "foo")
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 85: incr bad zone table
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs.incr({1}, "foo", 32)
    }
--- stream_response
--- error_log
bad "zone" argument



=== TEST 86: check the type of the shdict object
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        ngx.say("type: ", type(ngx.shared.dogs))
    }
--- stream_response
type: table
--- no_error_log
[error]



=== TEST 87: dogs, cat mixing
--- stream_config
    lua_shared_dict dogs 1m;
    lua_shared_dict cats 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("foo", 32)
        dogs:set("bah", 10502)
        local val = dogs:get("foo")
        ngx.say(val, " ", type(val))
        val = dogs:get("bah")
        ngx.say(val, " ", type(val))

        local cats = ngx.shared.cats
        val = cats:get("foo")
        ngx.say(val or "nil")
        val = cats:get("bah")
        ngx.say(val or "nil")
    }
--- stream_response
32 number
10502 number
nil
nil
--- no_error_log
[error]



=== TEST 88: push to an expired list
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local len, err = dogs:lpush("cc", "1") --add another list to avoid key"aa" be cleaned (run ‘ngx_http_lua_shdict_expire(ctx, 1)’ may clean key ,ensure key'aa' not clean ,just expired))
        if not len then
            ngx.say("push cc  err: ", err)
        end
        local len, err = dogs:lpush("aa", "1")
        if not len then
            ngx.say("push1 err: ", err)
        end
        local succ, err = dogs:expire("aa", 0.2)
        if not succ then
            ngx.say("expire err: ",err)
        end
        ngx.sleep(0.3) -- list aa expired
        local len, err = dogs:lpush("aa", "2") --push to an expired list may set as a new list
        if not len then
            ngx.say("push2 err: ", err)
        end
        local len, err = dogs:llen("aa") -- new list len is 1
        if not len then
            ngx.say("llen err: ", err)
        else
            ngx.say("aa:len :", dogs:llen("aa"))
        end
    }
--- stream_response
aa:len :1
--- no_error_log
[error]



=== TEST 89: push to an expired list then pop many time (more then list len )
--- stream_config
    lua_shared_dict dogs 1m;
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        local len, err = dogs:lpush("cc", "1") --add another list to avoid key"aa" be cleaned (run ‘ngx_http_lua_shdict_expire(ctx, 1)’ may clean key ,ensure key'aa' not clean ,just expired))
        if not len then
            ngx.say("push cc  err: ", err)
        end
        local len, err = dogs:lpush("aa", "1")
        if not len then
            ngx.say("push1 err: ", err)
        end
        local succ, err = dogs:expire("aa", 0.2)
        if not succ then
            ngx.say("expire err: ",err)
        end
        ngx.sleep(0.3) -- list aa expired
        local len, err = dogs:lpush("aa", "2") --push to an expired list may set as a new list
        if not len then
            ngx.say("push2 err: ", err)
        end
        local val, err = dogs:lpop("aa")
        if not val then
            ngx.say("llen err: ", err)
        end
        local val, err = dogs:lpop("aa")  -- val == nil
        ngx.say("aa list value: ", val)
    }
--- stream_response
aa list value: nil
--- no_error_log
[error]
