#!/usr/bin/env lua

local gd = require("gd")

local im = gd.createFromJpeg("./bugs.jpg")
assert(im)

local white = im:colorAllocate(255, 255, 255)
im:string(gd.FONT_MEDIUM, 10, 10, "Powered by", white)

local imlua = gd.createFromPng("./lua-gd.png")
-- imlua:colorTransparent(imlua:getPixel(0, 0))

local sx, sy = imlua:sizeXY()
gd.copy(im, imlua, 10, 25, 0, 0, sx, sy, sx, sy)
im:string(gd.FONT_MEDIUM, 10, 330, "http://ittner.github.com/lua-gd/", white)

im:png("out.png")
os.execute("xdg-open out.png")
