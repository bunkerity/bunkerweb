#!/usr/bin/env lua

local gd = require("gd")

gd.useFontConfig(true) -- Use Fontconfig by default.

local im = gd.createTrueColor(400, 400)
assert(im)

local black = im:colorAllocate(0, 0, 0)
local grayt = im:colorAllocateAlpha(255, 255, 255, 80)
local blue = im:colorAllocate(0, 0, 250)
local red = im:colorAllocate(255, 0, 0)
local green = im:colorAllocate(0, 250, 0)
local lblue = im:colorAllocate(180, 180, 255)
local yellow = im:colorAllocate(240, 240, 0)

im:stringFTEx(lblue, "Vera", 20, 0, 40, 40, "Half\nspace", 
    { linespacing = 0.5 } )

im:stringFTEx(red, "Vera", 20, 0, 140, 40, "Single\nspace", 
    { linespacing = 1.0 } )

im:stringFTEx(green, "Vera", 20, 0, 240, 40, "Double\nspace", 
    { linespacing = 2.0 } )

im:stringFTEx(yellow, "Vera", 40, 0, 80, 140, "Distorted!", 
    { hdpi = 96, vdpi = 30 } )


local k = "Kerniiiiiiiiiiiiiiiiiing?"
print(im:stringFTEx(red, "Vera", 30, 0, 10, 200, k, {}))
print(im:stringFTEx(red, "Vera", 30, 0, 10, 240, k, 
    { disable_kerning = true } ))

for i = 10, 400, 10 do
  im:line(i, 170, i, 250, grayt)
end 


local llX, llY, lrX, lrY, urX, urY, ulX, ulY, fontpath =
  im:stringFTEx(lblue, "Vera", 20, 0, 50, 320, "This font comes from",
    { return_font_path_name = true } )

im:string(gd.FONT_MEDIUM, 10, 340, fontpath, lblue)


im:png("out.png")
os.execute("xdg-open out.png")
