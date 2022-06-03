local qp = filter.chain(normalize(CRLF), encode("quoted-printable"), 
  wrap("quoted-printable"))
local input = source.chain(source.file(io.stdin), qp)
local output = sink.file(io.stdout)
pump.all(input, output)
