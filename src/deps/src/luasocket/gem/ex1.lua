local CRLF = "\013\010"
local input = source.chain(source.file(io.stdin), normalize(CRLF))
local output = sink.file(io.stdout)
pump.all(input, output)
