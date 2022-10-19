--
-- Open images automatically according to the file magic number.
-- Part of Lua-GD
--


local gd = require("gd")
local io = require("io")

local magics = {
    { "\137PNG", gd.createFromPng },
    { "GIF87a", gd.createFromGif },
    { "GIF89a", gd.createFromGif },
    { "\255\216\255\224\0\16\74\70\73\70\0", gd.createFromJpeg },
    { "\255\216\255\225\19\133\69\120\105\102\0", gd.createFromJpeg },  -- JPEG Exif
 }

--
-- Open some common image types according to the file headers
--
-- Arguments:
--  fname: a string with the file name
--
-- Return values:
--  on success, returns a GD image handler.
--  on error, returns nil followed by a string with the error description.
--

local function openany(fname)
    local fp = io.open(fname, "rb")
    if not fp then
        return nil, "Error opening file"
    end

    local header = fp:read(16)
    if not header then
        return nil, "Error reading file"
    end
    fp:close()

    for _, v in ipairs(magics) do
        if header:sub(1, #v[1]) == v[1] then
            return v[2](fname)
        end
    end

    return nil, "Image type not recognized"
end


return { openany = openany }

