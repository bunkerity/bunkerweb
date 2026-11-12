# Name
zstd-nginx-module - Nginx module for the [Zstandard compression](https://facebook.github.io/zstd/).

# Table of Contents

* [Name](#name)
* [Status](#status)
* [Synopsis](#synopsis)
* [Installation](#installation)
* [Directives](#directives)
  * [ngx_http_zstd_filter_module](#ngx_http_zstd_filter_module)
    * [zstd_dict_file](#zstd_dict_file)
    * [zstd](#zstd)
    * [zstd_comp_level](#zstd_comp_level)
    * [zstd_min_length](#zstd_min_length)
    * [zstd_types](#zstd_types)
    * [zstd_buffers](#zstd_buffers)
  * [ngx_http_zstd_static_module](#ngx_http_zstd_static_module)
    * [zstd_static](#zstd_static)
* [Variables](#variables)
  * [ngx_http_zstd_filter_module](#ngx_http_zstd_filter_module)
    * [$zstd_ratio](#$zstd_ratio)
* [Author](#author)

# Status

Actively maintained by [GetPageSpeed](https://www.getpagespeed.com/). This repository continues
the original [tokers/zstd-nginx-module](https://github.com/tokers/zstd-nginx-module) by Alex Zhang,
which has not seen a release since 2023. It carries HTTP correctness fixes, memory-management
fixes and an RFC 9110 compliant `Accept-Encoding` parser on top of that base, plus a test suite
and static-analysis CI.

Issues and PRs are welcome if you encounter any problems.

Prebuilt packages for RHEL/CentOS/Rocky/Alma, Fedora, Amazon Linux, SLES, Debian and Ubuntu are
available as `nginx-module-zstd` from
[GetPageSpeed extras](https://nginx-extras.getpagespeed.com/modules/zstd/).

# Synopsis

```nginx

# specify the dictionary
zstd_dict_file /path/to/dict;

server {
    listen 127.0.0.1:8080;
    server_name localhost;

    location / {
        # enable zstd compression
        zstd on;
        zstd_min_length 256; # no less than 256 bytes
        zstd_comp_level 3; # set the level to 3

        proxy_pass http://foo.com;
    }
}

server {
    listen 127.0.0.1:8081;
    server_name localhost;

    location / {
        zstd_static on;
        root html;
    }
}
```

# Installation

To use these modules, configure your nginx branch with `--add-module=/path/to/zstd-nginx-module`.

* You can set `ZSTD_INC` and `ZSTD_LIB` to the directories containing `zstd.h` and the zstd libraries. A custom shared-library path is also recorded as an RPATH.
* Dynamic nginx modules prefer the shared zstd library so they do not embed a non-PIC static archive. Static nginx builds prefer the static library.
* The system zstd library is used when `ZSTD_INC` and `ZSTD_LIB` are not specified.
* Both `ngx_http_zstd_static_module` and `ngx_http_zstd_filter_module` will be configured.

# Directives

## ngx_http_zstd_filter_module

The `ngx_http_zstd_filter_module` module is a filter that compresses responses using the _"zstd"_ method. This often helps to reduce the size of transmitted data by half or even more.

### zstd_dict_file

**Syntax:** *zstd_dict_file /path/to/dict;*  
**Default:** *-*  
**Context:** *http*  

Specifies the external dictionary.

**WARNING:** Be careful! The content-coding registration only specifies a means to signal the use of the zstd format, and does not additionally specify any mechanism for advertising/negotiating/synchronizing the use of a specific dictionary between client and server. Use the `zstd_dict_file` only if you can insure that both ends _(server and client)_ are capable of using the same dictionary (e.g. advertise with a HTTP header). See https://github.com/tokers/zstd-nginx-module/issues/2 for the details.

### zstd

**Syntax:** *zstd on | off;*  
**Default:** *zstd off;*  
**Context:** *http, server, location, if in location*

Enables or disables zstd compression for response.

### zstd_comp_level

**Syntax:** *zstd_comp_level level;*  
**Default:** *zstd_comp_level 1;*  
**Context:** *http, server, location*

Sets a zstd compression level of a response. Acceptable values are in the range from 1 to `ZSTD_maxCLevel()`.

### zstd_min_length

**Syntax:** *zstd_min_length length;*  
**Default:** *zstd_min_length 20;*  
**Context:** *http, server, location*

Sets the minimum length of a response that will be compressed by zstd. The length is determined only from the `Content-Length` response header field.

### zstd_types

**Syntax:** *zstd_types mime-type ...;*  
**Default:** *zstd_types text/html application/wasm text/wgsl;*  
**Context:** *http, server, location*

Enables zstd of responses for the specified MIME types in addition to `text/html`. The special value `*` matches any MIME type.

`application/wasm` and `text/wgsl` are compressed by default: both are text-like formats served under a non-text media type, so they compress well but are easy to overlook. Specifying `zstd_types` explicitly replaces the defaults other than `text/html`, which is always included.

### zstd_buffers

**Syntax:** *zstd_buffers number size;*  
**Default:** *zstd_buffers 32 4k | 16 8k;*  
**Context:** *http, server, location*

Sets the number and size of buffers used to compress a response. By default the buffer size is equal to one memory page. This is either 4K or 8K, depending on a platform.

## ngx_http_zstd_static_module

The `ngx_http_zstd_static_module` module allows sending precompressed files with the `.zst` filename extension instead of regular files.

### zstd_static

**Syntax:**	*zstd_static on | off | always;*  
**Default:** *zstd_static off;*  
**Context:** *http, server, location*  

Enables ("on") or disables ("off") checking the existence of precompressed files. When a `.zst` variant exists, negotiated responses emit `Vary: Accept-Encoding` independently of `gzip_vary`.

With the _"always"_ value, "zstd" file is used in all cases, without checking if the client supports it.

When no `.zst` file exists the request is declined unchanged, so `gzip_static` and the `gzip` filter still apply as they normally would.


# Variables

## ngx_http_zstd_filter_module

### $zstd_ratio

Achieved compression ratio, computed as the ratio between the original and compressed response sizes.

# Author

Original author: Alex Zhang (张超) zchao1995@gmail.com, UPYUN Inc.

Maintained by GetPageSpeed LLC.

# License

This Nginx module is licensed under [BSD 2-Clause License](LICENSE). See [NOTICE](NOTICE) for
provenance.
