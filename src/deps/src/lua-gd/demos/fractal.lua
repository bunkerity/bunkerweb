#!/usr/bin/env lua

-- Draws the famous Sierpinski triangle with lua-gd

local gd = require("gd")

local size = 500

local im = gd.createPalette(size, size)
local white = im:colorAllocate(255, 255, 255)
local black = im:colorAllocate(0, 0, 0)

local m = {}
m[math.floor(size/2)] = true

local n
for i = 1, size do
  n = {}
  for j = 1, size do
    if m[j] then
      im:setPixel(j, i, black)
      n[j+1] = not n[j+1]
      n[j-1] = not n[j-1]
    end
  end
  m = n
end

im:png("out.png")
os.execute("xdg-open out.png")

