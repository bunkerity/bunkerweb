#!/usr/bin/env lua

local gd = require("gd")

local function boxedtext(im, color, font, size, ang, x, y, text, bcolor)
  local font = "./" .. font .. ".ttf"
  local llx, lly, lrx, lry, urx, ury, ulx, uly =
    im:stringFT(color, font, size, math.rad(ang), x, y, text)
  im:polygon({ {llx, lly}, {lrx, lry}, {urx, ury}, {ulx, uly} }, bcolor)
end

local im = gd.createTrueColor(400, 400)
assert(im)

local black = im:colorAllocate(0, 0, 0)
local grayt = im:colorAllocateAlpha(255, 255, 255, 70)
local bluet = im:colorAllocateAlpha(0, 0, 250, 70)
local redt = im:colorAllocateAlpha(255, 0, 0, 0)
local greent = im:colorAllocateAlpha(0, 250, 0, 70)
local lbluet = im:colorAllocateAlpha(180, 180, 255, 70)
local yellowt = im:colorAllocateAlpha(240, 240, 0, 70)

boxedtext(im, yellowt, "Vera", 300, 0, 60, 350, "A", bluet)
boxedtext(im, greent, "Vera", 80, 45, 60, 220, "Ithil", bluet)
boxedtext(im, redt, "Vera", 45, 90, 380, 300, "Lua-GD", bluet)
boxedtext(im, lbluet, "Vera", 36, 290, 160, 130, "FreeType", bluet)
boxedtext(im, grayt, "Vera", 26, 180, 390, 360, "Turn 180° before read", bluet)

im:png("out.png")
os.execute("xdg-open out.png")
