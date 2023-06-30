# lua-ffi-zlib

A [Lua](http://www.lua.org) module using LuaJIT's [FFI](http://luajit.org/ext_ffi.html) feature to access zlib.
Intended primarily for use within [OpenResty](http://openresty.org) to allow manipulation of gzip encoded HTTP responses.

# Methods

Basic methods allowing for simple compression or decompression of gzip data

## inflateGzip
`Syntax: ok, err = inflateGzip(input, output, chunk?, windowBits?)`

 * `input` should be a function that accepts a chunksize as its only argument and return that many bytes of the gzip stream
 * `output` will receive a string of decompressed data as its only argument, do with it as you will!
 * `chunk` is the size of the input and output buffers, optional and defaults to 16KB
 * `windowBits` is passed to `inflateInit2()`, should be left as default for most cases.
    See [zlib manual](http://zlib.net/manual.html) for details

On error returns `false` and the error message, otherwise `true` and the last status message

## deflateGzip
`Syntax: ok, err = deflateGzip(input, output, chunk?, options?)`
 * `input` should be a function that accepts a chunksize as its only argument and return that many bytes of uncompressed data.
 * `output` will receive a string of compressed data as its only argument, do with it as you will!
 * `chunk` is the size of the input and output buffers, optional and defaults to 16KB
 * `options` is a table of options to pass to `deflateInit2()`
    Valid options are level, memLevel, strategy and windowBits, see [zlib manual](http://zlib.net/manual.html) for details

On error returns `false` and the error message, otherwise `true` and the last status message

# Example
Reads a file and output the decompressed version.

Roughly equivalent to running `gzip -dc file.gz > out_file | tee`

```lua
local table_insert = table.insert
local table_concat = table.concat
local zlib = require('lib.ffi-zlib')

local f = io.open(arg[1], "rb")
local out_f = io.open(arg[2], "w")

local input = function(bufsize)
    -- Read the next chunk
    local d = f:read(bufsize)
    if d == nil then
        return nil
    end
    return d
end

local output_table = {}
local output = function(data)
    table_insert(output_table, data)
    local ok, err = out_f:write(data)
    if not ok then
        -- abort decompression when error occurs
        return nil, err
    end
end

-- Decompress the data
local ok, err = zlib.inflateGzip(input, output)
if not ok then
    print(err)
    return
end

local decompressed = table_concat(output_table,'')

print(decompressed)
```
# Advanced Usage

Several other methods are available for advanced usage.
Some of these map directly to functions in the zlib library itself, see the [manual](http://zlib.net/manual.html) for full details.
Others are lower level utility functions.

## createStream
`Synax: stream, inbuf, outbuf = createStream(bufsize)`

Returns a z_stream struct, input buffer and output buffer of length `bufsize`

##  initInflate
`Syntax: ok = initInflate(stream, windowBits?)`

Calls zlib's inflateInit2 with given stream, defaults to automatic header detection.

## initDeflate
`Syntax: ok = initDeflate(stream, options?)`

Calls zlib's deflateInit2 with the given stream.
`options` is an optional table that can set level, memLevel, strategy and windowBits

## deflate
`Syntax: ok, err = deflate(input, output, bufsize, stream, inbuf, outbuf)`

 * `input` is a function that takes a chunk size argument and returns at most that many input bytes
 * `output` is a function that takes a string argument of output data
 * `bufsize` is the length of the output buffer
 * `inbuf` cdata input buffer
 * `outpuf` ccdata output buffer

This function will loop until all input data is consumed (`input` returns nil) or an error occurs.
It will then clean up the stream and return an error code

## inflate
`Syntax: ok, err = inflate(input, output, bufsize, stream, inbuf, outbuf)`

 * `input` is a function that takes a chunk size argument and returns at most that many input bytes
 * `output` is a function that takes a string argument of output data
 * `bufsize` is the length of the output buffer
 * `inbuf` cdata input buffer
 * `outpuf` ccdata output buffer

This function will loop until all input data is consumed (`input` returns nil) or an error occurs.
It will then clean up the stream and return an error code

## adler
`Syntax: chksum = adler(str, chksum?)`

Computes an adler32 checksum for a string, updates an existing checksum if provided

## crc
`Syntax: chksum = crc(str, chksum?)`

Computes an crc32 checksum for a string, updates an existing checksum if provided

## zlib_err
`Syntax: err = zlib_err(code)`

Returns the string representation of a zlib error code
