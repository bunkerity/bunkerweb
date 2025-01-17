source = {}
sink = {}
pump = {}
filter = {}

-- filter.chain
dofile("ex3.lua")

-- normalize
require"gem"
eol = gem.eol
dofile("ex2.lua")

-- encode
require"mime"
encode = mime.encode

-- wrap
wrap = mime.wrap

-- source.chain
dofile("ex6.lua")

-- source.file
dofile("ex5.lua")

-- sink.file
require"ltn12"
sink.file = ltn12.sink.file

-- pump.all
dofile("ex10.lua")

-- run test
CRLF = "\013\010"
dofile("ex4.lua")
