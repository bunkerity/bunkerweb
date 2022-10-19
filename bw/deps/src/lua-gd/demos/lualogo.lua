#!/usr/bin/env lua

--
-- lualogo.lua (c) 2006-11 Alexandre Erwin Ittner <alexandre@ittner.com.br>
--
-- Drawns the Lua Logo. This script requires fontconfig and the "Helvetica" 
-- font installed in your system.
--
--


local gd = require("gd")

gd.useFontConfig(true)

function makelogo(size)
  local nsize = 3 * size
  local im = gd.createTrueColor(nsize, nsize)
  local white = im:colorAllocate(255, 255, 255)
  local blue = im:colorAllocate(0, 0, 128)
  local gray = im:colorAllocate(170, 170, 170)

  local ediam = nsize * 0.68                    -- Earth diameter
  local mdiam = ediam * (1 - math.sqrt(2) / 2)  -- Moon diameter
  local odiam = ediam * 1.3                     -- Orbit diameter
  local emdist = odiam/2 * 1.05                 -- Earth - Moon distance
  local esdist = odiam/2 * 0.4                  -- Earth - Moon shadow distance
  local mang = 45                               -- Moon angle (degrees)
  local mangr = math.rad(mang)
  local cxy = nsize/2.0

  im:fill(0, 0, white)
  im:filledArc(cxy, cxy, ediam, ediam, 0, 360, blue, gd.ARC)

  im:setThickness(math.max(0.02 * ediam, 1))
  for i = 0, 360, 10 do
    im:arc(cxy, cxy, odiam, odiam, i, i+5, gray)
  end
  im:setThickness(1)

  -- Moon
  local mcx = cxy + math.sin(math.rad(mang)) * emdist
  local mcy = cxy - math.cos(math.rad(mang)) * emdist
  im:filledArc(mcx, mcy, mdiam, mdiam, 0, 360, blue, gd.ARC)

  -- Moon shadow
  local mscx = cxy + math.sin(math.rad(mang)) * esdist
  local mscy = cxy - math.cos(math.rad(mang)) * esdist
  im:filledArc(mscx, mscy, mdiam, mdiam, 0, 360, white, gd.ARC)

  im:stringFT(white, "Helvetica", 0.23*nsize, 0, 0.25*nsize, 0.7*nsize, "Lua")

  -- Implementation of the "Desperate anti-aliasing algorithm" ;)
  local im2 = gd.createTrueColor(size, size)
  im2:copyResampled(im, 0, 0, 0, 0, size, size, nsize, nsize)
  return im2
end

makelogo(140):png("out.png")
os.execute("xdg-open out.png")
