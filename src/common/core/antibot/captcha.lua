-- Copyright startx <startx@plentyfact.org>
-- Modifications copyright mrDoctorWho <mrdoctorwho@gmail.com>
-- Published under the MIT license

local _M = {}

local gd = require 'gd'
local os = os

local mt = { __index = {} }

-- Create a new captcha generator instance
function _M.new()
    local cap = {}
    local f = setmetatable({ cap = cap }, mt)
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        print("DEBUG: Creating new captcha instance")
    end
    
    return f
end

-- Generate random seed from /dev/urandom
local function urandom()
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        print("DEBUG: Reading from /dev/urandom")
    end
    
    local seed = 1
    local devurandom = io.open("/dev/urandom", "r")
    if not devurandom then
        if debug_mode then
            print("DEBUG: Failed to open /dev/urandom")
        end
        return os.time()  -- Fallback to current time
    end
    
    local urandom = devurandom:read(32)
    devurandom:close()

    if debug_mode then
        print("DEBUG: Read " .. string.len(urandom) .. " bytes from urandom")
    end

    for i = 1, string.len(urandom) do
        local s = string.byte(urandom, i)
        seed = seed + s
    end
    
    if debug_mode then
        print("DEBUG: Generated seed: " .. seed)
    end
    
    return seed
end

-- Generate random character string of specified length
local function random_char(length)
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        print("DEBUG: Generating random characters, length: " .. length)
    end
    
    local set, char, uid
    local set = [[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]]
    local captcha_t = {}

    local seed = urandom()
    if debug_mode then
        print("DEBUG: Random seed: " .. seed)
    end
    
    math.randomseed(seed)

    for c = 1, length do
        local i = math.random(1, string.len(set))
        local char = string.sub(set, i, i)
        table.insert(captcha_t, char)
        
        if debug_mode then
            print("DEBUG: Character " .. c .. ": " .. char .. 
                 " (index " .. i .. ")")
        end
    end

    if debug_mode then
        print("DEBUG: Generated character array: " .. 
             table.concat(captcha_t))
    end

    return captcha_t
end

-- Generate random angle for character rotation
local function random_angle()
    math.randomseed(urandom())
    return math.random(-20, 40)
end

-- Generate random coordinates for scribble lines
local function scribble(w, h)
    math.randomseed(urandom())
    local x1 = math.random(5, w - 5)
    local x2 = math.random(5, w - 5)
    return x1, x2
end

-- Set the captcha string
function mt.__index:string(s)
    self.cap.string = s
end

-- Set the number of scribble lines
function mt.__index:scribble(n)
    self.cap.scribble = n or 20
end

-- Set the length of the captcha string
function mt.__index:length(l)
    self.cap.length = l
end

-- Set the background color (RGB values)
function mt.__index:bgcolor(r, g, b)
    self.cap.bgcolor = { r = r, g = g, b = b }
end

-- Set the foreground color (RGB values)
function mt.__index:fgcolor(r, g, b)
    self.cap.fgcolor = { r = r, g = g, b = b }
end

-- Enable or disable line drawing
function mt.__index:line(line)
    self.cap.line = line
end

-- Set the font file path
function mt.__index:font(font)
    self.cap.font = font
end

-- Generate the captcha image
function mt.__index:generate()
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        print("DEBUG: Starting captcha generation")
        print("DEBUG: Captcha string: " .. tostring(self.cap.string))
        print("DEBUG: Captcha length: " .. tostring(self.cap.length))
    end
    
    local captcha_t = {}

    if not self.cap.string then
        if not self.cap.length then
            self.cap.length = 6
        end
        
        if debug_mode then
            print("DEBUG: Generating random characters, length: " .. 
                 self.cap.length)
        end
        
        captcha_t = random_char(self.cap.length)
        self:string(table.concat(captcha_t))
        
        if debug_mode then
            print("DEBUG: Generated string: " .. self.cap.string)
        end
    else
        if debug_mode then
            print("DEBUG: Using provided string: " .. self.cap.string)
        end
        
        for i = 1, #self.cap.string do
            table.insert(captcha_t, string.sub(self.cap.string, i, i))
        end
    end

    local image_width = #captcha_t * 40
    local image_height = 45
    
    if debug_mode then
        print("DEBUG: Creating image: " .. image_width .. "x" .. image_height)
    end

    self.im = gd.createTrueColor(image_width, image_height)
    local black = self.im:colorAllocate(0, 0, 0)
    local white = self.im:colorAllocate(255, 255, 255)
    local bgcolor
    if not self.cap.bgcolor then
        bgcolor = white
        if debug_mode then
            print("DEBUG: Using default white background")
        end
    else
        bgcolor = self.im:colorAllocate(self.cap.bgcolor.r, 
                                       self.cap.bgcolor.g, 
                                       self.cap.bgcolor.b)
        if debug_mode then
            print("DEBUG: Using custom background color: " .. 
                 self.cap.bgcolor.r .. "," .. self.cap.bgcolor.g .. "," .. 
                 self.cap.bgcolor.b)
        end
    end

    local fgcolor
    if not self.cap.fgcolor then
        fgcolor = black
        if debug_mode then
            print("DEBUG: Using default black foreground")
        end
    else
        fgcolor = self.im:colorAllocate(self.cap.fgcolor.r, 
                                       self.cap.fgcolor.g, 
                                       self.cap.fgcolor.b)
        if debug_mode then
            print("DEBUG: Using custom foreground color: " .. 
                 self.cap.fgcolor.r .. "," .. self.cap.fgcolor.g .. "," .. 
                 self.cap.fgcolor.b)
        end
    end

    self.im:filledRectangle(0, 0, image_width, image_height, bgcolor)

    local offset_left = 10

    if debug_mode then
        print("DEBUG: Drawing characters")
    end

    for i = 1, #captcha_t do
        local angle = random_angle()
        
        if debug_mode then
            print("DEBUG: Drawing character '" .. captcha_t[i] .. 
                 "' at angle " .. angle)
        end
        
        local llx, lly, lrx, lry, urx, ury, ulx, uly = 
            self.im:stringFT(fgcolor, self.cap.font, 25, 
                           math.rad(angle), offset_left, 35, captcha_t[i])
        self.im:polygon({ { llx, lly }, { lrx, lry }, 
                         { urx, ury }, { ulx, uly } }, bgcolor)
        offset_left = offset_left + 40
    end

    if self.cap.line then
        if debug_mode then
            print("DEBUG: Drawing line decorations")
        end
        
        self.im:line(10, 10, image_width - 10, 40, fgcolor)
        self.im:line(11, 11, image_width - 11, 41, fgcolor)
        self.im:line(12, 12, image_width - 12, 42, fgcolor)
    end

    if self.cap.scribble then
        if debug_mode then
            print("DEBUG: Drawing scribbles, count: " .. self.cap.scribble)
        end
        
        for i = 1, self.cap.scribble do
            local x1, x2 = scribble(image_width, image_height)
            self.im:line(x1, 5, x2, 40, fgcolor)
        end
    end
    
    if debug_mode then
        print("DEBUG: Captcha generation completed")
    end
end

-- Write the generated image to a JPEG file
function mt.__index:jpeg(outfile, quality)
    self.im:jpeg(outfile, quality)
end

-- Write the generated image to a PNG file
function mt.__index:png(outfile)
    self.im:png(outfile)
end

-- Get the image data in PNG format as string
function mt.__index:pngStr()
    return self.im:pngStr()
end

-- Get the image data in JPEG format as string
function mt.__index:jpegStr(quality)
    return self.im:jpegStr(quality)
end

-- Get the captcha text string
function mt.__index:getStr()
    return self.cap.string
end

-- Write the image to a file and return the captcha string
function mt.__index:write(outfile, quality)
    if self.cap.string == nil then
        self:generate()
    end
    self:jpeg(outfile, quality)
    return self:getStr()
end

return _M