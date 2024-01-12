local path = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
package.path = path .. "/?.lua;" .. package.path

local test = require "framework".test
local write_seperator = require "framework".write_seperator
local pkey = require "resty.openssl.pkey"
local example_pkey = assert(pkey.new())

for _, t in ipairs({"PEM", "DER", "JWK"}) do
    for _, op in ipairs({"load", "export"}) do 
        for _, p in ipairs({"public", "private"}) do
            
            if op == "load" then
                local txt = assert(example_pkey:tostring(p, t))
                local opts = {
                    format = t,
                }
                if t ~= "JWK" then
                    opts.type = p == "public" and "pu" or "pr"
                end

                test("load " .. t .. " " .. p .. " key", function()
                    return pkey.new(txt, opts)
                end)

            else
                test("export " .. t .. " " .. p .. " key", function()
                    return example_pkey:tostring(p, t)
                end)
            end

       end
    end

    write_seperator()
end
