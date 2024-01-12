#!/usr/bin/env lua

local gd = require("gd")

local im = gd.createPalette(120, 120)
assert(im)

local black = im:colorAllocate(0, 0, 0)
local blue = {}
for i = 1, 20 do
  blue[i] = im:colorAllocate(0, 0, 120+6*i)
end

im:gifAnimBegin("out.gif", true, 0)
for i = 1, 20 do
  tim = gd.createPalette(120, 120)
  tim:paletteCopy(im)
  tim:arc(60, 60, 6*i, 6*i, 0, 360, blue[21-i])
  tim:gifAnimAdd("out.gif", false, 0, 0, 5, gd.DISPOSAL_NONE)
end

gd.gifAnimEnd("out.gif")
os.execute("xdg-open out.gif")

