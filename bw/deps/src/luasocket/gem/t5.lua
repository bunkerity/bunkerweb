source = {}
sink = {}
pump = {}
filter = {}

-- source.chain
dofile("ex6.lua")

-- source.file
dofile("ex5.lua")

-- encode
require"mime"
encode = mime.encode

-- sink.chain
require"ltn12"
sink.chain = ltn12.sink.chain

-- wrap
wrap = mime.wrap

-- sink.file
sink.file = ltn12.sink.file

-- pump.all
dofile("ex10.lua")

-- run test
dofile("ex11.lua")
