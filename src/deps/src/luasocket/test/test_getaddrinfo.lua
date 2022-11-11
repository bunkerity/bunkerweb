local socket = require "socket"
local addresses = assert(socket.dns.getaddrinfo("localhost"))
assert(type(addresses) == 'table')

local ipv4mask = "^%d%d?%d?%.%d%d?%d?%.%d%d?%d?%.%d%d?%d?$"

for i, alt in ipairs(addresses) do
  if alt.family == 'inet' then
    assert(type(alt.addr) == 'string')
    assert(alt.addr:find(ipv4mask))
    assert(alt.addr == '127.0.0.1')
  end
end

print("done!")
