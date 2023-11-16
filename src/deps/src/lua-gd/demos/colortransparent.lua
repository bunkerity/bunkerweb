#!/usr/bin/env lua

local gd = require("gd")

local im = gd.createPalette(90, 90)

local white = im:colorAllocate(255, 255, 255)
local blue = im:colorAllocate(0, 0, 255)
local red = im:colorAllocate(255, 0, 0)

im:colorTransparent(white)
im:filledRectangle(10, 10, 50, 50, blue)
im:filledRectangle(40, 40, 80, 80, red)

im:gif("out.gif")
os.execute("xdg-open out.gif")
