#!/usr/bin/env lua

local gd = require("gd")

local im = gd.createPalette(80, 80)
assert(im)

local black = im:colorAllocate(0, 0, 0)
local white = im:colorAllocate(255, 255, 255)
im:gifAnimBegin("out.gif", true, 0)

for i = 1, 10 do
  tim = gd.createPalette(80, 80)
  tim:paletteCopy(im)
  tim:arc(40, 40, 40, 40, 36*(i-1), 36*i, white)
  tim:gifAnimAdd("out.gif", false, 0, 0, 5, gd.DISPOSAL_NONE)
end

gd.gifAnimEnd("out.gif")
os.execute("xdg-open out.gif")

