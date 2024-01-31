# lua-resty-http

Lua HTTP client cosocket driver for [OpenResty](http://openresty.org/) / [ngx\_lua](https://github.com/openresty/lua-nginx-module).

## Status

Production ready.

[![Test](https://github.com/ledgetech/lua-resty-http/actions/workflows/test.yml/badge.svg)](https://github.com/ledgetech/lua-resty-http/actions)

## Features

* HTTP 1.0 and 1.1
* SSL
* Streaming interface to the response body, for predictable memory usage
* Alternative simple interface for single-shot requests without a manual connection step
* Chunked and non-chunked transfer encodings
* Connection keepalives
* Request pipelining
* Trailers
* HTTP proxy connections
* mTLS (requires `ngx_lua_http_module` >= v0.10.23)


## API

* [new](#new)
* [connect](#connect)
* [set\_proxy\_options](#set_proxy_options)
* [set\_timeout](#set_timeout)
* [set\_timeouts](#set_timeouts)
* [set\_keepalive](#set_keepalive)
* [get\_reused\_times](#get_reused_times)
* [close](#close)
* [request](#request)
* [request\_uri](#request_uri)
* [request\_pipeline](#request_pipeline)
* [parse\_uri](#parse_uri)
* [get\_client\_body\_reader](#get_client_body_reader)
* [Response](#response)
    * [body\_reader](#resbody_reader)
    * [read\_body](#resread_body)
    * [read\_trailers](#resread_trailers)

### Deprecated

These methods may be removed in future versions.

* [connect\_proxy](#connect_proxy)
* [ssl\_handshake](#ssl_handshake)
* [proxy\_request](#proxy_request)
* [proxy\_response](#proxy_response)

## Usage

There are two basic modes of operation:

1. **Simple single-shot requests** which require no manual connection management but which buffer the entire response and leave the connection either closed or back in the connection pool.

2. **Streamed requests** where the connection is established separately, then the request is sent, the body stream read in chunks, and finally the connection is manually closed or kept alive. This technique requires a little more code but provides the ability to discard potentially large response bodies on the Lua side, as well as pipelining multiple requests over a single connection.

### Single-shot request

```lua
local httpc = require("resty.http").new()

-- Single-shot requests use the `request_uri` interface.
local res, err = httpc:request_uri("http://example.com/helloworld", {
    method = "POST",
    body = "a=1&b=2",
    headers = {
        ["Content-Type"] = "application/x-www-form-urlencoded",
    },
})
if not res then
    ngx.log(ngx.ERR, "request failed: ", err)
    return
end

-- At this point, the entire request / response is complete and the connection
-- will be closed or back on the connection pool.

-- The `res` table contains the expeected `status`, `headers` and `body` fields.
local status = res.status
local length = res.headers["Content-Length"]
local body   = res.body
```

### Streamed request

```lua
local httpc = require("resty.http").new()

-- First establish a connection
local ok, err, ssl_session = httpc:connect({
    scheme = "https",
    host = "127.0.0.1",
    port = 8080,
})
if not ok then
    ngx.log(ngx.ERR, "connection failed: ", err)
    return
end

-- Then send using `request`, supplying a path and `Host` header instead of a
-- full URI.
local res, err = httpc:request({
    path = "/helloworld",
    headers = {
        ["Host"] = "example.com",
    },
})
if not res then
    ngx.log(ngx.ERR, "request failed: ", err)
    return
end

-- At this point, the status and headers will be available to use in the `res`
-- table, but the body and any trailers will still be on the wire.

-- We can use the `body_reader` iterator, to stream the body according to our
-- desired buffer size.
local reader = res.body_reader
local buffer_size = 8192

repeat
    local buffer, err = reader(buffer_size)
    if err then
        ngx.log(ngx.ERR, err)
        break
    end

    if buffer then
        -- process
    end
until not buffer

local ok, err = httpc:set_keepalive()
if not ok then
    ngx.say("failed to set keepalive: ", err)
    return
end

-- At this point, the connection will either be safely back in the pool, or closed.
````

# Connection

## new

`syntax: httpc, err = http.new()`

Creates the HTTP connection object. In case of failures, returns `nil` and a string describing the error.

## connect

`syntax: ok, err, ssl_session = httpc:connect(options)`

Attempts to connect to the web server while incorporating the following activities:

- TCP connection
- SSL handshake
- HTTP proxy configuration

In doing so it will create a distinct connection pool name that is safe to use with SSL and / or proxy based connections, and as such this syntax is strongly recommended over the original (now deprecated) [TCP only connection syntax](#TCP-only-connect).

The options table has the following fields:

* `scheme`: scheme to use, or nil for unix domain socket
* `host`: target host, or path to a unix domain socket
* `port`: port on target host, will default to `80` or `443` based on the scheme
* `pool`: custom connection pool name. Option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsockconnect), except that the default will become a pool name constructed using the SSL / proxy properties, which is important for safe connection reuse. When in doubt, leave it blank!
* `pool_size`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsockconnect)
* `backlog`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsockconnect)
* `proxy_opts`: sub-table, defaults to the global proxy options set, see [set\_proxy\_options](#set_proxy_options).
* `ssl_reused_session`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake)
* `ssl_verify`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake), except that it defaults to `true`.
* `ssl_server_name`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake)
* `ssl_send_status_req`: option as per [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsocksslhandshake)
* `ssl_client_cert`: will be passed to `tcpsock:setclientcert`. Requires `ngx_lua_http_module` >= v0.10.23.
* `ssl_client_priv_key`: as above.

## set\_timeout

`syntax: httpc:set_timeout(time)`

Sets the socket timeout (in ms) for subsequent operations. See [set\_timeouts](#set_timeouts) below for a more declarative approach.

## set\_timeouts

`syntax: httpc:set_timeouts(connect_timeout, send_timeout, read_timeout)`

Sets the connect timeout threshold, send timeout threshold, and read timeout threshold, respectively, in milliseconds, for subsequent socket operations (connect, send, receive, and iterators returned from receiveuntil).

## set\_keepalive

`syntax: ok, err = httpc:set_keepalive(max_idle_timeout, pool_size)`

Either places the current connection into the pool for future reuse, or closes the connection. Calling this instead of [close](#close) is "safe" in that it will conditionally close depending on the type of request. Specifically, a `1.0` request without `Connection: Keep-Alive` will be closed, as will a `1.1` request with `Connection: Close`.

In case of success, returns `1`. In case of errors, returns `nil, err`. In the case where the connection is conditionally closed as described above, returns `2` and the error string `connection must be closed`, so as to distinguish from unexpected errors.

See [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsocksetkeepalive) for parameter documentation.

## set\_proxy\_options

`syntax: httpc:set_proxy_options(opts)`

Configure an HTTP proxy to be used with this client instance. The `opts` table expects the following fields:

* `http_proxy`: an URI to a proxy server to be used with HTTP requests
* `http_proxy_authorization`: a default `Proxy-Authorization` header value to be used with `http_proxy`, e.g. `Basic ZGVtbzp0ZXN0`, which will be overriden if the `Proxy-Authorization` request header is present.
* `https_proxy`: an URI to a proxy server to be used with HTTPS requests
* `https_proxy_authorization`: as `http_proxy_authorization` but for use with `https_proxy` (since with HTTPS the authorisation is done when connecting, this one cannot be overridden by passing the `Proxy-Authorization` request header).
* `no_proxy`: a comma separated list of hosts that should not be proxied.

Note that this method has no effect when using the deprecated [TCP only connect](#TCP-only-connect) connection syntax.

## get\_reused\_times

`syntax: times, err = httpc:get_reused_times()`

See [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsockgetreusedtimes).

## close

`syntax: ok, err = httpc:close()`

See [OpenResty docs](https://github.com/openresty/lua-nginx-module#tcpsockclose).

# Requesting

## request

`syntax: res, err = httpc:request(params)`

Sends an HTTP request over an already established connection. Returns a `res` table or `nil` and an error message.

The `params` table expects the following fields:

* `version`: The HTTP version number. Defaults to `1.1`.
* `method`: The HTTP method string. Defaults to `GET`.
* `path`: The path string. Defaults to `/`.
* `query`: The query string, presented as either a literal string or Lua table..
* `headers`: A table of request headers.
* `body`: The request body as a string, a table of strings, or an iterator function yielding strings until nil when exhausted. Note that you must specify a `Content-Length` for the request body, or specify `Transfer-Encoding: chunked` and have your function implement the encoding. See also: [get\_client\_body\_reader](#get_client_body_reader)).

When the request is successful, `res` will contain the following fields:

* `status`: The status code.
* `reason`: The status reason phrase.
* `headers`: A table of headers. Multiple headers with the same field name will be presented as a table of values.
* `has_body`: A boolean flag indicating if there is a body to be read.
* `body_reader`: An iterator function for reading the body in a streaming fashion.
* `read_body`: A method to read the entire body into a string.
* `read_trailers`: A method to merge any trailers underneath the headers, after reading the body.

If the response has a body, then before the same connection can be used for another request, you must read the body using `read_body` or `body_reader`.

## request\_uri

`syntax: res, err = httpc:request_uri(uri, params)`

The single-shot interface (see [usage](#Usage)). Since this method performs an entire end-to-end request, options specified in the `params` can include anything found in both [connect](#connect) and [request](#request) documented above. Note also that fields `path`, and `query`, in `params` will override relevant components of the `uri` if specified (`scheme`, `host`, and `port` will always be taken from the `uri`).

There are 3 additional parameters for controlling keepalives:

* `keepalive`: Set to `false` to disable keepalives and immediately close the connection. Defaults to `true`.
* `keepalive_timeout`: The maximal idle timeout (ms). Defaults to `lua_socket_keepalive_timeout`.
* `keepalive_pool`: The maximum number of connections in the pool. Defaults to `lua_socket_pool_size`.

If the request is successful, `res` will contain the following fields:

* `status`: The status code.
* `headers`: A table of headers.
* `body`: The entire response body as a string.


## request\_pipeline

`syntax: responses, err = httpc:request_pipeline(params)`

This method works as per the [request](#request) method above, but `params` is instead a nested table of parameter tables. Each request is sent in order, and `responses` is returned as a table of response handles. For example:

```lua
local responses = httpc:request_pipeline({
    { path = "/b" },
    { path = "/c" },
    { path = "/d" },
})

for _, r in ipairs(responses) do
    if not r.status then
        ngx.log(ngx.ERR, "socket read error")
        break
    end

    ngx.say(r.status)
    ngx.say(r:read_body())
end
```

Due to the nature of pipelining, no responses are actually read until you attempt to use the response fields (status / headers etc). And since the responses are read off in order, you must read the entire body (and any trailers if you have them), before attempting to read the next response.

Note this doesn't preclude the use of the streaming response body reader. Responses can still be streamed, so long as the entire body is streamed before attempting to access the next response.

Be sure to test at least one field (such as status) before trying to use the others, in case a socket read error has occurred.

# Response

## res.body\_reader

The `body_reader` iterator can be used to stream the response body in chunk sizes of your choosing, as follows:

````lua
local reader = res.body_reader
local buffer_size = 8192

repeat
    local buffer, err = reader(buffer_size)
    if err then
        ngx.log(ngx.ERR, err)
        break
    end

    if buffer then
        -- process
    end
until not buffer
````

If the reader is called with no arguments, the behaviour depends on the type of connection. If the response is encoded as chunked, then the iterator will return the chunks as they arrive. If not, it will simply return the entire body.

Note that the size provided is actually a **maximum** size. So in the chunked transfer case, you may get buffers smaller than the size you ask, as a remainder of the actual encoded chunks.

## res:read\_body

`syntax: body, err = res:read_body()`

Reads the entire body into a local string.

## res:read\_trailers

`syntax: res:read_trailers()`

This merges any trailers underneath the `res.headers` table itself. Must be called after reading the body.

# Utility

## parse\_uri

`syntax: local scheme, host, port, path, query? = unpack(httpc:parse_uri(uri, query_in_path?))`

This is a convenience function allowing one to more easily use the generic interface, when the input data is a URI.

As of version `0.10`, the optional `query_in_path` parameter was added, which specifies whether the querystring is to be included in the `path` return value, or separately as its own return value. This defaults to `true` in order to maintain backwards compatibility. When set to `false`, `path` will only include the path, and `query` will contain the URI args, not including the `?` delimiter.


## get\_client\_body\_reader

`syntax: reader, err = httpc:get_client_body_reader(chunksize?, sock?)`

Returns an iterator function which can be used to read the downstream client request body in a streaming fashion. You may also specify an optional default chunksize (default is `65536`), or an already established socket in
place of the client request.

Example:

```lua
local req_reader = httpc:get_client_body_reader()
local buffer_size = 8192

repeat
    local buffer, err = req_reader(buffer_size)
    if err then
        ngx.log(ngx.ERR, err)
        break
    end

    if buffer then
        -- process
    end
until not buffer
```

This iterator can also be used as the value for the body field in request params, allowing one to stream the request body into a proxied upstream request.

```lua
local client_body_reader, err = httpc:get_client_body_reader()

local res, err = httpc:request({
    path = "/helloworld",
    body = client_body_reader,
})
```

# Deprecated

These features remain for backwards compatability, but may be removed in future releases.

### TCP only connect

*The following versions of the `connect` method signature are deprecated in favour of the single `table` argument [documented above](#connect).*

`syntax: ok, err = httpc:connect(host, port, options_table?)`

`syntax: ok, err = httpc:connect("unix:/path/to/unix.sock", options_table?)`

NOTE: the default pool name will only incorporate IP and port information so is unsafe to use in case of SSL and/or Proxy connections. Specify your own pool or, better still, do not use these signatures.

## connect\_proxy

`syntax: ok, err = httpc:connect_proxy(proxy_uri, scheme, host, port, proxy_authorization)`

*Calling this method manually is no longer necessary since it is incorporated within [connect](#connect). It is retained for now for compatibility with users of the older [TCP only connect](#TCP-only-connect) syntax.*

Attempts to connect to the web server through the given proxy server. The method accepts the following arguments:

* `proxy_uri` - Full URI of the proxy server to use (e.g. `http://proxy.example.com:3128/`). Note: Only `http` protocol is supported.
* `scheme` - The protocol to use between the proxy server and the remote host (`http` or `https`). If `https` is specified as the scheme, `connect_proxy()` makes a `CONNECT` request to establish a TCP tunnel to the remote host through the proxy server.
* `host` - The hostname of the remote host to connect to.
* `port` - The port of the remote host to connect to.
* `proxy_authorization` - The `Proxy-Authorization` header value sent to the proxy server via `CONNECT` when the `scheme` is `https`.

If an error occurs during the connection attempt, this method returns `nil` with a string describing the error. If the connection was successfully established, the method returns `1`.

There's a few key points to keep in mind when using this api:

* If the scheme is `https`, you need to perform the TLS handshake with the remote server manually using the `ssl_handshake()` method before sending any requests through the proxy tunnel.
* If the scheme is `http`, you need to ensure that the requests you send through the connections conforms to [RFC 7230](https://tools.ietf.org/html/rfc7230) and especially [Section 5.3.2.](https://tools.ietf.org/html/rfc7230#section-5.3.2) which states that the request target must be in absolute form. In practice, this means that when you use `send_request()`, the `path` must be an absolute URI to the resource (e.g. `http://example.com/index.html` instead of just `/index.html`).

## ssl\_handshake

`syntax: session, err = httpc:ssl_handshake(session, host, verify)`

*Calling this method manually is no longer necessary since it is incorporated within [connect](#connect). It is retained for now for compatibility with users of the older [TCP only connect](#TCP-only-connect) syntax.*

See [OpenResty docs](https://github.com/openresty/lua-nginx-module#ngxsockettcp).

## proxy\_request / proxy\_response

*These two convenience methods were intended simply to demonstrate a common use case of implementing reverse proxying, and the author regrets their inclusion in the module. Users are encouraged to roll their own rather than depend on these functions, which may be removed in a subsequent release.*

### proxy\_request

`syntax: local res, err = httpc:proxy_request(request_body_chunk_size?)`

Performs a request using the current client request arguments, effectively proxying to the connected upstream. The request body will be read in a streaming fashion, according to `request_body_chunk_size` (see [documentation on the client body reader](#get_client_body_reader) below).


### proxy\_response

`syntax: httpc:proxy_response(res, chunksize?)`

Sets the current response based on the given `res`. Ensures that hop-by-hop headers are not sent downstream, and will read the response according to `chunksize` (see [documentation on the body reader](#resbody_reader) above).


# Author

James Hurst <james@pintsized.co.uk>, with contributions from @hamishforbes, @Tieske, @bungle et al.

# Licence

This module is licensed under the 2-clause BSD license.

Copyright (c) James Hurst <james@pintsized.co.uk>

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
