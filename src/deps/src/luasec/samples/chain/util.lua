local print  = print
local ipairs = ipairs

local _ENV = {}

function _ENV.show(cert)
  print("Serial:", cert:serial())
  print("NotBefore:", cert:notbefore())
  print("NotAfter:", cert:notafter())
  print("--- Issuer ---")
  for k, v in ipairs(cert:issuer()) do
    print(v.name .. " = " .. v.value)
  end

  print("--- Subject ---")
  for k, v in ipairs(cert:subject()) do
    print(v.name .. " = " .. v.value)
  end
  print("----------------------------------------------------------------------")
end

return _ENV
