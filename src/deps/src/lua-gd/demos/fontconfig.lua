#!/usr/bin/env lua

-- The fonts used in this example comes with Microsoft operating systems 
-- and can be downloaded from http://corefonts.sourceforge.net

local gd = require("gd")

local im = gd.createTrueColor(220, 190)
local white = im:colorAllocate(255, 255, 255)
local black = im:colorAllocate(0, 0, 0)
local x, y = im:sizeXY()
im:filledRectangle(0, 0, x, y, white)

gd.useFontConfig(true)
im:stringFT(black, "Arial", 20, 0, 10, 30, "Standard Arial")
im:stringFT(black, "Arial:bold", 20, 0, 10, 60, "Bold Arial")
im:stringFT(black, "Arial:italic", 20, 0, 10, 90, "Italic Arial")
im:stringFT(black, "Arial:bold:italic", 20, 0, 10, 120, "Italic Bold Arial")
im:stringFT(black, "Times New Roman", 20, 0, 10, 150, "Times New Roman")
im:stringFT(black, "Comic Sans MS", 20, 0, 10, 180, "Comic Sans MS")

im:png("out.png")
os.execute("xdg-open out.png")
