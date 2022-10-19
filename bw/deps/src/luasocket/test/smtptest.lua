local sent = {}

local from = "diego@localhost"
local server = "localhost"
local rcpt = "luasocket@localhost"

local files = {
    "/var/spool/mail/luasocket",
    "/var/spool/mail/luasock1",
    "/var/spool/mail/luasock2",
    "/var/spool/mail/luasock3",
}

local t = socket.time()
local err

dofile("mbox.lua")
local parse = mbox.parse
dofile("testsupport.lua")

local total = function()
    local t = 0
    for i = 1, #sent do
        t = t + sent[i].count
    end
    return t
end

local similar = function(s1, s2)
    return 
    string.lower(string.gsub(s1, "%s", "")) == 
    string.lower(string.gsub(s2, "%s", ""))
end

local fail = function(s)
    s = s or "failed!"
    print(s)
    os.exit()
end

local readfile = function(name)
    local f = io.open(name, "r")
    if not f then 
        fail("unable to open file!")
        return nil 
    end
    local s = f:read("*a")
    f:close()
    return s
end

local empty = function()
    for i,v in ipairs(files) do
        local f = io.open(v, "w")
        if not f then 
            fail("unable to open file!")
        end
        f:close()
    end
end

local get = function()
    local s = ""
    for i,v in ipairs(files) do
        s = s .. "\n" .. readfile(v)
    end
    return s
end

local check_headers = function(sent, got)
    sent = sent or {}
    got = got or {}
    for i,v in pairs(sent) do
        if not similar(v, got[i]) then fail("header " .. v .. "failed!") end
    end
end

local check_body = function(sent, got)
    sent = sent or ""
    got = got or ""
    if not similar(sent, got) then fail("bodies differ!") end
end

local check = function(sent, m)
    io.write("checking ", m.headers.title, ": ")
    for i = 1, #sent do
        local s = sent[i]
        if s.title == m.headers.title and s.count > 0 then
            check_headers(s.headers, m.headers)
            check_body(s.body, m.body)
            s.count = s.count - 1
            print("ok")
            return
        end
    end
    fail("not found")
end

local insert = function(sent, message)
    if type(message.rcpt) == "table" then
        message.count = #message.rcpt
    else message.count = 1 end
    message.headers = message.headers or {}
    message.headers.title = message.title
    table.insert(sent, message)
end

local mark = function()
    local time = socket.time()
    return { time = time }
end

local wait = function(sentinel, n)
    local to
    io.write("waiting for ", n, " messages: ")
    while 1 do
        local mbox = parse(get())
        if n == #mbox then break end
        if socket.time() - sentinel.time > 50 then 
            to = 1 
            break
        end
        socket.sleep(1)
        io.write(".")
        io.stdout:flush()
    end
    if to then fail("timeout")
    else print("ok") end
end

local stuffed_body = [[
This message body needs to be
stuffed because it has a dot
.
by itself on a line. 
Otherwise the mailer would
think that the dot
.
is the end of the message
and the remaining text would cause
a lot of trouble.
]]

insert(sent, {
    from = from,
    rcpt = {
        "luasocket@localhost",
        "luasock3@dell-diego.cs.princeton.edu",
        "luasock1@dell-diego.cs.princeton.edu"
    },
    body = "multiple rcpt body",
    title = "multiple rcpt",
})

insert(sent, {
    from = from,
    rcpt = {
        "luasock2@localhost",
        "luasock3",
        "luasock1"
    },
    headers = {
        header1 = "header 1",
        header2 = "header 2",
        header3 = "header 3",
        header4 = "header 4",
        header5 = "header 5",
        header6 = "header 6",
    },
    body = stuffed_body,
    title = "complex message",
})

insert(sent, {
    from = from,
    rcpt = rcpt,
    server = server,
    body = "simple message body",
    title = "simple message"
})

insert(sent, {
    from = from,
    rcpt = rcpt,
    server = server,
    body = stuffed_body,
    title = "stuffed message body"
})

insert(sent, {
    from = from,
    rcpt = rcpt,
    headers = {
        header1 = "header 1",
        header2 = "header 2",
        header3 = "header 3",
        header4 = "header 4",
        header5 = "header 5",
        header6 = "header 6",
    },
    title = "multiple headers"
})

insert(sent, {
    from = from,
    rcpt = rcpt,
    title = "minimum message"
})

io.write("testing host not found: ")
local c, e = socket.connect("wrong.host", 25)
local ret, err = socket.smtp.mail{
    from = from,
    rcpt = rcpt,
    server = "wrong.host"
}
if ret or e ~= err then fail("wrong error message")
else print("ok") end

io.write("testing invalid from: ")
local ret, err = socket.smtp.mail{
    from = ' " " (( _ * ', 
    rcpt = rcpt,
}
if ret or not err then fail("wrong error message")
else print(err) end

io.write("testing no rcpt: ")
local ret, err = socket.smtp.mail{
    from = from, 
}
if ret or not err then fail("wrong error message")
else print(err) end

io.write("clearing mailbox: ")
empty()
print("ok")

io.write("sending messages: ")
for i = 1, #sent do
    ret, err = socket.smtp.mail(sent[i])
    if not ret then fail(err) end
    io.write("+")
    io.stdout:flush()
end
print("ok")

wait(mark(), total())

io.write("parsing mailbox: ")
local mbox = parse(get())
print(#mbox .. " messages found!")

for i = 1, #mbox do
    check(sent, mbox[i])
end

print("passed all tests")
print(string.format("done in %.2fs", socket.time() - t))
