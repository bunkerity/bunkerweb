#!/usr/bin/env lua

local gd = require("gd")
local im = gd.createTrueColor(80, 80)
assert(im)

local black = im:colorAllocate(0, 0, 0)
local white = im:colorAllocate(255, 255, 255)
im:filledEllipse(40, 40, 70, 50, white)

im:png("out.png")
os.execute("xdg-open out.png")
