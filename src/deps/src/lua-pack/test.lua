local pack = require"lua_pack"

local bpack = pack.pack
local bunpack = pack.unpack

function hex(s)
 s=string.gsub(s,"(.)",function (x) return string.format("%02X",string.byte(x)) end)
 return s
end

a=bpack("AC8","\027Lua",5*16+1,0,1,4,4,4,8,0)
print(hex(a),string.len(a))

b=string.dump(hex)
b=string.sub(b,1,string.len(a))
print(a==b,string.len(b))
print(bunpack(b,"CA3C8"))

i=314159265 f="<I>I=I"
a=bpack(f,i,i,i)
print(hex(a))
print(bunpack(a,f))

i=3.14159265 f="<d>d=d"
a=bpack(f,i,i,i)
print(hex(a))
print(bunpack(a,f))
