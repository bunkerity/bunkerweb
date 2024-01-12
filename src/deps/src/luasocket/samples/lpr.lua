local lp = require("socket.lp")

local function usage()
  print('\nUsage: lua lpr.lua [filename] [keyword=val...]\n')
  print('Valid keywords are :')
  print(
     '  host=remote host or IP address (default "localhost")\n' ..
     '  queue=remote queue or printer name (default "printer")\n' ..
     '  port=remote port number (default 515)\n' ..
     '  user=sending user name\n' ..
     '  format=["binary" | "text" | "ps" | "pr" | "fortran"] (default "binary")\n' ..
     '  banner=true|false\n' ..
     '  indent=number of columns to indent\n' ..
     '  mail=email of address to notify when print is complete\n' ..
     '  title=title to use for "pr" format\n' ..
     '  width=width for "text" or "pr" formats\n' ..
     '  class=\n' ..
     '  job=\n' ..
     '  name=\n' ..
     '  localbind=true|false\n'
     )
  return nil
end

if not arg or not arg[1] then
  return usage()
end

do
    local opt = {}
    local pat = "[%s%c%p]*([%w]*)=([\"]?[%w%s_!@#$%%^&*()<>:;]+[\"]?.?)"
    for i = 2, #arg, 1 do
      string.gsub(arg[i], pat, function(name, value) opt[name] = value end)
    end
    if not arg[2] then
      return usage()
    end
    if arg[1] ~= "query" then
        opt.file = arg[1]
        r,e=lp.send(opt)
        io.stdout:write(tostring(r or e),'\n')
    else
        r,e=lp.query(opt)
        io.stdout:write(tostring(r or e), '\n')
    end
end

-- trivial tests
--lua lp.lua lp.lua queue=default host=localhost
--lua lp.lua lp.lua queue=default host=localhost format=binary localbind=1
--lua lp.lua query queue=default host=localhost
