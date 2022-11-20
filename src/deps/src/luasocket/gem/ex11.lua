local input = source.chain(
  source.file(io.open("input.bin", "rb")),
  encode("base64"))
local output = sink.chain(
  wrap(76),
  sink.file(io.open("output.b64", "w")))
pump.all(input, output)
