source = {}
sink = {}
pump = {}
filter = {}

-- source.file
dofile("ex5.lua")

-- sink.table
dofile("ex7.lua")

-- sink.chain
require"ltn12"
sink.chain = ltn12.sink.chain

-- normalize
require"gem"
eol = gem.eol
dofile("ex2.lua")

-- pump.all
dofile("ex10.lua")

-- run test
dofile("ex8.lua")
