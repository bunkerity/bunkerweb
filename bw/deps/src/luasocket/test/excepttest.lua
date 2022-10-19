local socket = require("socket")

local finalizer_called

local func = socket.protect(function(err, ...)
    local try = socket.newtry(function()
        finalizer_called = true
    end)

    if err then
        return error(err, 0)
    else
        return try(...)
    end
end)

local ret1, ret2, ret3 = func(false, 1, 2, 3)
assert(not finalizer_called, "unexpected finalizer call")
assert(ret1 == 1 and ret2 == 2 and ret3 == 3, "incorrect return values")

ret1, ret2, ret3 = func(false, false, "error message")
assert(finalizer_called, "finalizer not called")
assert(ret1 == nil and ret2 == "error message" and ret3 == nil, "incorrect return values")

local err = {key = "value"}
ret1, ret2 = pcall(func, err)
assert(not ret1, "error not rethrown")
assert(ret2 == err, "incorrect error rethrown")

print("OK")
