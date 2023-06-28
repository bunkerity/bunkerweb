# lua-resty-session

**lua-resty-session** is a secure, and flexible session library for OpenResty.

## TL;DR;

- Sessions are immutable (each save generates a new session), and lockless.
- Session data is AES-256-GCM encrypted with a key derived using HKDF-SHA256.
- Session has a fixed size header that is protected with HMAC-SHA256 MAC with
  a key derived using HKDF-SHA256.
- Session data can be stored in a stateless cookie or in various backend storages.
- A single session cookie can maintain multiple sessions across different audiences.

*Note:* Version 4.0.0 was a rewrite of this library with a lot of lessons learned
during the years. If you still use older version, please refer
[old documentation](https://github.com/bungle/lua-resty-session/tree/v3.10).


## Status

This library is considered production ready.


## Synopsis

```nginx
worker_processes  1;

events {
  worker_connections 1024;
}

http {
  init_by_lua_block {
    require "resty.session".init({
      remember = true,
      audience = "demo",
      secret   = "RaJKp8UQW1",
      storage  = "cookie",
    })
  }
  
  server {
    listen       8080;
    server_name  localhost;
    default_type text/html;

    location / {
      content_by_lua_block {
        ngx.say([[
          <html>
          <body>
            <a href=/start>Start the test</a>
          </body>
          </html>
        ]])
      }
    }

    location /start {
      content_by_lua_block {
        local session = require "resty.session".new()
        session:set_subject("OpenResty Fan")
        session:set("quote", "The quick brown fox jumps over the lazy dog")
        local ok, err = session:save()
       
        ngx.say(string.format([[
          <html>
          <body>
            <p>Session started (%s)</p>
            <p><a href=/started>Check if it really was</a></p>
          </body>
          </html>
        ]], err or "no error"))
      }
    }

    location /started {
      content_by_lua_block {
        local session, err = require "resty.session".start()
        
        ngx.say(string.format([[
          <html>
          <body>
            <p>Session was started by %s (%s)</p>
            <p><blockquote>%s</blockquote></p>
            <p><a href=/modify>Modify the session</a></p>
          </body>
          </html>
        ]],
          session:get_subject() or "Anonymous",
          err or "no error",
          session:get("quote") or "no quote"
        ))
      }
    }
    
    location /modify {
      content_by_lua_block {
        local session, err = require "resty.session".start()
        session:set_subject("Lua Fan")
        session:set("quote", "Lorem ipsum dolor sit amet")
        local _, err_save = session:save()
        
        ngx.say(string.format([[
          <html>
          <body>
            <p>Session was modified (%s)</p>
            <p><a href=/modified>Check if it is modified</a></p>
          </body>
          </html>
        ]], err or err_save or "no error"))
      }
    }
    
    location /modified {
      content_by_lua_block {
        local session, err = require "resty.session".start()

        ngx.say(string.format([[
          <html>
          <body>
            <p>Session was started by %s (%s)</p>
            <p><blockquote>%s</blockquote></p>
            <p><a href=/destroy>Destroy the session</a></p>
          </body>
          </html>
        ]],
          session:get_subject() or "Anonymous",
          err or "no error",
          session:get("quote")  or "no quote"
        ))
      }
    }
    
    location /destroy {
      content_by_lua_block {
        local ok, err = require "resty.session".destroy()

        ngx.say(string.format([[
          <html>
          <body>
            <p>Session was destroyed (%s)</p>
            <p><a href=/destroyed>Check that it really was?</a></p>
          </body>
          </html>
        ]], err or "no error"))
      }
    }
    
    location /destroyed {
      content_by_lua_block {
        local session, err = require "resty.session".open()

        ngx.say(string.format([[
          <html>
          <body>
            <p>Session was really destroyed, you are known as %s (%s)</p>
            <p><a href=/>Start again</a></p>
          </body>
          </html>
        ]],
          session:get_subject() or "Anonymous",
          err or "no error"
        ))
      }
    }    
  }
}  
```


# Table of Contents

* [Installation](#installation)
    * [Using OpenResty Package Manager (opm)](#using-openresty-package-manager-opm)
    * [Using LuaRocks](#using-luarocks)
* [Configuration](#configuration)
    * [Session Configuration](#session-configuration)
    * [Cookie Storage Configuration](#cookie-storage-configuration)
    * [DSHM Storage Configuration](#dshm-storage-configuration)
    * [File Storage Configuration](#file-storage-configuration)
    * [Memcached Storage Configuration](#memcached-storage-configuration)
    * [MySQL / MariaDB Storage Configuration](#mysql--mariadb-storage-configuration)
    * [Postgres Configuration](#postgres-configuration)
    * [Redis Configuration](#redis-configuration)
        * [Single Redis Configuration](#single-redis-configuration)
        * [Redis Sentinels Configuration](#redis-sentinels-configuration)
        * [Redis Cluster Configuration](#redis-cluster-configuration)
    * [SHM Configuration](#shm-configuration)
* [API](#api)
    * [Initialization](#initialization)
        * [session.init](#sessioninit)
    * [Constructors](#constructors)
        * [session.new](#sessionnew)
    * [Helpers](#helpers)
        * [session.open](#sessionopen)
        * [session.start](#sessionstart)
        * [session.logout](#sessionlogout)
        * [session.destroy](#sessiondestroy)
    * [Instance Methods](#instance-methods)
        * [session:open](#sessionopen-1)
        * [session:save](#sessionsave)
        * [session:touch](#sessiontouch)
        * [session:refresh](#sessionrefresh)
        * [session:logout](#sessionlogout-1)
        * [session:destroy](#sessiondestroy-1)
        * [session:close](#sessionclose)
        * [session:set_data](#sessionset_data)
        * [session:get_data](#sessionget_data)
        * [session:set](#sessionset)
        * [session:get](#sessionget)
        * [session:set_audience](#sessionset_audience)
        * [session:get_audience](#sessionget_audience)
        * [session:set_subject](#sessionset_subject)
        * [session:get_subject](#sessionget_subject)
        * [session:get_property](#sessionget_property)
        * [session:set_remember](#sessionset_remember)
        * [session:get_remember](#sessionget_remember)
        * [session:clear_request_cookie](#sessionclear_request_cookie)
        * [session:set_headers](#sessionset_headers)
        * [session:set_request_headers](#sessionset_request_headers)
        * [session:set_response_headers](#sessionset_response_headers)
        * [session.info:set](#sessioninfoset)
        * [session.info:get](#sessioninfoget)
        * [session.info:save](#sessioninfosave)
* [Cookie Format](#cookie-format)
* [Data Encryption](#data-encryption)
* [Cookie Header Authentication](#cookie-header-authentication)
* [Custom Storage Interface](#custom-storage-interface)
* [License](#license)


# Installation

## Using OpenResty Package Manager (opm)

```bash
❯ opm get bungle/lua-resty-session
```

Please note that `opm` doesn't install all the dependencies like LuaRocks does, e.g. you will still need
to install [lua_pack](https://github.com/Kong/lua-pack). Also check the dependencies for each storage
driver (there may be additional dependencies).

## Using LuaRocks

```bash
❯ luarocks install lua-resty-session
```

LuaRocks repository for `lua-resty-session` is located at https://luarocks.org/modules/bungle/lua-resty-session.

Also check the dependencies for each storage (there may be additional dependencies).


# Configuration

The configuration can be divided to generic session configuration and the server
side storage configuration.

Here is an example:

```lua
init_by_lua_block {
  require "resty.session".init({
    remember = true,
    store_metadata = true,
    secret = "RaJKp8UQW1",
    secret_fallbacks = {
      "X88FuG1AkY",
      "fxWNymIpbb",
    },
    storage = "postgres",
    postgres = {
      username = "my-service",
      password = "kVgIXCE5Hg",
      database = "sessions",
    },
  })
}
```


## Session Configuration

Session configuration can be passed to [initialization](#initialization), [constructor](#constructors),
and [helper](#helpers) functions.

Here are the possible session configuration options:

| Option                      |   Default    | Description                                                                                                                                                                                                                                                                                          |
|-----------------------------|:------------:|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `secret`                    |    `nil`     | Secret used for the key derivation. The secret is hashed with SHA-256 before using it. E.g. `"RaJKp8UQW1"`.                                                                                                                                                                                          |
| `secret_fallbacks`          |    `nil`     | Array of secrets that can be used as alternative secrets (when doing key rotation), E.g. `{ "6RfrAYYzYq", "MkbTkkyF9C" }`.                                                                                                                                                                           |
| `ikm`                       |   (random)   | Initial keying material (or ikm) can be specified directly (without using a secret) with exactly 32 bytes of data. E.g. `"5ixIW4QVMk0dPtoIhn41Eh1I9enP2060"`                                                                                                                                         |
| `ikm_fallbacks`             |    `nil`     | Array of initial keying materials that can be used as alternative keys (when doing key rotation), E.g. `{ "QvPtlPKxOKdP5MCu1oI3lOEXIVuDckp7" }`.                                                                                                                                                     |
| `cookie_prefix`             |    `nil`     | Cookie prefix, use `nil`, `"__Host-"` or `"__Secure-"`.                                                                                                                                                                                                                                              |
| `cookie_name`               | `"session"`  | Session cookie name, e.g. `"session"`.                                                                                                                                                                                                                                                               |
| `cookie_path`               |    `"/"`     | Cookie path, e.g. `"/"`.                                                                                                                                                                                                                                                                             |
| `cookie_http_only`          |    `true`    | Mark cookie HTTP only, use `true` or `false`.                                                                                                                                                                                                                                                        |
| `cookie_secure`             |    `nil`     | Mark cookie secure, use `nil`, `true` or `false`.                                                                                                                                                                                                                                                    |
| `cookie_priority`           |    `nil`     | Cookie priority, use `nil`, `"Low"`, `"Medium"`, or `"High"`.                                                                                                                                                                                                                                        |
| `cookie_same_site`          |   `"Lax"`    | Cookie same-site policy, use `nil`, `"Lax"`, `"Strict"`, `"None"`, or `"Default"`                                                                                                                                                                                                                    |
| `cookie_same_party`         |    `nil`     | Mark cookie with same party flag, use `nil`, `true`, or `false`.                                                                                                                                                                                                                                     |
| `cookie_partitioned`        |    `nil`     | Mark cookie with partitioned flag, use `nil`, `true`, or `false`.                                                                                                                                                                                                                                    |
| `remember`                  |   `false`    | Enable or disable persistent sessions, use `nil`, `true`, or `false`.                                                                                                                                                                                                                                |
| `remember_safety`           |  `"Medium"`  | Remember cookie key derivation complexity, use `nil`, `"None"` (fast), `"Low"`, `"Medium"`, `"High"` or `"Very High"` (slow).                                                                                                                                                                        |
| `remember_cookie_name`      | `"remember"` | Persistent session cookie name, e.g. `"remember"`.                                                                                                                                                                                                                                                   |
| `audience`                  | `"default"`  | Session audience, e.g. `"my-application"`.                                                                                                                                                                                                                                                           |
| `subject`                   |    `nil`     | Session subject, e.g. `"john.doe@example.com"`.                                                                                                                                                                                                                                                      |
| `enforce_same_subject`      |   `false`    | When set to `true`, audiences need to share the same subject. The library removes non-subject matching audience data on save.                                                                                                                                                                        |
| `stale_ttl`                 |     `10`     | When session is saved a new session is created, stale ttl specifies how long the old one can still be used, e.g. `10` (in seconds).                                                                                                                                                                  |
| `idling_timeout`            |    `900`     | Idling timeout specifies how long the session can be inactive until it is considered invalid, e.g. `900` (15 minutes) (in seconds), `0` disables the checks and touching.                                                                                                                            |
| `rolling_timeout`           |    `3600`    | Rolling timeout specifies how long the session can be used until it needs to be renewed, e.g. `3600` (an hour) (in seconds), `0` disables the checks and rolling.                                                                                                                                    |
| `absolute_timeout`          |   `86400`    | Absolute timeout limits how long the session can be renewed, until re-authentication is required, e.g. `86400` (a day) (in seconds), `0` disables the checks.                                                                                                                                        |
| `remember_rolling_timeout`  |   `604800`   | Remember timeout specifies how long the persistent session is considered valid, e.g. `604800` (a week) (in seconds), `0` disables the checks and rolling.                                                                                                                                            |
| `remember_absolute_timeout` |  `2592000`   | Remember absolute timeout limits how long the persistent session can be renewed, until re-authentication is required, e.g. `2592000` (30 days) (in seconds), `0` disables the checks.                                                                                                                |
| `hash_storage_key`          |   `false`    | Whether to hash or not the storage key. With storage key hashed it is impossible to decrypt data on server side without having a cookie too, use `nil`, `true` or `false`.                                                                                                                           |
| `hash_subject`              |   `false`    | Whether to hash or not the subject when `store_metadata` is enabled, e.g. for PII reasons.                                                                                                                                                                                                           |
| `store_metadata`            |   `false`    | Whether to also store metadata of sessions, such as collecting data of sessions for a specific audience belonging to a specific subject.                                                                                                                                                             |
| `touch_threshold`           |     `60`     | Touch threshold controls how frequently or infrequently the `session:refresh` touches the cookie, e.g. `60` (a minute) (in seconds)                                                                                                                                                                  |
| `compression_threshold`     |    `1024`    | Compression threshold controls when the data is deflated, e.g. `1024` (a kilobyte) (in bytes), `0` disables compression.                                                                                                                                                                             |
| `request_headers`           |    `nil`     | Set of headers to send to upstream, use `id`, `audience`, `subject`, `timeout`, `idling-timeout`, `rolling-timeout`, `absolute-timeout`. E.g. `{ "id", "timeout" }` will set `Session-Id` and `Session-Timeout` request headers when `set_headers` is called.                                        |
| `response_headers`          |    `nil`     | Set of headers to send to downstream, use `id`, `audience`, `subject`, `timeout`, `idling-timeout`, `rolling-timeout`, `absolute-timeout`. E.g. `{ "id", "timeout" }` will set `Session-Id` and `Session-Timeout` response headers when `set_headers` is called.                                     |
| `storage`                   |    `nil`     | Storage is responsible of storing session data, use `nil` or `"cookie"` (data is stored in cookie), `"dshm"`, `"file"`, `"memcached"`, `"mysql"`, `"postgres"`, `"redis"`, or `"shm"`, or give a name of custom module (`"custom-storage"`), or a `table` that implements session storage interface. |
| `dshm`                      |    `nil`     | Configuration for dshm storage, e.g. `{ prefix = "sessions" }` (see below)                                                                                                                                                                                                                           |
| `file`                      |    `nil`     | Configuration for file storage, e.g. `{ path = "/tmp", suffix = "session" }` (see below)                                                                                                                                                                                                             |
| `memcached`                 |    `nil`     | Configuration for memcached storage, e.g. `{ prefix = "sessions" }` (see below)                                                                                                                                                                                                                      |
| `mysql`                     |    `nil`     | Configuration for MySQL / MariaDB storage, e.g. `{ database = "sessions" }` (see below)                                                                                                                                                                                                              |
| `postgres`                  |    `nil`     | Configuration for Postgres storage, e.g. `{ database = "sessions" }` (see below)                                                                                                                                                                                                                     |
| `redis`                     |    `nil`     | Configuration for Redis / Redis Sentinel / Redis Cluster storages, e.g. `{ prefix = "sessions" }` (see below)                                                                                                                                                                                        |
| `shm`                       |    `nil`     | Configuration for shared memory storage, e.g. `{ zone = "sessions" }`                                                                                                                                                                                                                                |
| `["custom-storage"]`        |    `nil`     | custom storage (loaded with `require "custom-storage"`) configuration.                                                                                                                                                                                                                               |


## Cookie Storage Configuration

When storing data to cookie, there is no additional configuration required,
just set the `storage` to `nil` or `"cookie"`.


## DSHM Storage Configuration

With DHSM storage you can use the following settings (set the `storage` to `"dshm"`):

| Option              |    Default    | Description                                                                                  |
|---------------------|:-------------:|----------------------------------------------------------------------------------------------|
| `prefix`            |     `nil`     | The Prefix for the keys stored in DSHM.                                                      |
| `suffix`            |     `nil`     | The suffix for the keys stored in DSHM.                                                      |
| `host`              | `"127.0.0.1"` | The host to connect.                                                                         |
| `port`              |    `4321`     | The port to connect.                                                                         |
| `connect_timeout`   |     `nil`     | Controls the default timeout value used in TCP/unix-domain socket object's `connect` method. |
| `send_timeout`      |     `nil`     | Controls the default timeout value used in TCP/unix-domain socket object's `send` method.    |
| `read_timeout`      |     `nil`     | Controls the default timeout value used in TCP/unix-domain socket object's `receive` method. |
| `keepalive_timeout` |     `nil`     | Controls the default maximal idle time of the connections in the connection pool.            |
| `pool`              |     `nil`     | A custom name for the connection pool being used.                                            |
| `pool_size`         |     `nil`     | The size of the connection pool.                                                             |
| `backlog`           |     `nil`     | A queue size to use when the connection pool is full (configured with pool_size).            |
| `ssl`               |     `nil`     | Enable SSL.                                                                                  |
| `ssl_verify`        |     `nil`     | Verify server certificate.                                                                   |
| `server_name`       |     `nil`     | The server name for the new TLS extension Server Name Indication (SNI).                      |

Please refer to [ngx-distributed-shm](https://github.com/grrolland/ngx-distributed-shm) to get necessary
dependencies installed.


## File Storage Configuration

With file storage you can use the following settings (set the `storage` to `"file"`):

| Option              |     Default     | Description                                                                         |
|---------------------|:---------------:|-------------------------------------------------------------------------------------|
| `prefix`            |      `nil`      | File prefix for session file.                                                       |
| `suffix`            |      `nil`      | File suffix (or extension without `.`) for session file.                            |
| `pool`              |      `nil`      | Name of the thread pool under which file writing happens (available on Linux only). |
| `path`              | (tmp directory) | Path (or directory) under which session files are created.                          |


The implementation requires `LuaFileSystem` which you can install with LuaRocks:
```sh
❯ luarocks install LuaFileSystem
```


## Memcached Storage Configuration

With file Memcached you can use the following settings (set the `storage` to `"memcached"`):

| Option              |   Default   | Description                                                                                  |
|---------------------|:-----------:|----------------------------------------------------------------------------------------------|
| `prefix`            |    `nil`    | Prefix for the keys stored in memcached.                                                     |
| `suffix`            |    `nil`    | Suffix for the keys stored in memcached.                                                     |
| `host`              | `127.0.0.1` | The host to connect.                                                                         |
| `port`              |   `11211`   | The port to connect.                                                                         |
| `socket`            |    `nil`    | The socket file to connect to.                                                               |
| `connect_timeout`   |    `nil`    | Controls the default timeout value used in TCP/unix-domain socket object's `connect` method. |
| `send_timeout`      |    `nil`    | Controls the default timeout value used in TCP/unix-domain socket object's `send` method.    |
| `read_timeout`      |    `nil`    | Controls the default timeout value used in TCP/unix-domain socket object's `receive` method. |
| `keepalive_timeout` |    `nil`    | Controls the default maximal idle time of the connections in the connection pool.            |
| `pool`              |    `nil`    | A custom name for the connection pool being used.                                            |
| `pool_size`         |    `nil`    | The size of the connection pool.                                                             |
| `backlog`           |    `nil`    | A queue size to use when the connection pool is full (configured with pool_size).            |
| `ssl`               |   `false`   | Enable SSL                                                                                   |
| `ssl_verify`        |    `nil`    | Verify server certificate                                                                    |
| `server_name`       |    `nil`    | The server name for the new TLS extension Server Name Indication (SNI).                      |


## MySQL / MariaDB Storage Configuration

With file MySQL / MariaDB you can use the following settings (set the `storage` to `"mysql"`):

| Option              |      Default      | Description                                                                                  |
|---------------------|:-----------------:|----------------------------------------------------------------------------------------------|
| `host`              |   `"127.0.0.1"`   | The host to connect.                                                                         |
| `port`              |      `3306`       | The port to connect.                                                                         |
| `socket`            |       `nil`       | The socket file to connect to.                                                               |
| `username`          |       `nil`       | The database username to authenticate.                                                       |
| `password`          |       `nil`       | Password for authentication, may be required depending on server configuration.              |
| `charset`           |     `"ascii"`     | The character set used on the MySQL connection.                                              |
| `database`          |       `nil`       | The database name to connect.                                                                |
| `table_name`        |   `"sessions"`    | Name of database table to which to store session data.                                       |
| `table_name_meta`   | `"sessions_meta"` | Name of database meta data table to which to store session meta data.                        |
| `max_packet_size`   |     `1048576`     | The upper limit for the reply packets sent from the MySQL server (in bytes).                 |
| `connect_timeout`   |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `connect` method. |
| `send_timeout`      |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `send` method.    |
| `read_timeout`      |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `receive` method. |
| `keepalive_timeout` |       `nil`       | Controls the default maximal idle time of the connections in the connection pool.            |
| `pool`              |       `nil`       | A custom name for the connection pool being used.                                            |
| `pool_size`         |       `nil`       | The size of the connection pool.                                                             |
| `backlog`           |       `nil`       | A queue size to use when the connection pool is full (configured with pool_size).            |
| `ssl`               |      `false`      | Enable SSL.                                                                                  |
| `ssl_verify`        |       `nil`       | Verify server certificate.                                                                   |

You also need to create following tables in your database:

```sql
--
-- Database table that stores session data.
--
CREATE TABLE IF NOT EXISTS sessions (
  sid  CHAR(43) PRIMARY KEY,
  name VARCHAR(255),
  data MEDIUMTEXT,
  exp  DATETIME,
  INDEX (exp)
) CHARACTER SET ascii;

--
-- Sessions metadata table.
--
-- This is only needed if you want to store session metadata.
--
CREATE TABLE IF NOT EXISTS sessions_meta (
  aud VARCHAR(255),
  sub VARCHAR(255),
  sid CHAR(43),
  PRIMARY KEY (aud, sub, sid),
  CONSTRAINT FOREIGN KEY (sid) REFERENCES sessions(sid) ON DELETE CASCADE ON UPDATE CASCADE
) CHARACTER SET ascii;
```


## Postgres Configuration

With file Postgres you can use the following settings (set the `storage` to `"postgres"`):

| Option              |      Default      | Description                                                                                               |
|---------------------|:-----------------:|-----------------------------------------------------------------------------------------------------------|
| `host`              |   `"127.0.0.1"`   | The host to connect.                                                                                      |
| `port`              |      `5432`       | The port to connect.                                                                                      |
| `application`       |      `5432`       | Set the name of the connection as displayed in pg_stat_activity (defaults to `"pgmoon"`).                 |
| `username`          |   `"postgres"`    | The database username to authenticate.                                                                    |
| `password`          |       `nil`       | Password for authentication, may be required depending on server configuration.                           |
| `database`          |       `nil`       | The database name to connect.                                                                             |
| `table_name`        |   `"sessions"`    | Name of database table to which to store session data (can be `database schema` prefixed).                |
| `table_name_meta`   | `"sessions_meta"` | Name of database meta data table to which to store session meta data (can be `database schema` prefixed). |
| `connect_timeout`   |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `connect` method.              |
| `send_timeout`      |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `send` method.                 |
| `read_timeout`      |       `nil`       | Controls the default timeout value used in TCP/unix-domain socket object's `receive` method.              |
| `keepalive_timeout` |       `nil`       | Controls the default maximal idle time of the connections in the connection pool.                         |
| `pool`              |       `nil`       | A custom name for the connection pool being used.                                                         |
| `pool_size`         |       `nil`       | The size of the connection pool.                                                                          |
| `backlog`           |       `nil`       | A queue size to use when the connection pool is full (configured with pool_size).                         |
| `ssl`               |      `false`      | Enable SSL.                                                                                               |
| `ssl_verify`        |       `nil`       | Verify server certificate.                                                                                |
| `ssl_required`      |       `nil`       | Abort the connection if the server does not support SSL connections.                                      |

You also need to create following tables in your database:

```sql
--
-- Database table that stores session data.
--
CREATE TABLE IF NOT EXISTS sessions (
  sid  TEXT PRIMARY KEY,
  name TEXT,
  data TEXT,
  exp  TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ON sessions (exp);

--
-- Sessions metadata table.
--
-- This is only needed if you want to store session metadata.
--
CREATE TABLE IF NOT EXISTS sessions_meta (
  aud TEXT,
  sub TEXT,
  sid TEXT REFERENCES sessions (sid) ON DELETE CASCADE ON UPDATE CASCADE,
  PRIMARY KEY (aud, sub, sid)
);
```

The implementation requires `pgmoon` which you can install with LuaRocks:
```sh
❯ luarocks install pgmoon
```


## Redis Configuration

The session library supports single Redis, Redis Sentinel, and Redis Cluster
connections. Common configuration settings among them all:

| Option              | Default | Description                                                                                  |
|---------------------|:-------:|----------------------------------------------------------------------------------------------|
| `prefix`            |  `nil`  | Prefix for the keys stored in Redis.                                                         |
| `suffix`            |  `nil`  | Suffix for the keys stored in Redis.                                                         |
| `username`          |  `nil`  | The database username to authenticate.                                                       |
| `password`          |  `nil`  | Password for authentication.                                                                 |
| `connect_timeout`   |  `nil`  | Controls the default timeout value used in TCP/unix-domain socket object's `connect` method. |
| `send_timeout`      |  `nil`  | Controls the default timeout value used in TCP/unix-domain socket object's `send` method.    |
| `read_timeout`      |  `nil`  | Controls the default timeout value used in TCP/unix-domain socket object's `receive` method. |
| `keepalive_timeout` |  `nil`  | Controls the default maximal idle time of the connections in the connection pool.            |
| `pool`              |  `nil`  | A custom name for the connection pool being used.                                            |
| `pool_size`         |  `nil`  | The size of the connection pool.                                                             |
| `backlog`           |  `nil`  | A queue size to use when the connection pool is full (configured with pool_size).            |
| `ssl`               | `false` | Enable SSL                                                                                   |
| `ssl_verify`        |  `nil`  | Verify server certificate                                                                    |
| `server_name`       |  `nil`  | The server name for the new TLS extension Server Name Indication (SNI).                      |

The `single redis` implementation is selected when you don't pass either `sentinels` or `nodes`,
which would lead to selecting `sentinel` or `cluster` implementation.

### Single Redis Configuration

Single Redis has following additional configuration options (set the `storage` to `"redis"`):

| Option      |     Default     | Description                    |
|-------------|:---------------:|--------------------------------|
| `host`      |  `"127.0.0.1"`  | The host to connect.           |
| `port`      |     `6379`      | The port to connect.           |
| `socket`    |      `nil`      | The socket file to connect to. |
| `database`  |      `nil`      | The database to connect.       |


### Redis Sentinels Configuration

Redis Sentinel has following additional configuration options (set the `storage` to `"redis"`
and configure the `sentinels`):

| Option              | Default  | Description                    |
|---------------------|:--------:|--------------------------------|
| `master`            |  `nil`   | Name of master.                |
| `role`              |  `nil`   | `"master"` or `"slave"`.       |
| `socket`            |  `nil`   | The socket file to connect to. |
| `sentinels`         |  `nil`   | Redis Sentinels.               |
| `sentinel_username` |  `nil`   | Optional sentinel username.    |
| `sentinel_password` |  `nil`   | Optional sentinel password.    |
| `database`          |  `nil`   | The database to connect.       |

The `sentinels` is an array of Sentinel records:

| Option | Default | Description          |
|--------|:-------:|----------------------|
| `host` |  `nil`  | The host to connect. |
| `port` |  `nil`  | The port to connect. |

The `sentinel` implementation is selected when you pass `sentinels` as part of `redis`
configuration (and do not pass `nodes`, which would select `cluster` implementation).

The implementation requires `lua-resty-redis-connector` which you can install with LuaRocks:
```sh
❯ luarocks install lua-resty-redis-connector
```


### Redis Cluster Configuration

Redis Cluster has following additional configuration options (set the `storage` to `"redis"`
and configure the `nodes`):

| Option                    | Default | Description                                            |
|---------------------------|:-------:|--------------------------------------------------------|
| `name`                    |  `nil`  | Redis cluster name.                                    |
| `nodes`                   |  `nil`  | Redis cluster nodes.                                   |
| `lock_zone`               |  `nil`  | Shared dictionary name for locks.                      |
| `lock_prefix`             |  `nil`  | Shared dictionary name prefix for lock.                |
| `max_redirections`        |  `nil`  | Maximum retry attempts for redirection.                |
| `max_connection_attempts` |  `nil`  | Maximum retry attempts for connection.                 |
| `max_connection_timeout`  |  `nil`  | Maximum connection timeout in total among the retries. |

The `nodes` is an array of Cluster node records:

| Option |    Default    | Description                |
|--------|:-------------:|----------------------------|
| `ip`   | `"127.0.0.1"` | The IP address to connect. |
| `port` |    `6379`     | The port to connect.       |

The `cluster` implementation is selected when you pass `nodes` as part of `redis`
configuration.

For `cluster` to work properly, you need to configure `lock_zone`, so also add this
to your Nginx configuration:

```nginx
lua_shared_dict redis_cluster_locks 100k;
```

And set the `lock_zone` to `"redis_cluster_locks"`

The implementation requires `resty-redis-cluster` or `kong-redis-cluster` which you can install with LuaRocks:
```sh
❯ luarocks install resty-redis-cluster
# or
❯ luarocks install kong-redis-cluster
```


## SHM Configuration

With SHM storage you can use the following settings (set the `storage` to `"shm"`):

| Option   |   Default    | Description                        |
|----------|:------------:|------------------------------------|
| `prefix` |    `nil`     | Prefix for the keys stored in SHM. |
| `suffix` |    `nil`     | Suffix for the keys stored in SHM. |
| `zone`   | `"sessions"` | A name of shared memory zone.      |

You will also need to create a shared dictionary `zone` in Nginx:

```nginx
lua_shared_dict sessions 10m;
```

*Note:* you may need to adjust the size of shared memory zone according to your needs.


# API

LDoc generated API docs can also be viewed at [bungle.github.io/lua-resty-session](https://bungle.github.io/lua-resty-session/).


## Initialization

### session.init

**syntax:** *session.init(configuration)*

Initialize the session library.

This function can be called on `init` or `init_worker` phases on OpenResty
to set global default configuration to all session instances created by this
library.

```lua
require "resty.session".init({
  audience = "my-application",
  storage = "redis",
  redis = {
    username = "session",
    password = "storage",
  },
})
```

See [configuration](#configuration) for possible configuration settings.


## Constructors

### session.new

**syntax:** *session = session.new(configuration)*

Creates a new session instance.

```lua
local session = require "resty.session".new()
-- OR
local session = require "resty.session".new({
  audience = "my-application",
})
```

See [configuration](#configuration) for possible configuration settings.


## Helpers

### session.open

**syntax:** *session, err, exists = session.open(configuration)*

This can be used to open a session, and it will either return an existing
session or a new session. The `exists` (a boolean) return parameters tells whether
it was existing or new session that was returned. The `err` (a string) contains
a message of why opening might have failed (the function will still return
`session` too).

```lua
local session = require "resty.session".open()
-- OR
local session, err, exists = require "resty.session".open({
  audience = "my-application",
})
```

See [configuration](#configuration) for possible configuration settings.


### session.start

**syntax:** *session, err, exists, refreshed = session.start(configuration)*

This can be used to start a session, and it will either return an existing
session or a new session. In case there is an existing session, the
session will be refreshed as well (as needed). The `exists` (a boolean)
return parameters tells whether it was existing or new session that was
returned. The `refreshed` (a boolean) tells whether the call to `refresh`
was succesful.  The `err` (a string) contains a message of why opening or
refreshing might have failed (the function will still return `session` too).

```lua
local session = require "resty.session".start()
-- OR
local session, err, exists, refreshed = require "resty.session".start({
  audience = "my-application",
})
```

See [configuration](#configuration) for possible configuration settings.


### session.logout

**syntax:** *ok, err, exists, logged_out = session.logout(configuration)*

It logouts from a specific audience.

A single session cookie may be shared between multiple audiences
(or applications), thus there is a need to be able to logout from
just a single audience while keeping the session for the other
audiences. The `exists` (a boolean) return parameters tells whether
session existed. The `logged_out` (a boolean) return parameter signals
if the session existed and was also logged out. The `err` (a string)
contains a reason why session didn't exists or why the logout failed.
The `ok` (truthy) will be `true` when session existed and was
successfully logged out.

When there is only a single audience, then this can be considered
equal to `session.destroy`.

When the last audience is logged out, the cookie will be destroyed
as well and invalidated on a client.

```lua
require "resty.session".logout()
-- OR
local ok, err, exists, logged_out = require "resty.session".logout({
  audience = "my-application",
})
```


See [configuration](#configuration) for possible configuration settings.


### session.destroy

**syntax:** *ok, err, exists, destroyed = session.destroy(configuration)*

It destroys the whole session and clears the cookies.

A single session cookie may be shared between multiple audiences
(or applications), thus there is a need to be able to logout from
just a single audience while keeping the session for the other
audiences. The `exists` (a boolean) return parameters tells whether
session existed. The `destroyed` (a boolean) return parameter signals
if the session existed and was also destroyed out. The `err` (a string)
contains a reason why session didn't exists or why the logout failed.
The `ok` (truthy) will be `true` when session existed and was
successfully logged out.

```lua
require "resty.session".destroy()
-- OR
local ok, err, exists, destroyed = require "resty.session".destroy({
  cookie_name = "auth",
})
```

See [configuration](#configuration) for possible configuration settings.


## Instance Methods

### session:open

**syntax:** *ok, err = session:open()*

This can be used to open a session. It returns `true` when
session was opened and validated. Otherwise, it returns `nil` and
an error message.

```lua
local session = require "resty.session".new()
local ok, err = session:open()
if ok then
  -- session exists
  
else
  -- session did not exists or was invalid
end
```


### session:save

**syntax:** *ok, err = session:save()*

Saves the session data and issues a new session cookie with a new session id.
When `remember` is enabled, it will also issue a new persistent cookie and
possibly save the data in backend store. It returns `true` when session was saved.
Otherwise, it returns `nil` and an error message.

```lua
local session = require "resty.session".new()
session:set_subject("john")
local ok, err = session:save()
if not ok then
  -- error when saving session
end
```


### session:touch

**syntax:** *ok, err = session:touch()*

Updates idling offset of the session by sending an updated session cookie.
It only sends the client cookie and never calls any backend session store
APIs. Normally the `session:refresh` is used to call this indirectly. In
error case it returns `nil` and an error message, otherwise `true`.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  ok, err = session:touch()
end
```


### session:refresh

**syntax:** *ok, err = session:refresh()*

Either saves the session (creating a new session id) or touches the session
depending on whether the rolling timeout is getting closer, which means
by default when 3/4 of rolling timeout is spent, that is 45 minutes with default
rolling timeout of an hour. The touch has a threshold, by default one minute,
so it may be skipped in some cases (you can call `session:touch()` to force it).
In error case it returns `nil` and an error message, otherwise `true`.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local ok, err = session:refresh()
end
```

The above code looks a bit like `session.start()` helper.


### session:logout

**syntax:** *ok, err = session:logout()*

Logout either destroys the session or just clears the data for the current audience,
and saves it (logging out from the current audience). In error case it returns `nil`
and an error message, otherwise `true`.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local ok, err = session:logout()
end
```


### session:destroy

**syntax:** *ok, err = session:destroy()*

Destroy the session and clear the cookies. In error case it returns `nil`
and an error message, otherwise `true`.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local ok, err = session:destroy()
end
```


### session:close

**syntax:** *session:close()*

Just closes the session instance so that it cannot be used anymore.

```lua
local session = require "resty.session".new()
session:set_subject("john")
local ok, err = session:save()
if not ok then
  -- error when saving session
end
session:close()
```


### session:set_data

**syntax:** *session:set_data(data)*

Set session data. The `data` needs to be a `table`.

```lua
local session, err, exists = require "resty.session".open()
if not exists then
   session:set_data({
     cart = {},
   })
  session:save()
end
```


### session:get_data

**syntax:** *data = session:get_data()*

Get session data.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local data = session:get_data()
  ngx.req.set_header("Authorization", "Bearer " .. data.access_token)
end
```


### session:set

**syntax:** *session:set(key, value)*

Set a value in session.

```lua
local session, err, exists = require "resty.session".open()
if not exists then
  session:set("access-token", "eyJ...")
  session:save()
end
```


### session:get

**syntax:** *value = session:get(key)*

Get a value from session.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local access_token = session:get("access-token")
  ngx.req.set_header("Authorization", "Bearer " .. access_token)
end
```

### session:set_audience

**syntax:** *session:set_audience(audience)*

Set session audience.

```lua
local session = require "resty.session".new()
session.set_audience("my-service")
```


### session:get_audience

**syntax:** *audience = session:get_audience()*

Set session subject.


### session:set_subject

**syntax:** *session:set_subject(subject)*

Set session audience.

```lua
local session = require "resty.session".new()
session.set_subject("john@doe.com")
```


### session:get_subject

**syntax:** *subject = session:get_subject()*

Get session subject.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local subject = session.get_subject()
end
```


### session:get_property

**syntax:** *value = session:get_property(name)*

Get session property. Possible property names:

- `"id"`: 43 bytes session id (same as nonce, but base64 url-encoded)
- `"nonce"`: 32 bytes nonce (same as session id but in raw bytes)
- `"audience"`: Current session audience
- `"subject"`: Current session subject
- `"timeout"`: Closest timeout (in seconds) (what's left of it)
- `"idling-timeout`"`: Session idling timeout (in seconds) (what's left of it)
- `"rolling-timeout`"`: Session rolling timeout (in seconds) (what's left of it)
- `"absolute-timeout`"`: Session absolute timeout (in seconds) (what's left of it)

*Note:* the returned value may be `nil`.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local timeout = session.get_property("timeout")
end
```


### session:set_remember

**syntax:** *session:set_remember(value)*

Set persistent sessions on/off.

In many login forms user is given an option for "remember me".
You can call this function based on what user selected.

```lua
local session = require "resty.session".new()
if ngx.var.args.remember then
  session:set_remember(true)
end
session:set_subject(ngx.var.args.username)
session:save()
```


### session:get_remember

**syntax:** *remember = session:get_remember()*

Get state of persistent sessions.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local remember = session.get_remember()
end
```


### session:clear_request_cookie

**syntax:** *session:clear_request_cookie()*

Modifies the request headers by removing the session related
cookies. This is useful when you use the session library on
a proxy server and don't want the session cookies to be forwarded
to the upstream service.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  session:clear_request_cookie()
end
```


### session:set_headers

**syntax:** *session:set_headers(arg1, arg2, ...)*

Sets request and response headers based on configuration.

```lua
local session, err, exists = require "resty.session".open({
  request_headers = { "audience", "subject", "id" },
  response_headers = { "timeout", "idling-timeout", "rolling-timeout", "absolute-timeout" },
})
if exists then
  session:set_headers()
end
```

When called without arguments it will set request headers configured with `request_headers`
and response headers configured with `response_headers`.

See [configuration](#configuration) for possible header names.


### session:set_request_headers

**syntax:** *session:set_request_headers(arg1, arg2, ...)*

Set request headers.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  session:set_request_headers("audience", "subject", "id")
end
```

When called without arguments it will set request headers configured with `request_headers`.

See [configuration](#configuration) for possible header names.


### session:set_response_headers

**syntax:** *session:set_response_headers(arg1, arg2, ...)*

Set request headers.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  session:set_response_headers("timeout", "idling-timeout", "rolling-timeout", "absolute-timeout")
end
```

When called without arguments it will set request headers configured with `response_headers`.

See [configuration](#configuration) for possible header names.


### session.info:set

**syntax:** *session.info:set(key, value)*

Set a value in session information store. Session information store
may be used in scenarios when you want to store data on server side
storage, but do not want to create a new session and send a new
session cookie. The information store data is not considered when
checking authentication tag or message authentication code. Thus if
you want to use this for data that needs to be encrypted, you need
to encrypt value before passing it to thus function.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  session.info:set("last-access", ngx.now())
  session.info:save()
end
```

With cookie storage this still works, but it is then almost the same as
`session:set`.


### session.info:get

**syntax:** *value = session.info:get(key)*

Get a value from session information store.

```lua
local session, err, exists = require "resty.session".open()
if exists then
  local last_access = session.info:get("last-access")
end
```


### session.info:save

**syntax:** *value = session.info:save()*

Save information. Only updates backend storage. Does not send a new cookie (except with cookie storage).

```lua
local session = require "resty.session".new()
session.info:set("last-access", ngx.now())
local ok, err = session.info:save()
```


# Cookie Format

```
[ HEADER -------------------------------------------------------------------------------------]
[ Type || Flags || SID || Created at || Rolling Offset || Size || Tag || Idling Offset || Mac ]
[ 1B   || 2B    || 32B || 5B         || 4B             || 3B   || 16B || 3B            || 16B ]
```

and

```
[ PAYLOAD --]
[ Data  *B  ]   
```

Both the `HEADER` and `PAYLOAD` are base64 url-encoded before putting in a `Set-Cookie` header.
When using a server side storage, the `PAYLOAD` is not put in the cookie. With cookie storage
the base64 url-encoded header is concatenated with base64 url-encoded payload.

The `HEADER` is fixed size 82 bytes binary or 110 bytes in base64 url-encoded form.

Header fields explained:

- Type: number `1` binary packed in a single little endian byte (currently the only supported `type`).
- Flags: binary packed flags (short) in a two byte little endian form.
- SID: `32` bytes of crypto random data (Session ID).
- Created at: binary packed secs from epoch in a little endian form, truncated to 5 bytes.
- Rolling Offset: binary packed secs from creation time in a little endian form (integer). 
- Size: binary packed data size (short) in a two byte little endian form.
- Tag: `16` bytes of authentication tag from AES-256-GCM encryption of the data.
- Idling Offset: binary packed secs from creation time + rolling offset in a little endian form, truncated to 3 bytes.
- Mac: `16` bytes message authentication code of the header.


# Data Encryption

1. Initial keying material (IKM):
   1. derive IKM from `secret` by hashing `secret` with SHA-256, or
   2. use 32 byte IKM when passed to library with `ikm`
2. Generate 32 bytes of crypto random session id (`sid`) 
3. Derive 32 byte encryption key and 12 byte initialization vector with HKDF using SHA-256 (on FIPS-mode it uses PBKDF2 with SHA-256 instead)
   1. Use HKDF extract to derive a new key from `ikm` to get `key` (this step can be done just once per `ikm`):
      - output length: `32`
      - digest: `"sha256"`
      - key: `<ikm>`
      - mode: `extract only`
      - info: `""`
      - salt: `""`
   2. Use HKDF expand to derive `44` bytes of `output`:
      - output length: `44`
      - digest: `"sha256"`
      - key: `<key>`
      - mode: `expand only`
      - info: `"encryption:<sid>"`
      - salt: `""`
   3. The first 32 bytes of `output` are the encryption key (`aes-key`), and the last 12 bytes are the initialization vector (`iv`)
4. Encrypt `plaintext` (JSON encoded and optionally deflated) using AES-256-GCM to get `ciphertext` and `tag`
   1. cipher: `"aes-256-gcm"`
   2. key: `<aes-key>`
   3. iv: `<iv>`
   4. plaintext: `<plaintext>`
   5. aad: use the first 47 bytes of `header` as `aad`, that includes:
      1. Type
      2. Flags
      3. Session ID
      4. Creation Time
      5. Rolling Offset
      6. Data Size

There is a variation for `remember` cookies on step 3, where we may use `PBKDF2`
instead of `HKDF`, depending  on `remember_safety` setting (we also use it in FIPS-mode).
The `PBKDF2` settings:

- output length: `44`
- digest: `"sha256"`
- password: `<key>`
- salt: `"encryption:<sid>"`
- iterations: `<1000|10000|100000|1000000>`

Iteration counts are based on `remember_safety` setting (`"Low"`, `"Medium"`, `"High"`, `"Very High"`),
if `remember_safety` is set to `"None"`, we will use the HDKF as above.


# Cookie Header Authentication

1. Derive 32 byte authentication key (`mac_key`) with HKDF using SHA-256  (on FIPS-mode it uses PBKDF2 with SHA-256 instead):
    1. Use HKDF extract to derive a new key from `ikm` to get `key` (this step can be done just once per `ikm` and reused with encryption key generation):
        - output length: `32`
        - digest: `"sha256"`
        - key: `<ikm>`
        - mode: `extract only`
        - info: `""`
        - salt: `""`
    2. Use HKDF expand to derive `32` bytes of `mac-key`:
        - output length: `32`
        - digest: `"sha256"`
        - key: `<key>`
        - mode: `expand only`
        - info: `"authentication:<sid>"`
        - salt: `""`
2. Calculate message authentication code using HMAC-SHA256:
   -  digest: `"sha256"`
   -  key: `<mac-key>`
   -  message: use the first 66 bytes of `header`, that includes:
      1. Type
      2. Flags
      3. Session ID
      4. Creation Time
      5. Rolling Offset
      6. Data Size
      7. Tag
      8. Idling Offset


# Custom Storage Interface

If you want to implement custom storage, you need to implement following interface:

```lua
---
-- <custom> backend for session library
--
-- @module <custom>


---
-- Storage
-- @section instance


local metatable = {}


metatable.__index = metatable


function metatable.__newindex()
  error("attempt to update a read-only table", 2)
end


---
-- Store session data.
--
-- @function instance:set
-- @tparam string name cookie name
-- @tparam string key session key
-- @tparam string value session value
-- @tparam number ttl session ttl
-- @tparam number current_time current time
-- @tparam[opt] string old_key old session id
-- @tparam string stale_ttl stale ttl
-- @tparam[opt] table metadata table of metadata
-- @tparam boolean remember whether storing persistent session or not
-- @treturn true|nil ok
-- @treturn string error message
function metatable:set(name, key, value, ttl, current_time, old_key, stale_ttl, metadata, remember)
  -- NYI
end


---
-- Retrieve session data.
--
-- @function instance:get
-- @tparam string name cookie name
-- @tparam string key session key
-- @treturn string|nil session data
-- @treturn string error message
function metatable:get(name, key)
  -- NYI
end


---
-- Delete session data.
--
-- @function instance:delete
-- @tparam string name cookie name
-- @tparam string key session key
-- @tparam[opt] table metadata  session meta data
-- @treturn boolean|nil session data
-- @treturn string error message
function metatable:delete(name, key, current_time, metadata)
  -- NYI
end


local storage = {}


---
-- Constructors
-- @section constructors


---
-- Configuration
-- @section configuration


---
-- <custom> storage backend configuration
-- @field <field-name> TBD
-- @table configuration


---
-- Create a <custom> storage.
--
-- This creates a new shared memory storage instance.
--
-- @function module.new
-- @tparam[opt]  table   configuration  <custom> storage @{configuration}
-- @treturn      table                  <custom> storage instance
function storage.new(configuration)
  -- NYI
  -- return setmetatable({}, metatable)
end


return storage
```

Please check the existing implementations for the defails. And please
make a pull-request so that we can integrate it directly to library
for other users as well.


# License

`lua-resty-session` uses two clause BSD license.

```
Copyright (c) 2014 – 2023 Aapo Talvensaari, 2022 – 2023 Samuele Illuminati
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
