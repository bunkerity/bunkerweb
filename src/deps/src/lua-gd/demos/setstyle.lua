#!/usr/bin/env lua

local gd = require("gd")

local im = gd.createPalette(150, 100)
assert(im, "Failed to create new image.")

local white = im:colorAllocate(255, 255, 255)
local red = im:colorAllocate(200, 0, 0)
local green = im:colorAllocate(0, 128, 0)
local blue = im:colorAllocate(0, 0, 128)

local style = {}

for i = 0, 10 do
    style[#style+1] = red
end

for i = 0, 5 do
    style[#style+1] = blue
end

for i = 0, 2 do
    style[#style+1] = green
end

im:setStyle(style)

for i = 0, 100, 2 do
    im:line(i, i, i+50, i, gd.STYLED)
end

im:png("out.png")
os.execute("xdg-open out.png")


