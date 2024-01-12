#!/usr/bin/env lua
--[[

                      Steganography with Lua-GD

Steganography is the technique of writing hidden messages in such a way
that no one apart from the intended recipient knows of the existence of
the message; this is in contrast to cryptography, where the existence
of the message is clear, but the meaning is obscured. Generally a
steganographic message will appear to be something else, like a shopping
list, an article, a picture, or some other "cover" message. In the
digital age, steganography works by replacing bits of useless or unused
data in regular computer files (such as graphics, sound, text, HTML, or
even floppy disks) with bits of different, invisible information. This
hidden information can be plain text, cipher text or even images.


                           A Simple Example

If Alice wants to send a secret message to Bob through an insecure
channel, she can use some encryption software (like GnuPG) to encrypt
the message with Bob's public key. It's a good solution because no
one unless Bob will be able to read the message. She can also sign the
message so Bob will know that the message really comes from her. BUT,
a potential attacker will know that a ciphered message was sent. If the
attacker has control over the communication channel, he might block the
message in some way that Bob will never receive it. If Alice also HIDES
the ciphertext in an unsuspected piece of information (like a photo of her
cat) the attacker will not detect it and the message will arrive to Bob.

This program will help Alice to hide some arbitrary text in a PNG image by
replacing the least significant bits of each color channel of some pixels
with bits from the encrypted message. PNG or other loseless compression
algorithm are mandatory here, since compressing the image with a lossy
algorithm will destroy the stored information. The maximum length of the
message is limited by the image's size (each byte needs 8 color channels or
2 pixels and 2 channels from the next pixel). So, the image must have at
least "ceil((length+1)*8/3)" pixels (the extra byte is the NUL marker for
the end of the string). So, if Alice's message is "Meet me in the secret
place at nine o'clock.", she will encrypt and sign it to something like
"PyJYDpz5LCOSHPiXDvLHmVzxLV8qS7EFvZnoo1Mxk+BlT+7lMjpQKs" (imagine Alice's
cat walking in you keyboard :). This is the ciphertext that will be sent
to Bob through the image.

The following table shows what happens to the first eight pixels from
the image when mixed to the first three bytes from the encrypted message:


         +-----+---+----------+-----------------+----------+
         | Pix | C | Orig img |     Message     | New img  |
         |  #  |   |   bits   | Chr | Dec | Bin |   bits   |
         +-----+---+----------+-----+-----+-----+----------+
         |     | R | 01010010 |     |     |  0  | 01010010 |
         |  1  | G | 00101010 |     |     |  1  | 00101011 |
         |_____| B | 00010101 |     |     |  0  | 00010100 |
         |     | R | 11100100 |  P  | 080 |  1  | 11100101 |
         |  2  | G | 00100100 |     |     |  0  | 00100100 |
         |_____| B | 01001111 |     |     |  0  | 01001110 |
         |     | R | 01010010 |     |     |  0  | 01010010 |
         |  3  | G | 00101110 |_____|_____|__0__| 00101110 |
         |_____| B | 00111001 |     |     |  0  | 00111000 |
         |     | R | 10010110 |     |     |  1  | 10010111 |
         |  4  | G | 01011101 |     |     |  1  | 01011101 |
         |_____| B | 00100101 |  y  | 121 |  1  | 00100101 |
         |     | R | 01001001 |     |     |  1  | 01001001 |
         |  5  | G | 10110110 |     |     |  0  | 10110110 |
         |_____| B | 00010101 |     |     |  0  | 00010100 |
         |     | R | 00110100 |_____|_____|__1__| 00110101 |
         |  6  | G | 01000111 |     |     |  0  | 01000110 |
         |_____| B | 01001000 |     |     |  1  | 01001001 |
         |     | R | 01010110 |     |     |  0  | 01010110 |
         |  7  | G | 00011001 |     |     |  0  | 00011000 |
         |_____| B | 10010100 |  J  | 074 |  1  | 10010101 |
         |     | R | 00010101 |     |     |  0  | 00010100 |
         |  8  | G | 01011010 |     |     |  1  | 01011011 |
         |     | B | 01010001 |     |     |  0  | 01010000 |
         +-----+---+----------+-----+-----+-----+----------+


When Bob wants to read the message he will extract the least significant
bit (LSB) from each color channel from some pixels of the image and
join them to get the original ciphertext. A NULL character (ASCII #0)
will mark the end of the message within the image, so he will know when
to stop. Of course, this program will also do this boring job for Bob.


]]


local gd = require("gd")


local function getLSB(n)
  return (n % 2) ~= 0
end


-- Bizarre way to do some bit-level operations without bitlib.
local function setLSB(n, b)
  if type(b) == "number" then
    if b == 0 then
      b = false
    else
      b = true
    end
  end
  if getLSB(n) then
    if b then
      return n
    elseif n > 0 then
      return n - 1
    else
      return n + 1
    end
  else
    if not b then
      return n
    elseif n > 0 then
      return n - 1
    else
      return n + 1
    end
  end
end


local function intToBitArray(n)
  local ret = {}
  local i = 0
  while n ~= 0 do
    ret[i] = getLSB(n)
    n = math.floor(n/2)
    ret.size = i
    i = i + 1
  end 
  return ret
end


local function printBitArray(a)
  local i
  for i = a.size,0,-1 do
    if a[i] then
      io.write("1")
    else    
      io.write("0")
    end
  end
end


local function mergeMessage(im, msg)
  local w, h = im:sizeXY()
  msg = msg .. string.char(0)
  local len = string.len(msg)
  if h * w < len * 8 then
    return nil
  end
  local x, y = 0, 0
  local oim = gd.createTrueColor(w, h)
  local i = 1
  local a2, c, nc, chr
  local a = {}
  local s, e = 1, 1
  local rgb = {}

  while y < h do
    c = im:getPixel(x, y)
    rgb.r = im:red(c)
    rgb.g = im:green(c)
    rgb.b = im:blue(c)
    if i <= len and  e - s < 3 then
      a2 = intToBitArray(string.byte(string.sub(msg, i, i)))
      for cnt = 7,0,-1 do
        a[e+7-cnt] = a2[cnt]
      end
      i = i + 1
      e = e + 8
    end
    if e - s > 0 then
      rgb.r = setLSB(rgb.r, a[s])
      a[s] = nil
      s = s + 1
    end
    if e - s > 0 then
      rgb.g = setLSB(rgb.g, a[s])
      a[s] = nil
      s = s + 1
    end
    if e - s > 0 then
      rgb.b = setLSB(rgb.b, a[s])
      a[s] = nil
      s = s + 1
    end
    nc = oim:colorResolve(rgb.r, rgb.g, rgb.b)
    oim:setPixel(x, y, nc)
    x = x + 1
    if x == w then
      x = 0
      y = y + 1
    end
  end
  return oim, len*8, w*h
end


local function getMessage(im)
  local msg = {}
  local w, h = im:sizeXY()
  local x, y = 0, 0
  local a = {}
  local s, e = 1, 1
  local b = 0
  local c
  while y <= h do
    c = im:getPixel(x, y)
    a[e] = getLSB(im:red(c))
    a[e+1] = getLSB(im:green(c))
    a[e+2] = getLSB(im:blue(c))
    e = e + 2
    if e - s >= 7 then
      b = 0
      for p = s, s+7 do
        b = b * 2
        if a[p] then
          b = b + 1
        end
        a[p] = nil
      end
      s = s + 8
      if b == 0 then
        return table.concat(msg)
      else
        msg[#msg+1] = string.char(b)
      end
    end
    e = e + 1
    x = x + 1
    if x == w then
      x = 0
      y = y + 1
    end
  end
  return table.concat(msg)
end


local function compare(fimg1, fimg2)
  local im1 = gd.createFromPng(fimg1)
  if not im1 then
    print("ERROR: " .. fimg1 .. " bad PNG data.")
    os.exit(1)
  end
  local im2 = gd.createFromPng(fimg2)
  if not im2 then
    print("ERROR: " .. fimg2 .. " bad PNG data.")
    os.exit(1)
  end
  local w1, h1 = im1:sizeXY()
  local w2, h2 = im2:sizeXY()
  if w1 ~= w2 or h1 ~= h2 then
    print("ERROR: Images have different sizes.")
    os.exit(1)
  end
  local oim = gd.createTrueColor(w1, h1)
  local x, y = 0, 0
  local c1, c2, oc, f, fc
  while y < h1 do
    c1 = im1:getPixel(x, y)
    c2 = im2:getPixel(x, y)
    if im1:red(c1) ~= im2:red(c2)
    or im1:green(c1) ~= im2:green(c2)
    or im1:blue(c1) ~= im2:blue(c2) then
      oc = oim:colorResolve(im2:red(c2), im2:green(c2), im2:blue(c2))
      oim:setPixel(x, y, oc)
    else
      f = math.floor((im1:red(c1) + im1:green(c1) + im1:blue(c1))/6.0)
      fc = oim:colorResolve(f, f, f)
      oim:setPixel(x, y, fc)
    end
    x = x + 1
    if x == w1 then
      x = 0
      y = y + 1
    end
  end
  return oim
end
    

local function usage()
  print("Usage:")
  print(" lua steg.lua hide <input file> <output file>")
  print(" lua steg.lua show <input file>")
  print(" lua steg.lua diff <input file 1> <input file 2> <output file>")
  print("")
  print(" hide - Reads a message from stdin and saves into <output file>.")
  print(" show - Reads a message from <input file> and prints it to stdout.")
  print(" diff - Compares two images and writes the diff to <output file>.")
  print("")
  print(" WARNING: All files used here must be in the PNG format!")
end


if not arg[1] or not arg[2] then
  usage()
  os.exit(1)
end

if arg[1] == "show" then
  local im = gd.createFromPng(arg[2])
  if not im then    
    print("ERROR: Bad image data.")
    os.exit(1)
  end
  io.write(getMessage(im))
  os.exit(0)
end

if arg[1] == "hide" then
  if not arg[3] then
    usage()
    os.exit(1)
  end
  local im = gd.createFromPng(arg[2])
  if not im then
    print("ERROR: Bad image data.")
    os.exit(1)
  end
  print("Type your message and press CTRL+D to finish.")
  local msg = io.read("*a")
  local oim, l, t = mergeMessage(im, msg)
  if not oim then
    print("ERROR: Image is too small for the message.")
    os.exit(1)
  end
  if not oim:png(arg[3]) then
    print("ERROR: Failed to write output file.")
    os.exit(1)
  end
  print(string.format("DONE: %2.1f%% of the image used to store the message.",
    100.0*l/t))
  os.exit(0)
end

if arg[1] == "diff" then
  if not arg[3] and arg[4] then
    usage()
    os.exit(1)
  end
  local oim = compare(arg[2], arg[3])
  if not oim:png(arg[4]) then
    print("ERROR: Failed to write output file.")
    os.exit(1)
  end
  os.exit(0)
end

usage()
os.exit(1)

