-- Copyright startx <startx@plentyfact.org>
-- Modifications copyright mrDoctorWho <mrdoctorwho@gmail.com>
-- Published under the MIT license

local _M = {}

local gd = require 'gd'

local mt = { __index = {} }


function _M.new()
	local cap = {}
	local f = setmetatable({ cap = cap}, mt)
	return f
end


local function urandom()
	local seed = 1
	local devurandom = io.open("/dev/urandom", "r")
	local urandom = devurandom:read(32)
	devurandom:close()

	for i=1,string.len(urandom) do
		local s = string.byte(urandom,i)
		seed = seed + s
	end
	return seed
end


local function random_char(length)
	local set, char, uid
	-- local set = [[1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]]
	local set = [[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]]
	local captcha_t = {}

	math.randomseed(urandom())
	
	for c=1,length do
		 local i = math.random(1, string.len(set))
		 table.insert(captcha_t, string.sub(set,i,i))
	end

	return captcha_t
end


local function random_angle()
	math.randomseed(urandom())
	return math.random(-20, 40) 
end


local function scribble(w,h)
	math.randomseed(urandom())
	local x1 = math.random(5, w - 5)
	local x2 = math.random(5, w - 5)
	return x1, x2
end


function mt.__index:string(s)
	self.cap.string = s
end

function mt.__index:scribble(n)
	self.cap.scribble = n or 20
end

function mt.__index:length(l)
	self.cap.length = l
end


function mt.__index:bgcolor(r,g,b)
	self.cap.bgcolor = { r = r , g = g , b = b}
end

function mt.__index:fgcolor(r,g,b)
	self.cap.fgcolor = { r = r , g = g , b = b}
end

function mt.__index:line(line)
	self.cap.line = line
end


function mt.__index:font(font)
	self.cap.font = font 
end


function mt.__index:generate()
	--local self.captcha = {}
	local captcha_t = {}

	if not self.cap.string then
		 if not self.cap.length then
			self.cap.length = 6
		 end
		 captcha_t = random_char(self.cap.length)
		 self:string(table.concat(captcha_t))
	else
		 for i=1, #self.cap.string do
			table.insert(captcha_t, string.sub(self.cap.string, i, i))
		 end
	end


	self.im = gd.createTrueColor(#captcha_t * 40, 45)
	local black = self.im:colorAllocate(0, 0, 0)
	local white = self.im:colorAllocate(255, 255, 255)
	local bgcolor
	if not self.cap.bgcolor then
		 bgcolor = white
	else
		 bgcolor = self.im:colorAllocate(self.cap.bgcolor.r , self.cap.bgcolor.g, self.cap.bgcolor.b )
	end

	local fgcolor
	if not self.cap.fgcolor then
		fgcolor = black
	else
		fgcolor = self.im:colorAllocate(self.cap.fgcolor.r , self.cap.fgcolor.g, self.cap.fgcolor.b )
	end

	self.im:filledRectangle(0, 0, #captcha_t * 40, 45, bgcolor)
	
	local offset_left = 10

	for i=1, #captcha_t do
		local angle = random_angle()
		local llx, lly, lrx, lry, urx, ury, ulx, uly = self.im:stringFT(fgcolor, self.cap.font, 25, math.rad(angle), offset_left, 35, captcha_t[i])
		self.im:polygon({ {llx, lly}, {lrx, lry}, {urx, ury}, {ulx, uly} }, bgcolor)
		offset_left = offset_left + 40
	end

	if self.cap.line then
		self.im:line(10, 10, ( #captcha_t * 40 ) - 10  , 40, fgcolor)
		self.im:line(11, 11, ( #captcha_t * 40 ) - 11  , 41, fgcolor)
		self.im:line(12, 12, ( #captcha_t * 40 ) - 12  , 42, fgcolor)
	end


	if self.cap.scribble then
		for i=1,self.cap.scribble do
			local x1,x2 = scribble( #captcha_t * 40 , 45 )
			self.im:line(x1, 5, x2, 40, fgcolor)
		end
	end
end


-- Perhaps it's not the best solution
-- Writes the generated image to a jpeg file
function mt.__index:jpeg(outfile, quality)
	self.im:jpeg(outfile, quality)
end

-- Writes the generated image to a png file
function mt.__index:png(outfile)
	self.im:png(outfile)
end

-- Allows to get the image data in PNG format
function mt.__index:pngStr()
	return self.im:pngStr()
end

-- Allows to get the image data in JPEG format
function mt.__index:jpegStr(quality)
	return self.im:jpegStr(quality)
end

-- Allows to get the image text
function mt.__index:getStr()
	return self.cap.string
end

-- Writes the image to a file
function mt.__index:write(outfile, quality)
	if self.cap.string == nil then
		self:generate()
	end
	self:jpeg(outfile, quality)
	-- Compatibility
	return self:getStr()
end

return _M