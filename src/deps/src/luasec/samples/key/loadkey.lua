--
-- Public domain
--
local ssl = require("ssl")

local pass = "foobar"
local cfg = {
  protocol = "tlsv1",
  mode = "client",
  key = "key.pem",
}

-- Shell
print(string.format("*** Hint: password is '%s' ***", pass))
ctx, err = ssl.newcontext(cfg)
assert(ctx, err)
print("Shell: ok")

-- Text password
cfg.password = pass
ctx, err = ssl.newcontext(cfg)
assert(ctx, err)
print("Text: ok")

-- Callback
cfg.password = function() return pass end
ctx, err = ssl.newcontext(cfg)
assert(ctx, err)
print("Callback: ok")
