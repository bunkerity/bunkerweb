# lua-resty-session

**lua-resty-session** is a secure, and flexible session library for OpenResty.

## Hello World with lua-resty-session

```nginx
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    server {
        listen       8080;
        server_name  localhost;
        default_type text/html;

        location / {
            content_by_lua '
                ngx.say("<html><body><a href=/start>Start the test</a>!</body></html>")
            ';
        }
        location /start {
            content_by_lua '
                local session = require "resty.session".start()
                session.data.name = "OpenResty Fan"
                session:save()
                ngx.say("<html><body>Session started. ",
                        "<a href=/test>Check if it is working</a>!</body></html>")
            ';
        }
        location /test {
            content_by_lua '
                local session = require "resty.session".open()
                ngx.say("<html><body>Session was started by <strong>",
                        session.data.name or "Anonymous",
                        "</strong>! <a href=/modify>Modify the session</a>.</body></html>")
            ';
        }
        location /modify {
            content_by_lua '
                local session = require "resty.session".start()
                session.data.name = "Lua Fan"
                session:save()
                ngx.say("<html><body>Session modified. ",
                        "<a href=/modified>Check if it is modified</a>!</body></html>")
            ';
        }
        location /modified {
            content_by_lua '
                local session = require "resty.session".open()
                ngx.say("<html><body>Session was modified by <strong>",
                        session.data.name or "Anonymous",
                        "</strong>! <a href=/destroy>Destroy the session</a>.</body></html>")
            ';
        }
        location /destroy {
            content_by_lua '
                require "resty.session".destroy()
                ngx.say("<html><body>Session was destroyed. ",
                        "<a href=/check>Is it really so</a>?</body></html>")
            ';
        }
        location /check {
            content_by_lua '
                local session = require "resty.session".open()
                ngx.say("<html><body>Session was really destroyed, you are known as ",
                        "<strong>",
                        session.data.name or "Anonymous",
                        "</strong>! <a href=/>Start again</a>.</body></html>")
            ';
        }
    }
}
```

## Installation

Just place [`session.lua`](https://github.com/bungle/lua-resty-session/blob/master/lib/resty/session.lua)
and [`session`](https://github.com/bungle/lua-resty-session/tree/master/lib/resty/session) directory
somewhere in your `package.path`, under `resty` directory. If you are using OpenResty, the default
location would be `/usr/local/openresty/lualib/resty`.

### Using OpenResty Package Manager (opm)

```Shell
$ opm get bungle/lua-resty-session
```

### Using LuaRocks

```Shell
$ luarocks install lua-resty-session
```

LuaRocks repository for `lua-resty-session` is located at https://luarocks.org/modules/bungle/lua-resty-session.

## About The Defaults

`lua-resty-session` does by default session only cookies (non-persistent, and `HttpOnly`) so that
the cookies are not readable from Javascript (not subjectible to XSS in that matter). It will also set
`Secure` flag by default when the request was made via SSL/TLS connection or when cookie name (`session.name`)
is prefixed with `__Secure-` or `__Host-` (see [Cookies: HTTP State Management Mechanism](https://tools.ietf.org/html/draft-ietf-httpbis-rfc6265bis-05).
Cookies send via SSL/TLS don't work when sent via HTTP and vice-versa (unless the checks are disabled).
By default the HMAC key is generated from session id (random bytes generated with OpenSSL), expiration time,
unencrypted data, `http_user_agent` and `scheme`. You may also configure it to use `remote_addr` as well by
setting `set $session_check_addr on;` (but this may be problematic with clients behind proxies or NATs that
change the remote address between requests). If you are using SSL Session IDs you may also add
`set $session_check_ssi on;`, but please check that it works accordingly (you may need to adjust both SSL
and session library settings).

The data part is encrypted with AES-algorithm (by default it uses OpenSSL `EVP_aes_256_cbc` and
`EVP_sha512` functions that are provided with `lua-resty-string`. They come pre-installed with
the default OpenResty bundle. The `lua-resty-session` library is not tested with all the
`resty.aes` functions (but the defaults are tested to be working). Please let me know or contact
`lua-resty-string` project if you hit any problems with different algorithms. We also support
pluggable cipher adapters. You can also disable encryption by choosing `none` adapter.

Session identifier length is by default 16 bytes (randomly generated data with OpenSSL
`RAND_bytes` function). The server secret is also generated by default with this same
function and it's default length is 32 bytes. This will work until Nginx is restarted, but you
might want to consider setting your own secret using `set $session_secret 623q4hR325t36VsCD3g567922IC0073T;`,
for example (this will work in farms installations as well). On farm installations you should
also configure other session configuration variables the same on all the servers in the farm.

Cookie parts are encoded with cookie safe Base64 encoding without padding (we also support pluggable
encoders). Before encrypting and encoding the data part, the data is serialized with JSON encoding
(so you can use basic Lua types in data, and expect to receive them back as the same Lua types).
JSON encoding is done by the bundled OpenResty cJSON library (Lua cJSON). We do support pluggable
serializers as well, though only serializer currently supplied is JSON. Cookie's path scope is by
default `/` (meaning that it will be send to all paths in the server). The domain scope is not set
by default, and it means that the cookie will only be sent back to same domain/host where it originated.
If you set  session name (e.g. `set $session_name <value>`) and it contains prefix `__Secure-` the
`Secure` flag will be forced, and if it contains `__Host-` the `path` is forced to `/` and the
`domain` is removed, and the `Secure` flag will be forced too.

For session data we do support pluggable storage adapters. The default adapter is `cookie` that
stores data to client-side cookie. Currently we do also support a few server side storages: `shm`
(aka a shared dictionary), `memcache`, `redis`, and `dshm`.

## Notes About Turning Lua Code Cache Off

In issue ([#15](https://github.com/bungle/lua-resty-session/issues/15)) it was raised that there may
be problems of using `lua-resty-session` when the `lua_code_cache` setting has been turned off.

Nginx:

```nginx
lua_code_cache off;
```

The problem is caused by the fact that by default we do generate session secret automatically with
a random generator (on first use of the library). If the code cache is turned off, we regenerate
the secret on each request. That will invalidate the cookies aka making sessions non-functioning.
The cure for this problem is to define the secret in Nginx or in Lua code (it is a good idea to
always have session secret defined).

Nginx:

```nginx
set $session_secret 623q4hR325t36VsCD3g567922IC0073T;
```

Lua:

```lua
local session = require "resty.session".start{ secret = "623q4hR325t36VsCD3g567922IC0073T" }
-- or
local session = require "resty.session".new()
session.secret = "623q4hR325t36VsCD3g567922IC0073T"
```

## About Locking

With some storage adapters we implement `locking` mechanism. The `locks` are normally released
automatically, and they will timeout, but if you happen to call `session.start()` or `session:start()`,
then it is your responsibility to release the lock by calling `session:close()`, `session:save()` or
`session:destroy()`.

## Pluggable Session Strategies

Strategies can be a bit cumbersome to do with just configuration, and that's why you can
implement them only with the code. Currently `lua-resty-session` comes with two strategies:

* `default`    — the default strategy (original implementation)
* `regenerate` — similar to default strategy, but does not use session `expiry` with `HMAC`
                 functions, and instead generates a new session identifier on each `save`.

The `default` one has been here from the beginning, but recently I got information about
use case of Javascript application with parallel asynchronous queries, where the session
was saved to a database with a custom storage adapter using `header_filter` phase, which resulted
the need to use the asynchronous `ngx.timer`. And that resulted that the JS XHR requests may
have sent an old cookie, or perhaps a new cookie that was not yet found in db because of async
timer. This resulted issues because cryptographic functions in `default` strategy used `expires`,
and every time you saved a cookie it got a new `expiry`. The `regenerate` adapter does not use
`expiry` anymore, but it instead generates a new `session id` on each `save` call. This makes
a new row in a database while the previous `session` will still function. If your storage adapter
implements `ttl` the `regenerate` strategy will call that with the old id and `10` seconds
of `ttl`. `default` strategy is still adequate if you use `cookie` storage adapter as that
is not issue with it, but if using server side storage adapter like `redis` or `memcache`
you may want to consider using `regenerate` if you have a heavily JS based application with
a lot of asynchronous queries at the same time. This issue happens usually when session
is about to be renewed, so it is quite rare even when using `default` strategy.

Strategy can be selected with configuration (if no configuration is present, the `default`
strategy is picked up):

```nginx
set $session_strategy regenerate;
```

To implement a custom strategy, please checkout the existing ones.

Basically you need to implement at least these functions:
- boolean open(session, cookie)
- boolean start(session)
- boolean destroy(session)
- boolean close(session)
- cookie  save(session, close)
- cookie  touch(session, close)

## Pluggable HMAC Algorithms

If your strategy happens to be using `HMAC`, like the `default` and `regenerate` ones do,
you can tell them what `HMAC` algorithm to use. At the moment only `HMAC SHA1` is available
as that comes with OpenResty and works without additional dependencies. You may implement
your own custom HMAC algorithms (preferrably binding to some existing crypto library,
such as OpenSSL), and the strategies will pick up from there.

HMAC can be selected with configuration (if no configuration is present, the `sha1` strategy is picked up):

```nginx
set $session_hmac sha1;
```

To implement your own, you need to implement this interface: `digest hmac(secret, input)`.


## Pluggable Storage Adapters

With version 2.0 we started to support pluggable session data storage adapters. We do currently have
support for these backends:

* `cookie` aka Client Side Cookie (this is the default adapter)
* `shm` aka Lua Shared Dictionary
* `memcache` aka Memcached Storage Backend (thanks [@zandbelt](https://github.com/zandbelt))
* `redis` aka Redis Backend
* `dshm` aka [ngx-distributed-shm](https://github.com/grrolland/ngx-distributed-shm) Storage Adapter (thanks [@grrolland](https://github.com/grrolland))

Here are some comparisons about the backends:

|                               | cookie | shm | memcache | redis | dshm |
| :---------------------------- | :----: | :-: | :------: | :---: | :--: |
| Stateless                     | ✓      |     |          |       |      |
| Lock-less                     | ✓      | ¹   | ¹        | ¹     | ✓    |
| Works with Web Farms          | ✓      |     | ✓        | ✓     | ✓    |
| Session Data Stored on Client | ✓      |     |          |       |      |
| Zero Configuration            | ✓      |     |          |       |      |
| Extra Dependencies            |        |     | ✓        | ✓     | ✓    |
| Extra Security ²              |        | ✓   | ✓        | ✓     | ✓    |

¹ Can be configured lock-less.

² HMAC is stored on a client but the data is stored on a server. That means that you are unable to edit
  cookie if you cannot edit server side storage as well, and vice-versa.

The storage adapter can be selected from Nginx config like this:

```nginx
set $session_storage shm;
```

Or with Lua code like this:

```lua
local session = require "resty.session".new() -- OR .open() | .start()
-- After new you cannot specify storage as a string,
-- you need to give actual implementation
session.storage = require "resty.session.storage.shm".new(session)
-- or
local session = require "resty.session".new({
  storage = "shm"
})
```

#### Cookie Storage Adapter

Cookie storage adapter is the default adapter that is used if storage adapter has not been configured. Cookie
adapter does not have any settings.

Cookie adapter can be selected with configuration (if no configuration is present, the cookie adapter is picked up):

```nginx
set $session_storage cookie;
```

**NOTE:**

If you store large amounts of data in a cookie, this library will automatically split the cookies to 4k chars chunks. With large cookies, you may need to adjust your Nginx configuration to accept large client header buffers. E.g.:

```nginx
large_client_header_buffers 4 16k;
```

#### Shared Dictionary Storage Adapter

Shared dictionary uses OpenResty shared dictionary and works with multiple worker processes, but it isn't a good
choice if you want to run multiple separate frontends. It is relatively easy to configure and has some added
benefits on security side compared to `cookie`, although the normal cookie adapter is quite secure as well.
For locking the `shm` adapter uses `lua-resty-lock`.

Shared dictionary adapter can be selected with configuration:

```nginx
set $session_storage shm;
```

But for this to work, you will also need a storage configured for that:

```nginx
http {
   lua_shared_dict sessions 10m;
}
```

Additionally you can configure the locking and some other things as well:

```nginx
set $session_shm_store         sessions;
set $session_shm_uselocking    on;
set $session_shm_lock_exptime  30;    # (in seconds)
set $session_shm_lock_timeout  5;     # (in seconds)
set $session_shm_lock_step     0.001; # (in seconds)
set $session_shm_lock_ratio    2;
set $session_shm_lock_max_step 0.5;   # (in seconds)
```

The keys stored in shared dictionary are in form:

`{session id}` and `{session id}.lock`.


#### Memcache Storage Adapter

Memcache storage adapter stores the session data inside Memcached server.
It is scalable and works with web farms.

Memcache adapter can be selected with configuration:

```nginx
set $session_storage memcache;
```

Additionally you can configure Memcache adapter with these settings:

```nginx
set $session_memcache_prefix           sessions;
set $session_memcache_connect_timeout  1000; # (in milliseconds)
set $session_memcache_send_timeout     1000; # (in milliseconds)
set $session_memcache_read_timeout     1000; # (in milliseconds)
set $session_memcache_socket           unix:///var/run/memcached/memcached.sock;
set $session_memcache_host             127.0.0.1;
set $session_memcache_port             11211;
set $session_memcache_uselocking       on;
set $session_memcache_spinlockwait     150;  # (in milliseconds)
set $session_memcache_maxlockwait      30;   # (in seconds)
set $session_memcache_pool_name        sessions;
set $session_memcache_pool_timeout     1000; # (in milliseconds)
set $session_memcache_pool_size        10;
set $session_memcache_pool_backlog     10;
```

The keys stored in Memcached are in form:

`{prefix}:{session id}` and `{prefix}:{session id}.lock`.

#### Redis Storage Adapter

Redis storage adapter stores the session data inside Redis server.
It is scalable and works with web farms.

Redis adapter can be selected with configuration:

```nginx
set $session_storage redis;
```

Additionally you can configure Redis adapter with these settings:

```nginx
set $session_redis_prefix                   sessions;
set $session_redis_database                 0;
set $session_redis_connect_timeout          1000; # (in milliseconds)
set $session_redis_send_timeout             1000; # (in milliseconds)
set $session_redis_read_timeout             1000; # (in milliseconds)
set $session_redis_socket                   unix:///var/run/redis/redis.sock;
set $session_redis_host                     127.0.0.1;
set $session_redis_port                     6379;
set $session_redis_ssl                      off;
set $session_redis_ssl_verify               off;
set $session_redis_server_name              example.com; # for TLS SNI
set $session_redis_username                 username;
set $session_redis_password                 password;
set $session_redis_uselocking               on;
set $session_redis_spinlockwait             150;  # (in milliseconds)
set $session_redis_maxlockwait              30;   # (in seconds)
set $session_redis_pool_name                sessions;
set $session_redis_pool_timeout             1000; # (in milliseconds)
set $session_redis_pool_size                10;
set $session_redis_pool_backlog             10;
set $session_redis_cluster_name             redis-cluster;
set $session_redis_cluster_dict             sessions;
set $session_redis_cluster_maxredirections  5;
set $session_redis_cluster_nodes            '127.0.0.1:30001 127.0.0.1:30002 127.0.0.1:30003 127.0.0.1:30004 127.0.0.1:30005 127.0.0.1:30006';
```

**Note**: `session_redis_auth` has been deprecated; use `session_redis_password`.

To use `cluster` you need also to install:
```shell
luarocks install kong-redis-cluster
# OR
luarocks install lua-resty-redis-cluster

# OR install this manually https://github.com/steve0511/resty-redis-cluster
```

The keys stored in Redis are in form:

`{prefix}:{session id}` and `{prefix}:{session id}.lock`.

#### DSHM Storage Adapter

DSHM storage adapter stores the session data inside Distributed Shared Memory server based
on Vertx and Hazelcast. It is scalable and works with web farms.

The DSHM lua library and the DSHM servers should be installed conforming with the documentation
[here](https://github.com/grrolland/ngx-distributed-shm/blob/master/README.md).


DSHM adapter can be selected with configuration:

```nginx
set $session_storage dshm;
```

Additionally you can configure DSHM adapter with these settings:

```nginx
set $session_dshm_region           sessions;
set $session_dshm_connect_timeout  1000; # (in milliseconds)
set $session_dshm_send_timeout     1000; # (in milliseconds)
set $session_dshm_read_timeout     1000; # (in milliseconds)
set $session_dshm_host             127.0.0.1;
set $session_dshm_port             4321;
set $session_dshm_pool_name        sessions;
set $session_dshm_pool_timeout     1000; # (in milliseconds)
set $session_dshm_pool_size        10;
set $session_dshm_pool_backlog     10;
```

The keys stored in DSHM are in form:

`{region}::{encoded session id}`

The `region` represents the cache region in DSHM.

#### Implementing a Storage Adapter

It is possible to implement additional storage adapters using the plugin architecture in `lua-resty-session`.

You need to implement APIs you need

* `storage new(session)`
* `boolean storage:open(id)`
* `boolean storage:start(id)`
* `boolean storage:save(id, ttl, data, close)`
* `bookean storage:close(id)`
* `boolean storage:destroy(id)`
* `boolean storage:ttl(id, ttl, close)`

The `id` parameter is already encoded, but `data` is in raw bytes, so please encode it as needed.

You have to place your adapter inside `resty.session.storage` for auto-loader to work.

To configure session to use your adapter, you can do so with Nginx configuration
(or in Lua code):

```nginx
# Just an example. Pull request for MySQL support is greatly welcomed.
set $session_storage mysql;
```

## Pluggable Ciphers

With version 2.1 we started to support pluggable ciphers. We currently have support for these ciphers:

* `aes` aka AES encryption / decryption using `lua-resty-string`'s AES library (the default).
* `none` aka no encryption or decryption is done.

The cipher adapter can be selected from Nginx config like this:

```nginx
set $session_cipher aes;
```

Or with Lua code like this:

```lua
local session = require "resty.session".start{ cipher = "aes" }
```

#### AES Cipher

AES Cipher uses `lua-resty-string`'s (an OpenResty core library) AES implementation
(bindings to OpenSSL) for encryption.

AES adapter can be selected with configuration:

```nginx
set $session_cipher aes;
```

Additionally you can configure Memcache adapter with these settings:

```nginx
set $session_aes_size   256;
set $session_aes_mode   "cbc";
set $session_aes_hash   "sha512";
set $session_aes_rounds 1;
```

Here follows the description of each setting:

**size**

`session.aes.size` holds the size of the cipher (`lua-resty-string` supports AES in `128`, `192`,
and `256` bits key sizes). See `aes.cipher` function in `lua-resty-string` for more information.
By default this will use `256` bits key size. This can be configured with Nginx
`set $session_aes_size 256;`.

**mode**

`session.aes.mode` holds the mode of the cipher. `lua-resty-string` supports AES in `ecb`, `cbc`,
`cfb1`, `cfb8`, `cfb128`, `ofb`, `ctr`, and `gcm` (recommended!) modes (ctr mode is not available
with 256 bit keys).  See `aes.cipher` function in `lua-resty-string` for more information.
By default `cbc` mode is  used. This can be configured with Nginx `set $session_aes_mode cbc;`.

**hash**

`session.aes.hash` is used in ecryption key, and iv derivation (see: OpenSSL
[EVP_BytesToKey](https://www.openssl.org/docs/crypto/EVP_BytesToKey.html)). By default `sha512` is
used but `md5`, `sha1`, `sha224`, `sha256`, and `sha384` are supported as well in `lua-resty-string`.
This can be configured with Nginx `set $session_aes_hash sha512;`.

**rounds**

`session.aes.rounds` can be used to slow-down the encryption key, and iv derivation. By default
this is set to `1` (the fastest). This can be configured with Nginx `set $session_aes_rounds 1;`.

#### None Cipher

None cipher disables encryption of the session data. This can be handy if you want to
debug things or want you session management as light as possible, or perhaps share the
session data with some other process without having to deal with encryption key management.
In general it is better to have encryption enabled in a production.

None adapter can be selected with configuration:

```nginx
set $session_cipher none;
```

There isn't any settings for None adapter as it is basically a no-op adapter.

#### Implementing a Cipher Adapter

If you want to write your own cipher adapter, you need to implement these three methods:

* `cipher new(session)`
* `string, err, tag = cipher:encrypt(data, key, salt, aad)`
* `string, err, tag = cipher:decrypt(data, key, salt, aad, tag)`

If you do not use say salt or aad (associated data) in your cipher, you can ignore them.
If you don't use `AEAD` construct (like `AES in GCM-mode`), don't return `tag`.

You have to place your adapter inside `resty.session.ciphers` for auto-loader to work.

## Pluggable Serializers

Currently we only support JSON serializer, but there is a plugin architecture that you can use to
plugin your own serializer. The serializer is used to serialize session data in a form that can be
later deserialized and stored in some of our supported storages.

The supported serializer names are:

* `json`

You need only to implement two functions to write an adapter:

* `string serialize(table)`
* `table  deserialize(string)`

You have to place your adapter inside `resty.session.serializers` for auto-loader to work.

To configure session to use your adapter, you can do so with Nginx configuration (or in Lua code):

```nginx
set $session_serializer json;
```

## Pluggable Compressors

The session data may grew quite a big if you decide to store for example JWT tokens in a session.
By compressing the data we can make the data part of the cookie smaller before sending it to client
or before storing it to a backend store (using pluggable storage adapters).

The supported compressors are:

* `none` (the default)
* `zlib` (this has extra requirement to `penlight` and `ffi-zlib`)

To use `zlib` you need also to install:
```shell
luarocks install lua-ffi-zlib
luarocks install penlight

# OR install these manually:
# - https://github.com/hamishforbes/lua-ffi-zlib
# - https://github.com/lunarmodules/Penlight
```


If you want to write your own compressor you need to implement these three methods:

* `cipher new(session)`
* `string compressor:compress(data)`
* `string compressor:decompress(data)`

To configure session to use your compressor, you can do so with Nginx configuration (or in Lua code):

```nginx
set $session_compressor none;
```

## Pluggable Encoders

Cookie data needs to be encoded in cookie form before it is send to client. We support
two encoding methods by default: modified cookie friendly base-64, and base-16 (or hexadecimal encoding).

The supported encoder names are:

* `base64`
* `base16` or `hex`

If you want to write your own encoder, you need to implement these two methods:

* `string encode(string)`
* `string decode(string)`

You have to place your adapter inside `resty.session.encoders` for auto-loader to work.

To configure session to use your adapter, you can do so with Nginx configuration (or in Lua code):

```nginx
set $session_encoder base64;
```

## Pluggable Session Identifier Generators

With version 2.12 we started to support pluggable session identifier generators in `lua-resty-session`.
Right now we support only one type of generator, and that is:

* `random`

If you want to write your own session identifier generator, you need to implement one function:

* `string generate(session)`

(the `config` is actually a `session` instance)

You have to place your generator inside `resty.session.identifiers` for auto-loader to work.

To configure session to use your generator, you can do so with Nginx configuration (or in Lua code):

```nginx
set $session_identifier_generator random;
```

#### Random Sesssion Identifier Generator

Random generator uses `lua-resty-string`'s (an OpenResty core library) OpenSSL based cryptographically
safe random generator.

Random generator can be selected with configuration:

```nginx
set $session_identifier random;
```

Additionally you can configure Random generator with these settings:

```nginx
set $session_random_length 16;
```

Here follows the description of each setting:

**length**

`session.random.length` holds the length of the `session.id`. By default it is 16 bytes.
This can be configured with Nginx `set $session_random_length 16;`.

## Lua API

### Functions and Methods

#### session session.new(opts)

With this function you can create a new session table (i.e. the actual session instance). This allows
you to generate session table first, and set invidual configuration before calling `session:open()` or
`session:start()`. You can also pass in `opts` Lua `table` with the configurations.

```lua
local session = require "resty.session".new()
-- set the configuration parameters before calling start
session.cookie.domain = "mydomain.com"
-- call start before setting session.data parameters
session:start()
session.data.uid = 1
-- save session and update the cookie to be sent to the client
session:save()
```

This is equivalent to this:

```lua
local session = require "resty.session".new{ cookie = { domain = "mydomain.com" } }
session:start()
session.data.uid = 1
session:save()
```

As well as with this:

```lua
local session = require "resty.session".start{ cookie = { domain = "mydomain.com" } }
session.data.uid = 1
session:save()
```

#### session, present, reason = session.open(opts, keep_lock)

With this function you can open a new session. It will create a new session Lua `table` on each call (unless called with
colon `:` as in examples above with `session.new`). Calling this function repeatedly will be a no-op when using colon `:`.
This function will return a (new) session `table` as a result. If the session cookie is supplied with user's HTTP(S)
client then this function validates the supplied session cookie. If validation is successful, the user supplied session
data will be used (if not, a new session is generated with empty data). You may supply optional session configuration
variables with `opts` argument, but be aware that many of these will only have effect if the session is a fresh session
(i.e. not loaded from user supplied cookie). If you set the `keep_lock` argument to `true` the possible lock implemented
by a storage adapter will not be released after opening the session. The second `boolean` return argument `present` will
be `true` if the user client send a valid cookie (meaning that session was already started on some earlier request),
and `false` if the new session was created (either because user client didn't send a cookie or that the cookie was not
a valid one). If the cookie was not `present` the last `string` argument `reason` will return the reason why it failed
to open a session cookie. This function will not set a client cookie or write data to database (e.g. update the expiry).
You need to call `session:start()` to really start the session. This open function is mainly used if you only want to
read data and avoid automatically sending a cookie (see also issue [#12](https://github.com/bungle/lua-resty-session/issues/12)).
But be aware that this doesn't update cookie expiration time stored in a cookie or in the database.

```lua
local session = require "resty.session".open()
-- Set some options (overwriting the defaults or nginx configuration variables)
local session = require "resty.session".open{ random = { length = 32 }}
-- Read some data
if session.present then
    ngx.print(session.data.uid)
end
-- Now let's really start the session
-- (session.started will be always false in this example):
if not session.started then
    session:start() -- with some storage adapters this will held a lock.
end

session.data.greeting = "Hello, World!"
session:save() -- this releases the possible lock held by :start()
```

#### session, present, reason session.start(opts)

With this function you can start a new session. It will create a new session Lua `table` on each call (unless called with
colon `:` as in examples above with `session.new`). Right now you should only start session once per request as calling
this function repeatedly will overwrite the previously started session cookie and session data. This function will return
a (new) session `table` as a result. If the session cookie is supplied with user's HTTP(S) client then this function
validates the supplied session cookie. If validation is successful, the user supplied session data will be used
(if not, a new session is generated with empty data). You may supply optional session configuration variables
with `opts` argument, but be aware that many of these will only have effect if the session is a fresh session
(i.e. not loaded from user supplied cookie). This function does also manage session cookie renewing configured
with `$session_cookie_renew`. E.g. it will send a new cookie with a new expiration time if the following is
met `session.expires - now < session.cookie.renew or session.expires > now + session.cookie.lifetime`. The second
`boolean` return argument will be `true` if the user client send a valid cookie (meaning that session was already
started on some earlier request), and `false` if the new session was created (either because user client didn't send
a cookie or that the cookie was not a valid one). On error this will return nil and error message.

```lua
local session = require "resty.session".start()
-- Set some options (overwriting the defaults or nginx configuration variables)
local session = require "resty.session".start{ random = { length = 32 }}
-- Always remember to:
session:close()
-- OR
session:save()
-- OR
session:destroy()
```

#### boolean session.destroy(opts)

This function will immediately set session data to empty table `{}`. It will also send a new cookie to
client with empty data and Expires flag `Expires=Thu, 01 Jan 1970 00:00:01 GMT` (meaning that the client
should remove the cookie, and not send it back again). This function returns a boolean value if everything went
as planned. It returns nil and error on failure.

```lua
require "resty.session".destroy()
-- but usually you want to possibly lock (server side storages)
-- the session before destroying
local session require "resty.session".start()
session:destroy()
```

#### string session:get_cookie()

Returns the cookie from the request or `nil` if the cookie was not found.

#### table session:parse_cookie(cookie)

Parses cookie and returns the data back as a `table` on success and `nil` and error on errors.

#### boolean session:regenerate(flush, close)

This function regenerates a session. It will generate a new session identifier (`session.id`) and optionally
flush the session data if `flush` argument evaluates `true`. It will automatically call `session:save` which
means that a new expires flag is set on the cookie, and the data is encrypted with the new parameters. With
client side sessions (`cookie` storage adapter) this overwrites the current cookie with a new one (but it
doesn't invalidate the old one as there is no state held on server side - invalidation actually happens when
the cookie's expiration time is not valid anymore). Optionally you may pass `false` to this method as a second
argument, if you don't want to `close` the session just yet, but just to regenerate a new id and save the session.
This function returns a boolean value if everything went as planned. If not it will return `nil` and error string
as a second return value.

```lua
local session = require "resty.session".start()
session:regenerate()
-- flush the current data, and but keep session
-- open and possible locks still held
session:regenerate(true, false)
```

#### boolean session:save(close)

This function saves the session and sends (not immediate though, as actual sending is handled by Nginx/OpenResty)
a new cookie to client (with a new expiration time and encrypted data). You need to call this function whenever
you want to save the changes made to `session.data` table. It is advised that you call this function only once
per request (no need to encrypt and set cookie many times). This function returns a boolean value if everything
went as planned. If not it will return error string as a second return value. Optionally you may pass `false`
to this method, if you don't want to `close` the session just yet, but just to save the data.

```lua
local session = require "resty.session".start()
session.data.uid = 1
session:save()
```

#### boolean, string session:close()

This function is mainly usable with storages that implement `locking` as calling this with e.g. `cookie` storage
does not do anything else than set `session.closed` to `true`.


#### session:hide()

Sometimes, when you are using `lua-resty-session` in reverse proxy, you may want to hide the session
cookies from the upstream server. To do that you can call `session:hide()`.

```lua
local session = require "resty.session".start()
session:hide()
```

### Fields

#### string session.id

`session.id` holds the current session id. By default it is 16 bytes long (raw binary bytes).
It is automatically generated.

#### boolean session.present

`session.present` can be used to check if the session that was opened with `session.open` or `session.start`
was really a one the was received from a client. If the session is a new one, this will be false.

#### boolean session.opened

`session.opened` can be used to check if the `session:open()` was called for the current session
object.

#### boolean session.started

`session.started` can be used to check if the `session:start()` was called for the current session
object.

#### boolean session.destroyed

`session.destroyed` can be used to check if the `session:destroy()` was called for the current session
object. It will also set `session.opened`, `session.started`,  and `session.present` to false.

#### boolean session.closed

`session.closed` can be used to check if the `session:close()` was called for the current session
object.

#### string session.key

`session.key` holds the HMAC key. It is automatically generated. Nginx configuration like
`set $session_check_ssi on;`, `set $session_check_ua on;`, `set $session_check_scheme on;` and `set $session_check_addr on;`
 will have effect on the generated key.

#### table session.data

`session.data` holds the data part of the session cookie. This is a Lua `table`. `session.data`
is the place where you store or retrieve session variables. When you want to save the data table,
you need to call `session:save` method.

**Setting session variable:**

```lua
local session = require "resty.session".start()
session.data.uid = 1
session:save()
```

**Retrieving session variable (in other request):**

```lua
local session = require "resty.session".open()
local uid = session.data.uid
```

#### number session.expires

`session.expires` holds the expiration time of the session (expiration time will be generated when
`session:save` method is called).

#### string session.secret

`session.secret` holds the secret that is used in keyed HMAC generation.

#### boolean session.cookie.persistent

`session.cookie.persistent` is by default `false`. This means that cookies are not persisted between browser sessions
(i.e. they are deleted when the browser is closed). You can enable persistent sessions if you want to by setting this
to `true`. This can be configured with Nginx `set $session_cookie_persistent on;`.

#### number session.usebefore

`session.usebefore` holds the expiration time based on session usgae (expiration time will be generated
when the session is saved or started). This expiry time is only stored client-side in the cookie.
Note that just opening a session will not update the cookie! To mark the session as used you must call
`session:touch`. (You can also use `session:save` but that will also write session data to the
storage, whereas just calling `touch` reads the session data and updates the `usebefore` value in the
client-side cookie without writing to the storage, it will just be setting a new cookie)

#### number session.cookie.idletime

`session.cookie.idletime` holds the cookie idletime in seconds in the future. If a cookie is not used
(idle) for this time, the session becomes invalid. By default this is set to 0 seconds, meaning it is
disabled. This can be configured with Nginx `set $session_cookie_idletime 300;`.

#### number session.cookie.discard

`session.cookie.discard` holds the time in seconds how of long you want to keep old cookies alive when
using `regenerate` session strategy. This can be configured with Nginx `set $session_cookie_discard 10;`
(10 seconds is the default value). This works only with server side session storage adapters and when
using `regenerate` strategy (perhaps your custom strategy could utilize this too).

#### number session.cookie.renew

`session.cookie.renew` holds the minimun seconds until the cookie expires, and renews cookie automatically
(i.e. sends a new cookie with a new expiration time according to `session.cookie.lifetime`). This can be configured
with Nginx `set $session_cookie_renew 600;` (600 seconds is the default value).

#### number session.cookie.lifetime

`session.cookie.lifetime` holds the cookie lifetime in seconds in the future. By default this is set
to 3,600 seconds. This can be configured with Nginx `set $session_cookie_lifetime 3600;`. This does not
set cookie's expiration time on session only (by default) cookies, but it is used if the cookies are
configured persistent with `session.cookie.persistent == true`. See also notes about
[ssl_session_timeout](#nginx-configuration-variables).

#### string session.cookie.path

`session.cookie.path` holds the value of the cookie path scope. This is by default permissive `/`. You
may want to have a more specific scope if your application resides in different path (e.g. `/forums/`).
This can be configured with Nginx `set $session_cookie_path /forums/;`.

#### string session.cookie.domain

`session.cookie.domain` holds the value of the cookie domain. By default this is automatically set using
Nginx variable `host`. This can be configured with Nginx `set $session_cookie_domain openresty.org;`.
For `localhost` this is omitted.

#### string session.cookie.samesite

`session.cookie.samesite` holds the value of the cookie SameSite flag. By default we do use value of `Lax`.
The possible values are `Lax`, `Strict`, `None`, and `off`. Actually, setting this parameter anything else than
`Lax`, `Strict` or `None` will turn this off (but in general, you shouldn't do it). If you want better protection
against Cross Site Request Forgery (CSRF), set this to `Strict`. Default value of `Lax` gives you quite a
good protection against CSRF, but `Strict` goes even further.

#### boolean session.cookie.secure

`session.cookie.secure` holds the value of the cookie `Secure` flag. meaning that when set the client will
only send the cookie with encrypted TLS/SSL connection. By default the `Secure` flag is set on all the
cookies where the request was made through TLS/SSL connection. This can be configured and forced with
Nginx `set $session_cookie_secure on;`.

#### boolean session.cookie.httponly

`session.cookie.httponly` holds the value of the cookie `HttpOnly` flag. By default this is enabled,
and I cannot think of an situation where one would want to turn this off. By keeping this on you can
prevent your session cookies access from Javascript and give some safety of XSS attacks. If you really
want to turn this off, this can be configured with Nginx `set $session_cookie_httponly off;`.

#### string session.cookie.maxsize

`session.cookie.maxsize` is used to configure maximum size of a single cookie. This value is used to split a
large cookie into chunks. By default it is `4000` bytes of serialized and encoded data which does not count
the cookie name and cookie flags. If you expect your cookies + flags be more than e.g. `4096` bytes, you
should reduce the `session.cookie.maxsize` so that a single cookie fits into `4096` bytes because otherwise
the user-agent may ignore the cookie (being too big).

#### number session.cookie.chunks

`session.cookie.chunks` should be used as a read only property to determine how many separate cookies was
used for a session. Usually this is `1`, but if you are using a `cookie` storage backend and store a lot
of data in session, then the cookie is divided to `n` chunks where each stores data containing 4.000 bytes
(the last one 4000 or less). This was implemented in version 2.15.

#### boolean session.check.ssi

`session.check.ssi` is additional check to validate that the request was made with the same SSL
session as when the original cookie was delivered. This check is enabled by default on releases prior 2.12
on non-persistent sessions and disabled by default on persistent sessions and on releases 2.12 and later.
Please note that on TLS with TLS Tickets enabled, this will be empty) and not used. This is discussed on issue #5
(https://github.com/bungle/lua-resty-session/issues/5). You can disable TLS tickets with Nginx configuration:

```nginx
ssl_session_tickets off;
```

#### boolean session.check.ua

`session.check.ua` is additional check to validate that the request was made with the same user-agent browser string
as where the original cookie was delivered. This check is enabled by default.

#### boolean session.check.addr

`session.check.addr` is additional check to validate that the request was made from the same remote ip-address
as where the original cookie was delivered. This check is disabled by default.

#### boolean session.check.scheme

`session.check.scheme` is additional check to validate that the request was made using the same protocol
as the one used when the original cookie was delivered. This check is enabled by default.

## Nginx Configuration Variables

You can set default configuration parameters directly from Nginx configuration. It's **IMPORTANT** to understand
that these are read only once (not on every request), for performance reasons. This is especially important if
you run multiple sites (with different configurations) on the same Nginx server. You can of course set the common
parameters on Nginx configuration even on that case. But if you are really supporting multiple site with different
configurations (e.g. different `session.secret` on each site), you should set these in code (see: `session.new`
and `session.start`).

Please note that Nginx has also its own SSL/TLS caches and timeouts. Especially note `ssl_session_timeout` if you
are running services over SSL/TLS as this will end sessions regardless of `session.cookie.lifetime`. Please adjust
that accordingly or disable `ssl_session_id` check `session.check.ssi = false` (in code) or
`set $session_check_ssi off;` (in Nginx configuration). As of 2.12 checking SSL session identifier check
(`$session_check_ssi` / `session.check.ssi`) is disabled by default because it was not reliable (most servers use
session tickets now), and it usually needed extra configuration.

You may want to add something like this to your Nginx SSL/TLS config (quite a huge cache in this example, 1 MB is
about 4.000 SSL sessions):

```nginx
ssl_session_cache shared:SSL:100m;
ssl_session_timeout 60m;
```

Also note that the `ssl_session_id` may be `null` if the TLS tickets are enabled. You can disable tickets in Nginx
server with the configuration below:

```nginx
ssl_session_tickets off;
```

Right now this is a workaround and may change in a future if we find alternative ways to have the added security
that we have with `ssl_session_id` with TLS tickets too. While TLS tickets are great, they also have effect on
(Perfect) Forward Secrecy, and it is adviced to disable tickets until the problems mentioned in
[The Sad State of Server-Side TLS Session Resumption Implementations](https://timtaubert.de/blog/2014/11/the-sad-state-of-server-side-tls-session-resumption-implementations/)
article are resolved.

Here is a list of `lua-resty-session` related Nginx configuration variables that you can use to control
`lua-resty-session`:

```nginx
set $session_name              session;
set $session_secret            623q4hR325t36VsCD3g567922IC0073T;
set $session_strategy          default;
set $session_storage           cookie;
set $session_hmac              sha1;
set $session_cipher            aes;
set $session_encoder           base64;
set $session_serializer        json;
set $session_compressor        none;
set $session_cookie_persistent off;
set $session_cookie_discard    10;
set $session_cookie_idletime   0;
set $session_cookie_renew      600;
set $session_cookie_lifetime   3600;
set $session_cookie_path       /;
set $session_cookie_domain     openresty.org;
set $session_cookie_samesite   Lax;
set $session_cookie_secure     on;
set $session_cookie_httponly   on;
set $session_cookie_delimiter  |;
set $session_cookie_maxsize    4000;
set $session_check_ssi         off;
set $session_check_ua          on;
set $session_check_scheme      on;
set $session_check_addr        off;
set $session_random_length     16;
set $session_aes_mode          cbc;
set $session_aes_size          256;
set $session_aes_hash          sha512;
set $session_aes_rounds        1;
```

## Changes

The changes of every release of this module is recorded in [Changes.md](https://github.com/bungle/lua-resty-session/blob/master/Changes.md) file.

## Roadmap

* Add support for different schemes:
    * Encrypt-and-MAC: The ciphertext is generated by encrypting the plaintext and then appending a MAC of the plaintext.
    * MAC-then-encrypt: The ciphertext is generated by appending a MAC to the plaintext and then encrypting everything.
    * Encrypt-then-MAC: The ciphertext is generated by encrypting the plaintext and then appending a MAC of the encrypted plaintext.
    * Authenticated Encryption with Associated Data (AEAD)
* Add support for HMAC plugins
* Add support for `lua-resty-nettle` for more wide variety of encryption algorithms as a plugin.
* Implement cookieless server-side session support using `ssl_session_id` as a `session.id` (using a server-side storage).

## See Also

* [lua-resty-route](https://github.com/bungle/lua-resty-route) — Routing library
* [lua-resty-reqargs](https://github.com/bungle/lua-resty-reqargs) — Request arguments parser
* [lua-resty-template](https://github.com/bungle/lua-resty-template) — Templating engine
* [lua-resty-validation](https://github.com/bungle/lua-resty-validation) — Validation and filtering library

## License

`lua-resty-session` uses two clause BSD license.

```
Copyright (c) 2014 – 2022 Aapo Talvensaari
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
  list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
```
