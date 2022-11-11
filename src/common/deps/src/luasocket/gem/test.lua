function readfile(n)
    local f = io.open(n, "rb")
    local s = f:read("*a")
    f:close()
    return s
end

lf = readfile("t1lf.txt")
os.remove("t1crlf.txt")
os.execute("lua t1.lua < t1lf.txt > t1crlf.txt")
crlf = readfile("t1crlf.txt")
assert(crlf == string.gsub(lf, "\010", "\013\010"), "broken")

gt = readfile("t2gt.qp")
os.remove("t2.qp")
os.execute("lua t2.lua < t2.txt > t2.qp")
t2 = readfile("t2.qp")
assert(gt == t2, "broken")

os.remove("t1crlf.txt")
os.execute("lua t3.lua < t1lf.txt > t1crlf.txt")
crlf = readfile("t1crlf.txt")
assert(crlf == string.gsub(lf, "\010", "\013\010"), "broken")

t = readfile("test.lua")
os.execute("lua t4.lua < test.lua > t")
t2 = readfile("t")
assert(t == t2, "broken")

os.remove("output.b64")
gt = readfile("gt.b64")
os.execute("lua t5.lua")
t5 = readfile("output.b64")
assert(gt == t5, "failed")

print("1 2 5 6 10 passed")
print("2 3 4 5 6 10 passed")
print("2 5 6 7 8 10 passed")
print("5 9 passed")
print("5 6 10 11 passed")

os.remove("t")
os.remove("t2.qp")
os.remove("t1crlf.txt")
os.remove("t11.b64")
os.remove("output.b64")
