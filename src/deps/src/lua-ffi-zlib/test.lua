local table_insert = table.insert
local table_concat = table.concat

local zlib = require('lib.ffi-zlib')

local chunk = tonumber(arg[2]) or 16384
local uncompressed = ''
local input
local f

local passing = true

local in_adler
local out_adler
local in_crc
local out_crc

if arg[1] == nil then
    print("No file provided")
    return
else
    f = io.open(arg[1], "rb")
    input = function(bufsize)
        local d = f:read(bufsize)
        if d == nil then
            return nil
        end
        in_crc = zlib.crc(d, in_crc)
        in_adler = zlib.adler(d, in_adler)
        uncompressed = uncompressed..d
        return d
    end
end

print('zlib version: '..zlib.version())
print()

local output_table = {}
local output = function(data)
    out_crc = zlib.crc(data, out_crc)
    out_adler = zlib.adler(data, out_adler)
    table_insert(output_table, data)
end

-- Compress the data
print('Compressing')
local ok, err = zlib.deflateGzip(input, output, chunk)
if not ok then
    -- Err message
    print(err)
end

local compressed = table_concat(output_table,'')

local orig_in_crc = in_crc
local orig_in_adler = in_adler
print('Input crc32: ', in_crc)
print('Output crc32: ', out_crc)
print('Input adler32: ', in_adler)
print('Output adler32: ', out_adler)

-- Decompress it again
print()
print('Decompressing')
-- Reset vars
in_adler = nil
out_adler = nil
in_crc = nil
out_crc = nil
output_table = {}

local count = 0
local input = function(bufsize)
    local start = count > 0 and bufsize*count or 1
    local finish = (bufsize*(count+1)-1)
    count = count + 1
    if bufsize == 1 then
        start = count
        finish = count
    end
    local data = compressed:sub(start, finish)
    in_crc = zlib.crc(data, in_crc)
    in_adler = zlib.adler(data, in_adler)
    return data
end

local ok, err = zlib.inflateGzip(input, output, chunk)
if not ok then
    -- Err message
    print(err)
end
local output_data = table_concat(output_table,'')

print('Input crc32: ', in_crc)
print('Output crc32: ', out_crc)
print('Input adler32: ', in_adler)
print('Output adler32: ', out_adler)
print()

if output_data ~= uncompressed then
    passing = false
    print("inflateGzip / deflateGzip failed")
end

if orig_in_adler ~= out_adler then
    passing = false
    print("Adler checksum failed")
end

if orig_in_crc ~= out_crc then
    passing = false
    print("CRC checksum failed")
end

local bad_output = function(data)
    return nil, "bad output"
end

if not passing then
    print(":(")
else
    print(":)")
end

local dump_input = function(bufsize)
    return compressed
end

local ok, err = zlib.deflateGzip(dump_input, bad_output, chunk)
if not ok then
    if err ~= "DEFLATE: bad output" then
        print(err)
    else
        print("abort deflation: ok")
    end
end

local ok, err = zlib.inflateGzip(dump_input, bad_output, chunk)
if not ok then
    if err ~= "INFLATE: bad output" then
        print(err)
    else
        print("abort inflation: ok")
    end
end
