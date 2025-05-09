local bit
if _VERSION == "Lua 5.1" then bit = require "bit" else bit = require "bit32" end

local M = {_TYPE='module', _NAME='flag.funcs', _VERSION='1.0-0'}

M.BOUNCER_SOURCE = 0x1
M.APPSEC_SOURCE = 0x2
M.VERIFY_STATE = 0x4
M.VALIDATED_STATE = 0x8

M.Flags = {}
M.Flags[0x0] = ""
M.Flags[0x1] = "bouncer"
M.Flags[0x2] = "appsec"
M.Flags[0x4] = "to_verify"
M.Flags[0x8] = "validated"


function M.GetFlags(flags)
  local source = 0x0
  local err = ""
  local state = 0x0

  if flags == nil then
    return source, state, err
  end

  if bit.band(flags, M.BOUNCER_SOURCE) ~= 0 then
    source = M.BOUNCER_SOURCE
  elseif bit.band(flags, M.APPSEC_SOURCE) ~= 0 then
    source = M.APPSEC_SOURCE
  end

  if bit.band(flags, M.VERIFY_STATE) ~= 0 then
    state = M.VERIFY_STATE
  elseif bit.band(flags, M.VALIDATED_STATE) ~= 0 then
    state = M.VALIDATED_STATE
  end
  return source, state, err

end

return M
