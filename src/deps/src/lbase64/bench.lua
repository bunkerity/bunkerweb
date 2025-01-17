local base64 = require'base64'
local N = 10000000
local st = {}
local letters = ' abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
 .. 'абвгдеёжзийклмнопрстуфхцшщчъыьэюя'
 .. 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦШЩЧЪЫЬЭЮЯ'
local nletters = #letters
for i = 1, N do
	local j = math.random( nletters )
	st[i] = letters:sub( j, j )
end
local s = table.concat( st )
local t = os.clock()
local encoded = base64.encode( s )
local encodetime = os.clock() - t

t = os.clock()
local decoded = base64.decode( encoded )
local decodetime = os.clock() - t

assert( s == decoded )
print('Common text')
print(('Encoding: %d bytes/sec'):format( math.floor(N/encodetime)))
print(('Decoding: %d bytes/sec'):format( math.floor(N/decodetime)))
collectgarbage()

t = os.clock()
encoded = base64.encode( s, nil, true )
encodetime = os.clock() - t

t = os.clock()
decoded = base64.decode( encoded, nil, true )
assert( s == decoded )
decodetime = os.clock() - t
print('Common text (cache)')
print(('Encoding: %d bytes/sec'):format( math.floor(N/encodetime)))
print(('Decoding: %d bytes/sec'):format( math.floor(N/decodetime)))
collectgarbage()

local lt = {}
for i = 0, 255 do
	lt[i] = string.char(i)
end
nletters = #lt
for i = 1, N do
	local j = math.random( nletters )
	st[i] = lt[j]
end
s = table.concat( st )

t = os.clock()
encoded = base64.encode( s, nil )
encodetime = os.clock() - t

t = os.clock()
decoded = base64.decode( encoded )
decodetime = os.clock() - t

assert( s == decoded )
print('Binary')
print(('Encoding: %d bytes/sec'):format( math.floor(N/encodetime)))
print(('Decoding: %d bytes/sec'):format( math.floor(N/decodetime)))
collectgarbage()

t = os.clock()
encoded = base64.encode( s, nil, true )
encodetime = os.clock() - t

t = os.clock()
decoded = base64.decode( encoded, nil, true )
assert( s == decoded )
decodetime = os.clock() - t
print('Binary (cache)')
print(('Encoding: %d bytes/sec'):format( math.floor(N/encodetime)))
print(('Decoding: %d bytes/sec'):format( math.floor(N/decodetime)))
collectgarbage()
