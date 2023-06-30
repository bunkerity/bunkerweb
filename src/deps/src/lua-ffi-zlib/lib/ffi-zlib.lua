local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_str = ffi.string
local ffi_sizeof = ffi.sizeof
local ffi_copy = ffi.copy
local tonumber = tonumber

local _M = {
    _VERSION = '0.5.0',
}

local mt = { __index = _M }


ffi.cdef([[
enum {
    Z_NO_FLUSH           = 0,
    Z_PARTIAL_FLUSH      = 1,
    Z_SYNC_FLUSH         = 2,
    Z_FULL_FLUSH         = 3,
    Z_FINISH             = 4,
    Z_BLOCK              = 5,
    Z_TREES              = 6,
    /* Allowed flush values; see deflate() and inflate() below for details */
    Z_OK                 = 0,
    Z_STREAM_END         = 1,
    Z_NEED_DICT          = 2,
    Z_ERRNO              = -1,
    Z_STREAM_ERROR       = -2,
    Z_DATA_ERROR         = -3,
    Z_MEM_ERROR          = -4,
    Z_BUF_ERROR          = -5,
    Z_VERSION_ERROR      = -6,
    /* Return codes for the compression/decompression functions. Negative values
    * are errors, positive values are used for special but normal events.
    */
    Z_NO_COMPRESSION      =  0,
    Z_BEST_SPEED          =  1,
    Z_BEST_COMPRESSION    =  9,
    Z_DEFAULT_COMPRESSION = -1,
    /* compression levels */
    Z_FILTERED            =  1,
    Z_HUFFMAN_ONLY        =  2,
    Z_RLE                 =  3,
    Z_FIXED               =  4,
    Z_DEFAULT_STRATEGY    =  0,
    /* compression strategy; see deflateInit2() below for details */
    Z_BINARY              =  0,
    Z_TEXT                =  1,
    Z_ASCII               =  Z_TEXT,   /* for compatibility with 1.2.2 and earlier */
    Z_UNKNOWN             =  2,
    /* Possible values of the data_type field (though see inflate()) */
    Z_DEFLATED            =  8,
    /* The deflate compression method (the only one supported in this version) */
    Z_NULL                =  0,  /* for initializing zalloc, zfree, opaque */
};


typedef void*    (* z_alloc_func)( void* opaque, unsigned items, unsigned size );
typedef void     (* z_free_func) ( void* opaque, void* address );

typedef struct z_stream_s {
   char*         next_in;
   unsigned      avail_in;
   unsigned long total_in;
   char*         next_out;
   unsigned      avail_out;
   unsigned long total_out;
   char*         msg;
   void*         state;
   z_alloc_func  zalloc;
   z_free_func   zfree;
   void*         opaque;
   int           data_type;
   unsigned long adler;
   unsigned long reserved;
} z_stream;


const char*   zlibVersion();
const char*   zError(int);

int inflate(z_stream*, int flush);
int inflateEnd(z_stream*);
int inflateInit2_(z_stream*, int windowBits, const char* version, int stream_size);

int deflate(z_stream*, int flush);
int deflateEnd(z_stream* );
int deflateInit2_(z_stream*, int level, int method, int windowBits, int memLevel,int strategy, const char *version, int stream_size);

unsigned long adler32(unsigned long adler, const char *buf, unsigned len);
unsigned long crc32(unsigned long crc,   const char *buf, unsigned len);
unsigned long adler32_combine(unsigned long, unsigned long, long);
unsigned long crc32_combine(unsigned long, unsigned long, long);

]])

local zlib = ffi.load(ffi.os == "Windows" and "zlib1" or "z")
_M.zlib = zlib

-- Default to 16k output buffer
local DEFAULT_CHUNK = 16384

local Z_OK           = zlib.Z_OK
local Z_NO_FLUSH     = zlib.Z_NO_FLUSH
local Z_STREAM_END   = zlib.Z_STREAM_END
local Z_FINISH       = zlib.Z_FINISH
local Z_NEED_DICT    = zlib.Z_NEED_DICT
local Z_BUF_ERROR    = zlib.Z_BUF_ERROR
local Z_STREAM_ERROR = zlib.Z_STREAM_ERROR

local function zlib_err(err)
    return ffi_str(zlib.zError(err))
end
_M.zlib_err = zlib_err

local function createStream(bufsize)
    -- Setup Stream
    local stream = ffi_new("z_stream")

    -- Create input buffer var
    local inbuf = ffi_new('char[?]', bufsize+1)
    stream.next_in, stream.avail_in = inbuf, 0

    -- create the output buffer
    local outbuf = ffi_new('char[?]', bufsize)
    stream.next_out, stream.avail_out = outbuf, 0

    return stream, inbuf, outbuf
end
_M.createStream = createStream

local function initInflate(stream, windowBits)
    -- Setup inflate process
    local windowBits = windowBits or (15 + 32) -- +32 sets automatic header detection
    local version    = ffi_str(zlib.zlibVersion())

    return zlib.inflateInit2_(stream, windowBits, version, ffi_sizeof(stream))
end
_M.initInflate = initInflate

local function initDeflate(stream, options)
    -- Setup deflate process
    local method     = zlib.Z_DEFLATED
    local level      = options.level      or zlib.Z_DEFAULT_COMPRESSION
    local memLevel   = options.memLevel   or 8
    local strategy   = options.strategy   or zlib.Z_DEFAULT_STRATEGY
    local windowBits = options.windowBits or (15 + 16) -- +16 sets gzip wrapper not zlib
    local version    = ffi_str(zlib.zlibVersion())

    return zlib.deflateInit2_(stream, level, method, windowBits, memLevel, strategy, version, ffi_sizeof(stream))
end
_M.initDeflate = initDeflate

local function flushOutput(stream, bufsize, output, outbuf)
    -- Calculate available output bytes
    local out_sz = bufsize - stream.avail_out
    if out_sz == 0 then
        return
    end
    -- Read bytes from output buffer and pass to output function
    local ok, err = output(ffi_str(outbuf, out_sz))
    if not ok then
        return err
    end
end

local function inflate(input, output, bufsize, stream, inbuf, outbuf)
    local zlib_flate = zlib.inflate
    local zlib_flateEnd = zlib.inflateEnd
    -- Inflate a stream
    local err = 0
    repeat
        -- Read some input
        local data = input(bufsize)
        if data ~= nil then
            ffi_copy(inbuf, data)
            stream.next_in, stream.avail_in = inbuf, #data
        else
            -- no more input data
            stream.avail_in = 0
        end

        if stream.avail_in == 0 then
            -- When decompressing we *must* have input bytes
            zlib_flateEnd(stream)
            return false, "INFLATE: Data error, no input bytes"
        end

        -- While the output buffer is being filled completely just keep going
        repeat
            stream.next_out  = outbuf
            stream.avail_out = bufsize
            -- Process the stream, always Z_NO_FLUSH in inflate mode
            err = zlib_flate(stream, Z_NO_FLUSH)

            -- Buffer errors are OK here
            if err == Z_BUF_ERROR then
                err = Z_OK
            end
            if err < Z_OK or err == Z_NEED_DICT then
               -- Error, clean up and return
               zlib_flateEnd(stream)
               return false, "INFLATE: "..zlib_err(err), stream
            end
            -- Write the data out
            local err = flushOutput(stream, bufsize, output, outbuf)
            if err then
               zlib_flateEnd(stream)
               return false, "INFLATE: "..err
            end
        until stream.avail_out ~= 0

    until err == Z_STREAM_END

    -- Stream finished, clean up and return
    zlib_flateEnd(stream)
    return true, zlib_err(err)
end
_M.inflate = inflate

local function deflate(input, output, bufsize, stream, inbuf, outbuf)
    local zlib_flate = zlib.deflate
    local zlib_flateEnd = zlib.deflateEnd

    -- Deflate a stream
    local err = 0
    local mode = Z_NO_FLUSH
    repeat
        -- Read some input
        local data = input(bufsize)
        if data ~= nil then
            ffi_copy(inbuf, data)
            stream.next_in, stream.avail_in = inbuf, #data
        else
            -- EOF, try and finish up
            mode = Z_FINISH
            stream.avail_in = 0
        end

        -- While the output buffer is being filled completely just keep going
        repeat
            stream.next_out  = outbuf
            stream.avail_out = bufsize

            -- Process the stream
            err = zlib_flate(stream, mode)

            -- Only possible *bad* return value here
            if err == Z_STREAM_ERROR then
               -- Error, clean up and return
               zlib_flateEnd(stream)
               return false, "DEFLATE: "..zlib_err(err), stream
            end
            -- Write the data out
            local err = flushOutput(stream, bufsize, output, outbuf)
            if err then
               zlib_flateEnd(stream)
               return false, "DEFLATE: "..err
            end
        until stream.avail_out ~= 0

        -- In deflate mode all input must be used by this point
        if stream.avail_in ~= 0 then
            zlib_flateEnd(stream)
            return false, "DEFLATE: Input not used"
        end

    until err == Z_STREAM_END

    -- Stream finished, clean up and return
    zlib_flateEnd(stream)
    return true, zlib_err(err)
end
_M.deflate = deflate

local function adler(str, chksum)
    local chksum = chksum or 0
    local str = str or ""
    return zlib.adler32(chksum, str, #str)
end
_M.adler = adler

local function crc(str, chksum)
    local chksum = chksum or 0
    local str = str or ""
    return zlib.crc32(chksum, str, #str)
end
_M.crc = crc

function _M.inflateGzip(input, output, bufsize, windowBits)
    local bufsize = bufsize or DEFAULT_CHUNK

    -- Takes 2 functions that provide input data from a gzip stream and receives output data
    -- Returns uncompressed string
    local stream, inbuf, outbuf = createStream(bufsize)

    local init = initInflate(stream, windowBits)
    if init == Z_OK then
        return inflate(input, output, bufsize, stream, inbuf, outbuf)
    else
        -- Init error
        zlib.inflateEnd(stream)
        return false, "INIT: "..zlib_err(init)
    end
end

function _M.deflateGzip(input, output, bufsize, options)
    local bufsize = bufsize or DEFAULT_CHUNK
    options = options or {}

    -- Takes 2 functions that provide plain input data and receives output data
    -- Returns gzip compressed string
    local stream, inbuf, outbuf = createStream(bufsize)

    local init = initDeflate(stream, options)
    if init == Z_OK then
        return deflate(input, output, bufsize, stream, inbuf, outbuf)
    else
        -- Init error
        zlib.deflateEnd(stream)
        return false, "INIT: "..zlib_err(init)
    end
end

function _M.version()
    return ffi_str(zlib.zlibVersion())
end

return _M
