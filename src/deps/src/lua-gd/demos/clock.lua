#!/usr/bin/env lua

-- a cgi script that draws an analog clock with lua and lua-gd
-- (c) 2004 Alexandre Erwin Ittner

local gd = require("gd")

local function createClock(size, hours, minutes)
  local im = gd.createTrueColor(size, size)
  local white = im:colorAllocate(255, 255, 255)
  local gray = im:colorAllocate(128, 128, 128)
  local black = im:colorAllocate(0, 0, 0)
  local blue = im:colorAllocate(0, 0, 128)
  local cxy = size/2

  im:filledRectangle(0, 0, size, size, white)
  im:setThickness(math.max(1, size/100))
  im:arc(cxy, cxy, size, size, 0, 360, black)

  local ang = 0
  local rang, gsize
  while ang < 360 do
    rang = math.rad(ang)
    if (ang % 90) == 0 then
      gsize = 0.75
    else
      gsize = 0.85
    end
    im:line(
      cxy + gsize * cxy * math.sin(rang),
      size - (cxy + gsize * cxy * math.cos(rang)),
      cxy + cxy * 0.9 * math.sin(rang),
      size - (cxy + cxy * 0.9 * math.cos(rang)),
      gray)
    ang = ang + 30
  end

  im:setThickness(math.max(1, size/50))
  im:line(cxy, cxy,
    cxy + 0.45 * size * math.sin(math.rad(6*minutes)),
    size - (cxy + 0.45 * size * math.cos(math.rad(6*minutes))),
    blue)

  im:setThickness(math.max(1, size/25))
  rang = math.rad(30*hours + minutes/2)
  im:line(cxy, cxy, 
    cxy + 0.25 * size * math.sin(rang),
    size - (cxy + 0.25 * size * math.cos(rang)),
    blue)

  im:setThickness(1)
  local sp = math.max(1, size/20)
  im:filledArc(cxy, cxy, sp, sp, 0, 360, black, gd.ARC)

  return im
end

local dh = os.date("*t")
local im = createClock(100, dh.hour, dh.min)

print("Content-type: image/png")
print("Refresh: 60")            -- Ask browser to reload the image after 60s
print("Pragma: no-cache")       -- Can mozilla understand this?
print("Expires: Thu Jan 01 00:00:00 UTC 1970")  -- Marks as expired
print("")

io.write(im:pngStr())

