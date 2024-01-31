# ngx_brotli

Brotli is a generic-purpose lossless compression algorithm that compresses data
using a combination of a modern variant of the LZ77 algorithm, Huffman coding
and 2nd order context modeling, with a compression ratio comparable to the best
currently available general-purpose compression methods. It is similar in speed
with deflate but offers more dense compression.

ngx_brotli is a set of two nginx modules:

- ngx_brotli filter module - used to compress responses on-the-fly,
- ngx_brotli static module - used to serve pre-compressed files.

[![TravisCI Build Status](https://travis-ci.org/google/ngx_brotli.svg?branch=master)](https://travis-ci.org/google/ngx_brotli)

## Table of Contents

- [Status](#status)
- [Installation](#installation)
- [Configuration directives](#configuration-directives)
  - [`brotli_static`](#brotli_static)
  - [`brotli`](#brotli)
  - [`brotli_types`](#brotli_types)
  - [`brotli_buffers`](#brotli_buffers)
  - [`brotli_comp_level`](#brotli_comp_level)
  - [`brotli_window`](#brotli_window)
  - [`brotli_min_length`](#brotli_min_length)
- [Variables](#variables)
  - [`$brotli_ratio`](#brotli_ratio)
- [Sample configuration](#sample-configuration)
- [Contributing](#contributing)
- [License](#license)

## Status

Both Brotli library and nginx module are under active development.

## Installation

### Dynamically loaded

    $ cd nginx-1.x.x
    $ ./configure --with-compat --add-dynamic-module=/path/to/ngx_brotli
    $ make modules

You will need to use **exactly** the same `./configure` arguments as your Nginx configuration and append `--with-compat --add-dynamic-module=/path/to/ngx_brotli` to the end, otherwise you will get a "module is not binary compatible" error on startup. You can run `nginx -V` to get the configuration arguments for your Nginx installation.

`make modules` will result in `ngx_http_brotli_filter_module.so` and `ngx_http_brotli_static_module.so` in the `objs` directory. Copy these to `/usr/lib/nginx/modules/` then add the `load_module` directives to `nginx.conf` (above the http block):
```nginx
load_module modules/ngx_http_brotli_filter_module.so;
load_module modules/ngx_http_brotli_static_module.so;
```

### Statically compiled

    $ cd nginx-1.x.x
    $ ./configure --add-module=/path/to/ngx_brotli
    $ make && make install
  
This will compile the module directly into Nginx.

## Configuration directives

### `brotli_static`

- **syntax**: `brotli_static on|off|always`
- **default**: `off`
- **context**: `http`, `server`, `location`

Enables or disables checking of the existence of pre-compressed files with`.br`
extension. With the `always` value, pre-compressed file is used in all cases,
without checking if the client supports it.

### `brotli`

- **syntax**: `brotli on|off`
- **default**: `off`
- **context**: `http`, `server`, `location`, `if`

Enables or disables on-the-fly compression of responses.

### `brotli_types`

- **syntax**: `brotli_types <mime_type> [..]`
- **default**: `text/html`
- **context**: `http`, `server`, `location`

Enables on-the-fly compression of responses for the specified MIME types
in addition to `text/html`. The special value `*` matches any MIME type.
Responses with the `text/html` MIME type are always compressed.

### `brotli_buffers`

- **syntax**: `brotli_buffers <number> <size>`
- **default**: `32 4k|16 8k`
- **context**: `http`, `server`, `location`

**Deprecated**, ignored.

### `brotli_comp_level`

- **syntax**: `brotli_comp_level <level>`
- **default**: `6`
- **context**: `http`, `server`, `location`

Sets on-the-fly compression Brotli quality (compression) `level`.
Acceptable values are in the range from `0` to `11`.

### `brotli_window`

- **syntax**: `brotli_window <size>`
- **default**: `512k`
- **context**: `http`, `server`, `location`

Sets Brotli window `size`. Acceptable values are `1k`, `2k`, `4k`, `8k`, `16k`,
`32k`, `64k`, `128k`, `256k`, `512k`, `1m`, `2m`, `4m`, `8m` and `16m`.

### `brotli_min_length`

- **syntax**: `brotli_min_length <length>`
- **default**: `20`
- **context**: `http`, `server`, `location`

Sets the minimum `length` of a response that will be compressed.
The length is determined only from the `Content-Length` response header field.

## Variables

### `$brotli_ratio`

Achieved compression ratio, computed as the ratio between the original
and compressed response sizes.

## Sample configuration

```
brotli on;
brotli_comp_level 6;
brotli_static on;
brotli_types application/atom+xml application/javascript application/json application/rss+xml
             application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype
             application/x-font-ttf application/x-javascript application/xhtml+xml application/xml
             font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon
             image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml;
```

## Contributing

See [Contributing](CONTRIBUTING.md).

## License

    Copyright (C) 2002-2015 Igor Sysoev
    Copyright (C) 2011-2015 Nginx, Inc.
    Copyright (C) 2015 Google Inc.
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met:
    1. Redistributions of source code must retain the above copyright
       notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
    FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
    OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
    HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
    OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
    SUCH DAMAGE.
