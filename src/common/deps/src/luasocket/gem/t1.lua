source = {}
sink = {}
pump = {}
filter = {}

-- source.chain
dofile("ex6.lua")

-- source.file
dofile("ex5.lua")

-- normalize
require"gem"
eol = gem.eol
dofile("ex2.lua")

-- sink.file
require"ltn12"
sink.file = ltn12.sink.file

-- pump.all
dofile("ex10.lua")

-- run test
dofile("ex1.lua")
