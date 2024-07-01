#!/usr/bin/env lua
-- counter.lua -- a web counter in Lua!
-- (c) 2004 Alexandre Erwin Ittner

local gd = require("gd")

local datafile = "counter.txt"
local fp = io.open(datafile, "r+")
local cnt = 0
if fp then
  cnt = tonumber(fp:read("*l")) or 0
  fp:seek("set", 0)
else
  fp = io.open(datafile, "w")
  assert(fp)
end
cnt = cnt + 1
fp:write(cnt .."\n")
fp:close()

local sx = math.max(string.len(tostring(cnt)), 1) * 8
local im = gd.create(sx, 15)
-- first allocated color defines the background.
local white = im:colorAllocate(255, 255, 255)
im:colorTransparent(white)
local black = im:colorAllocate(0, 0, 0)
im:string(gd.FONT_MEDIUM, 1, 1, cnt, black)

print("Content-type: image/png\n")
io.write(im:pngStr())
