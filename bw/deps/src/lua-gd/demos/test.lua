#!/usr/bin/env lua

local gd = require("gd")

math.randomseed(os.time())

local im = gd.createFromJpeg("./bugs.jpg")
assert(im)
local sx, sy = im:sizeXY()

local im2 = gd.createTrueColor(2*sx, sy)
local black = im2:colorAllocate(0, 0, 0)
local white = im2:colorAllocate(255, 255, 255)
gd.copy(im2, im, 0, 0, 0, 0, sx, sy, sx, sy)

local sx2, sy2 = im2:sizeXY()
im2:stringUp(gd.FONT_SMALL, 5, sy2-10, gd.VERSION, white)

for i = 0, 14 do
  for j = 0, 24 do
    local rcl = im2:colorAllocate(math.random(255), math.random(255), 
            math.random(255))
    im2:filledRectangle(sx+20+j*10, i*20+40, sx+30+j*10, i*20+50, rcl)
  end
end

im2:string(gd.FONT_GIANT, sx+80, 10, "Powered by Lua", white)

local blackTr = im2:colorAllocateAlpha(0, 0, 0, 80)
im2:stringFT(blackTr, "./Vera.ttf", 140, 0, 70, 130, "gd")
im2:stringFT(white, "./Vera.ttf", 45, math.pi/5, 340, 250, "FreeType")


im2:png("out.png")
os.execute("xdg-open out.png")
