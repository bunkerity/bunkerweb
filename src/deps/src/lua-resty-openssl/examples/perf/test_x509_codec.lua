local path = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
package.path = path .. "/?.lua;" .. package.path

local test = require "framework".test
local write_seperator = require "framework".write_seperator
local x509 = require "resty.openssl.x509"
local cert = assert(io.open(path .. "../../t/fixtures/Github.pem")):read("*a")
local example_x509 = assert(x509.new(cert))

for _, t in ipairs({"PEM", "DER"}) do
    for _, op in ipairs({"load", "export"}) do 
        if op == "load" then
            local txt = assert(example_x509:tostring(t))
            test("load " .. t .. " x509", function()
                return x509.new(txt, t)
            end)

        else
            test("export " .. t .. " x509", function()
                return example_x509:tostring(t)
            end)
        end
    end

    write_seperator()
end
