------------------------------------------------------------------------------
-- DynASM s390x module.
--
-- Copyright (C) 2005-2017 Mike Pall. All rights reserved.
-- See dynasm.lua for full copyright notice.
------------------------------------------------------------------------------

-- Module information:
local _info = {
  arch =	"s390x",
  description =	"DynASM s390x module",
  version =	"1.4.0",
  vernum =	 10400,
  release =	"2015-10-18",
  author =	"Mike Pall",
  license =	"MIT",
}

-- Exported glue functions for the arch-specific module.
local _M = { _info = _info }

-- Cache library functions.
local type, tonumber, pairs, ipairs = type, tonumber, pairs, ipairs
local assert, setmetatable, rawget = assert, setmetatable, rawget
local _s = string
local sub, format, byte, char = _s.sub, _s.format, _s.byte, _s.char
local match, gmatch, gsub = _s.match, _s.gmatch, _s.gsub
local concat, sort, insert = table.concat, table.sort, table.insert
local bit = bit or require("bit")
local band, shl, shr, sar = bit.band, bit.lshift, bit.rshift, bit.arshift
local ror, tohex = bit.ror, bit.tohex

-- Inherited tables and callbacks.
local g_opt, g_arch
local wline, werror, wfatal, wwarn

-- Action name list.
-- CHECK: Keep this in sync with the C code!
local action_names = {
  "STOP", "SECTION", "ESC", "REL_EXT",
  "ALIGN", "REL_LG", "LABEL_LG",
  "REL_PC", "LABEL_PC", "DISP12", "DISP20", "IMM8", "IMM16", "IMM32", "LEN8R","LEN4HR","LEN4LR",
}

-- Maximum number of section buffer positions for dasm_put().
-- CHECK: Keep this in sync with the C code!
local maxsecpos = 25 -- Keep this low, to avoid excessively long C lines.

-- Action name -> action number.
local map_action = {}
local max_action = 0
for n, name in ipairs(action_names) do
  map_action[name] = n-1
  max_action = n
end

-- Action list buffer.
local actlist = {}

-- Argument list for next dasm_put(). Start with offset 0 into action list.
local actargs = { 0 }

-- Current number of section buffer positions for dasm_put().
local secpos = 1

------------------------------------------------------------------------------

-- Dump action names and numbers.
local function dumpactions(out)
  out:write("DynASM encoding engine action codes:\n")
  for n, name in ipairs(action_names) do
    local num = map_action[name]
    out:write(format("  %-10s %02X  %d\n", name, num, num))
  end
  out:write("\n")
end

local function havearg(a)
  return a == "ESC" or
         a == "SECTION" or
         a == "REL_LG" or
         a == "LABEL_LG" or
         a == "REL_EXT"
end

-- Write action list buffer as a huge static C array.
local function writeactions(out, name)
  local nn = #actlist
  if nn == 0 then nn = 1; actlist[0] = map_action.STOP end
  out:write("static const unsigned short ", name, "[", nn, "] = {")
  local esc = false -- also need to escape for action arguments
  for i = 1, nn do
    assert(out:write("\n  0x", sub(tohex(actlist[i]), 5, 8)))
    if i ~= nn then assert(out:write(",")) end
    local name = action_names[actlist[i]+1]
    if not esc and name then
      assert(out:write(" /* ", name, " */"))
      esc = havearg(name)
    else
      esc = false
    end
  end
  assert(out:write("\n};\n\n"))
end

------------------------------------------------------------------------------

-- Add halfword to action list.
local function wputxhw(n)
  assert(n >= 0 and n <= 0xffff, "halfword out of range")
  actlist[#actlist+1] = n
end

-- Add action to list with optional arg. Advance buffer pos, too.
local function waction(action, val, a, num)
  local w = assert(map_action[action], "bad action name `"..action.."'")
  wputxhw(w)
  if val then wputxhw(val) end -- Not sure about this, do we always have one arg?
  if a then actargs[#actargs+1] = a end
  if val or a or num then secpos = secpos + (num or 1) end
end

-- Flush action list (intervening C code or buffer pos overflow).
local function wflush(term)
  if #actlist == actargs[1] then return end -- Nothing to flush.
  if not term then waction("STOP") end -- Terminate action list.
  wline(format("dasm_put(Dst, %s);", concat(actargs, ", ")), true)
  actargs = { #actlist } -- Actionlist offset is 1st arg to next dasm_put().
  secpos = 1 -- The actionlist offset occupies a buffer position, too.
end

-- Put escaped halfword.
local function wputhw(n)
  if n <= max_action then waction("ESC") end
  wputxhw(n)
end

-- Reserve position for halfword.
local function wpos()
  local pos = #actlist+1
  actlist[pos] = ""
  return pos
end

------------------------------------------------------------------------------

-- Global label name -> global label number. With auto assignment on 1st use.
local next_global = 20
local map_global = setmetatable({}, { __index = function(t, name)
  if not match(name, "^[%a_][%w_]*$") then werror("bad global label") end
  local n = next_global
  if n > 2047 then werror("too many global labels") end
  next_global = n + 1
  t[name] = n
  return n
end})

-- Dump global labels.
local function dumpglobals(out, lvl)
  local t = {}
  for name, n in pairs(map_global) do t[n] = name end
  out:write("Global labels:\n")
  for i=20, next_global-1 do
    out:write(format("  %s\n", t[i]))
  end
  out:write("\n")
end

-- Write global label enum.
local function writeglobals(out, prefix)
  local t = {}
  for name, n in pairs(map_global) do t[n] = name end
  out:write("enum {\n")
  for i=20, next_global-1 do
    out:write("  ", prefix, t[i], ",\n")
  end
  out:write("  ", prefix, "_MAX\n};\n")
end

-- Write global label names.
local function writeglobalnames(out, name)
  local t = {}
  for name, n in pairs(map_global) do t[n] = name end
  out:write("static const char *const ", name, "[] = {\n")
  for i=20, next_global-1 do
    out:write("  \"", t[i], "\",\n")
  end
  out:write("  (const char *)0\n};\n")
end

------------------------------------------------------------------------------

-- Extern label name -> extern label number. With auto assignment on 1st use.
local next_extern = 0
local map_extern_ = {}
local map_extern = setmetatable({}, { __index = function(t, name)
  -- No restrictions on the name for now.
  local n = next_extern
  if n > 2047 then werror("too many extern labels") end
  next_extern = n + 1
  t[name] = n
  map_extern_[n] = name
  return n
end})

-- Dump extern labels.
local function dumpexterns(out, lvl)
  out:write("Extern labels:\n")
  for i=0, next_extern-1 do
    out:write(format("  %s\n", map_extern_[i]))
  end
  out:write("\n")
end

-- Write extern label names.
local function writeexternnames(out, name)
  out:write("static const char *const ", name, "[] = {\n")
  for i=0, next_extern-1 do
    out:write("  \"", map_extern_[i], "\",\n")
  end
  out:write("  (const char *)0\n};\n")
end

------------------------------------------------------------------------------

-- Arch-specific maps.
-- Ext. register name -> int. name.
local map_archdef = { sp = "r15" }

-- Int. register name -> ext. name.
local map_reg_rev = { r15 = "sp" }

local map_type = {}		-- Type name -> { ctype, reg }
local ctypenum = 0		-- Type number (for Dt... macros).

-- Reverse defines for registers.
function _M.revdef(s)
  return map_reg_rev[s] or s
end

local map_cond = {
  o = 1, h = 2, nle = 3, l = 4,
  nhe = 5, lh = 6, ne = 7, e = 8,
  nlh = 9, he = 10, nl = 11, le = 12,
  nh = 13, no = 14, [""] = 15,
}

------------------------------------------------------------------------------

local function parse_reg(expr)
  if not expr then werror("expected register name") end
  local tname, ovreg = match(expr, "^([%w_]+):(r1?%d)$")
  local tp = map_type[tname or expr]
  if tp then
    local reg = ovreg or tp.reg
    if not reg then
      werror("type `"..(tname or expr).."' needs a register override")
    end
    expr = reg
  end
  local r = match(expr, "^[rf](1?%d)$")
  if r then
    r = tonumber(r)
    if r <= 15 then return r, tp end
  end
  werror("bad register name `"..expr.."'")
end

local parse_ctx = {}

local loadenv = setfenv and function(s)
  local code = loadstring(s, "")
  if code then setfenv(code, parse_ctx) end
  return code
end or function(s)
  return load(s, "", nil, parse_ctx)
end

-- Try to parse simple arithmetic, too, since some basic ops are aliases.
local function parse_number(n)
  local x = tonumber(n)
  if x then return x end
  local code = loadenv("return "..n)
  if code then
    local ok, y = pcall(code)
    if ok then return y end
  end
  return nil
end

local function is_uint12(num)
  return 0 <= num and num < 4096
end

local function is_int20(num)
  return -shl(1, 19) <= num and num < shl(1, 19)
end

local function is_int32(num)
  return -2147483648 <= num and num < 2147483648
end

local function is_uint16(num)
  return 0 <= num and num < 0xffff
end

local function is_int16(num)
  return -32768 <= num and num < 32768
end

local function is_int8(num)
  return -128 <= num and num < 128
end

local function is_uint8(num)
  return 0 <= num and num < 256
end

-- Split a memory operand of the form d(b) or d(x,b) into d, x and b.
-- If x is not specified then it is 0.
local function split_memop(arg)
  local reg = "[%w_:]+"
  local d, x, b = match(arg, "^(.*)%(%s*("..reg..")%s*,%s*("..reg..")%s*%)$")
  if d then
    return d, parse_reg(x), parse_reg(b)
  end
  local d, b = match(arg, "^(.*)%(%s*("..reg..")%s*%)$")
  if d then
    return d, 0, parse_reg(b)
  end
  -- Assume the two registers are passed as "(r1,r2)", and displacement(d) is not specified. TODO: not sure if we want to do this, GAS doesn't.
  local x, b = match(arg,"%(%s*("..reg..")%s*,%s*("..reg..")%s*%)$")
  if b then
    return 0, parse_reg(x), parse_reg(b)
  end
  -- Accept a lone integer as a displacement. TODO: allow expressions/variables here? Interacts badly with the other rules currently.
  local d = match(arg,"^(-?[%d]+)$")
  if d then
    return d, 0, 0
  end
  local reg, tailr = match(arg, "^([%w_:]+)%s*(.*)$")
  if reg then
    local r, tp = parse_reg(reg)
    if tp then
      return format(tp.ctypefmt, tailr), 0, r
    end
  end
  werror("bad memory operand: "..arg)
  return nil
end

-- Parse memory operand of the form d(x, b) where 0 <= d < 4096 and b and x
-- are GPRs.
-- If the fourth return value is not-nil then it needs to be called to
-- insert an action.
-- Encoded as: xbddd
local function parse_mem_bx(arg)
  local d, x, b = split_memop(arg)
  local dval = tonumber(d)
  if dval then
    if not is_uint12(dval) then
      werror("displacement out of range: ", dval)
    end
    return dval, x, b, nil
  end
  if match(d, "^[rf]1?[0-9]?") then
    werror("expected immediate operand, got register")
  end
  return 0, x, b, function() waction("DISP12", nil, d) end
end

-- Parse memory operand of the form d(b) where 0 <= d < 4096 and b is a GPR.
-- Encoded as: bddd
local function parse_mem_b(arg)
  local d, x, b, a = parse_mem_bx(arg)
  if x ~= 0 then
    werror("unexpected index register")
  end
  return d, b, a
end

-- Parse memory operand of the form d(x, b) where -(2^20)/2 <= d < (2^20)/2
-- and b and x are GPRs.
-- Encoded as: xblllhh (ls are the low-bits of d, and hs are the high bits).
local function parse_mem_bxy(arg)
  local d, x, b = split_memop(arg)
  local dval = tonumber(d)
  if dval then
    if not is_int20(dval) then
      werror("displacement out of range: ", dval)
    end
    return dval, x, b, nil
  end
  if match(d, "^[rf]1?[0-9]?") then
    werror("expected immediate operand, got register")
  end
  return 0, x, b, function() waction("DISP20", nil, d) end
end

-- Parse memory operand of the form d(b) where -(2^20)/2 <= d < (2^20)/2 and
-- b is a GPR.
-- Encoded as: blllhh (ls are the low-bits of d, and hs are the high bits).
local function parse_mem_by(arg)
  local d, x, b, a = parse_mem_bxy(arg)
  if x ~= 0 then
    werror("unexpected index register")
  end
  return d, b, a
end

-- Parse memory operand of the form d(l, b) where 0 <= d < 4096, 1 <= l <= 256,
-- and b is a GPR.
local function parse_mem_lb(arg)
  local reg = "r1?[0-9]"
  local d, l, b = match(arg, "^(.*)%s*%(%s*(.*)%s*,%s*("..reg..")%s*%)$")
  if not d then
    -- TODO: handle values without registers?
    -- TODO: handle registers without a displacement?
    werror("bad memory operand: "..arg)
    return nil
  end
  local dval = tonumber(d)
  local dact = nil
  if dval then
    if not is_uint12(dval) then
      werror("displacement out of range: ", dval)
    end
  else
    dval = 0
    dact = function() waction("DISP12", nil, d) end
  end
  local lval = tonumber(l)
  local lact = nil
  if lval then
    if lval < 1 or lval > 256 then
      werror("length out of range: ", dval)
    end
    lval = lval - 1
  else
    lval = 0
    lact = function() waction("LEN8R", nil, l) end
  end
  return dval, lval, parse_reg(b), dact, lact
end

local function parse_mem_l2b(arg, high_l)
  local reg = "r1?[0-9]"
  local d, l, b = match(arg, "^(.*)%s*%(%s*(.*)%s*,%s*("..reg..")%s*%)$")
  if not d then
    -- TODO: handle values without registers?
    -- TODO: handle registers without a displacement?
    werror("bad memory operand: "..arg)
    return nil
  end
  local dval = tonumber(d)
  local dact = nil
  if dval then
    if not is_uint12(dval) then
      werror("displacement out of range: ", dval)
    end
  else
    dval = 0
    dact = function() waction("DISP12", nil, d) end
  end
  local lval = tonumber(l)
  local lact = nil
  if lval then
    if lval < 1 or lval > 128 then
      werror("length out of range: ", dval)
    end
    lval = lval - 1
  else
    lval = 0
    if high_l then
    lact = function() waction("LEN4HR", nil, l) end
    else
    lact = function() waction("LEN4LR", nil, l) end
    end
  end
  return dval, lval, parse_reg(b), dact, lact
end

local function parse_imm32(imm)
  local imm_val = tonumber(imm)
  if imm_val then
    if not is_int32(imm_val) then
      werror("immediate value out of range: ", imm_val)
    end
    wputhw(band(shr(imm_val, 16), 0xffff))
    wputhw(band(imm_val, 0xffff))
  elseif match(imm, "^[rfv]([1-3]?[0-9])$") or
	 match(imm, "^([%w_]+):(r1?[0-9])$") then
    werror("expected immediate operand, got register")
  else
    waction("IMM32", nil, imm) -- if we get label
  end
end

local function parse_imm16(imm)
  local imm_val = tonumber(imm)
  if imm_val then
    if not is_int16(imm_val) and not is_uint16(imm_val) then
      werror("immediate value out of range: ", imm_val)
    end
    wputhw(band(imm_val, 0xffff))
  elseif match(imm, "^[rfv]([1-3]?[0-9])$") or
	 match(imm, "^([%w_]+):(r1?[0-9])$") then
    werror("expected immediate operand, got register")
  else
    waction("IMM16", nil, imm)
  end
end

local function parse_imm8(imm)
  local imm_val = tonumber(imm)
  if imm_val then
    if not is_int8(imm_val) and not is_uint8(imm_val) then
      werror("Immediate value out of range: ", imm_val)
    end
    return imm_val, nil
  end
  return 0, function() waction("IMM8", nil, imm) end
end

local function parse_mask(mask)
  local m3 = parse_number(mask)
  if m3 then
    if ((m3 == 1) or (m3 == 0) or ( m3 >=3 and m3 <=7)) then
      return m3
    else
      werror("Mask value should be 0,1 or 3-7: ", m3)
    end
  end
end

local function parse_mask2(mask)
  local m4 = parse_number(mask)
  if ( m4 >=0 and m4 <=1) then
    return m4
  else
    werror("Mask value should be 0 or 1: ", m4)
  end
end

local function parse_label(label, def)
  local prefix = sub(label, 1, 2)
  -- =>label (pc label reference)
  if prefix == "=>" then
    return "PC", 0, sub(label, 3)
  end
  -- ->name (global label reference)
  if prefix == "->" then
    return "LG", map_global[sub(label, 3)]
  end
  if def then
    -- [1-9] (local label definition)
    if match(label, "^[1-9]$") then
      return "LG", 10+tonumber(label)
    end
  else
    -- [<>][1-9] (local label reference)
    local dir, lnum = match(label, "^([<>])([1-9])$")
    if dir then -- Fwd: 1-9, Bkwd: 11-19.
      return "LG", lnum + (dir == ">" and 0 or 10)
    end
    -- extern label (extern label reference)
    local extname = match(label, "^extern%s+(%S+)$")
    if extname then
      return "EXT", map_extern[extname]
    end
  end
  werror("bad label `"..label.."'")
end

------------------------------------------------------------------------------

local map_op, op_template

local function op_alias(opname, f)
  return function(params, nparams)
    if not params then return "-> "..opname:sub(1, -3) end
    f(params, nparams)
    op_template(params, map_op[opname], nparams)
  end
end

-- Template strings for s390x instructions.
map_op = {
  a_2 =		"00005a000000RX-a",
  ad_2 =	"00006a000000RX-a",
  adb_2 =	"ed000000001aRXE",
  adbr_2 =	"0000b31a0000RRE",
  adr_2 =	"000000002a00RR",
  ae_2 =	"00007a000000RX-a",
  aeb_2 =	"ed000000000aRXE",
  aebr_2 =	"0000b30a0000RRE",
  aer_2 =	"000000003a00RR",
  afi_2 =	"c20900000000RIL-a",
  ag_2 =	"e30000000008RXY-a",
  agf_2 =	"e30000000018RXY-a",
  agfi_2 =	"c20800000000RIL-a",
  agfr_2 =	"0000b9180000RRE",
  aghi_2 =	"0000a70b0000RI-a",
  agr_2 =	"0000b9080000RRE",
  ah_2 =	"00004a000000RX-a",
  ahi_2 =	"0000a70a0000RI-a",
  ahy_2 =	"e3000000007aRXY-a",
  aih_2 =	"cc0800000000RIL-a",
  al_2 =	"00005e000000RX-a",
  alc_2 =	"e30000000098RXY-a",
  alcg_2 =	"e30000000088RXY-a",
  alcgr_2 =	"0000b9880000RRE",
  alcr_2 =	"0000b9980000RRE",
  alfi_2 =	"c20b00000000RIL-a",
  alg_2 =	"e3000000000aRXY-a",
  algf_2 =	"e3000000001aRXY-a",
  algfi_2 =	"c20a00000000RIL-a",
  algfr_2 =	"0000b91a0000RRE",
  algr_2 =	"0000b90a0000RRE",
  alr_2 =	"000000001e00RR",
  alsih_2 =	"cc0a00000000RIL-a",
  alsihn_2 =	"cc0b00000000RIL-a",
  aly_2 =	"e3000000005eRXY-a",
  ap_2 =	"fa0000000000SS-b",
  ar_2 =	"000000001a00RR",
  au_2 =	"00007e000000RX-a",
  aur_2 =	"000000003e00RR",
  aw_2 =	"00006e000000RX-a",
  awr_2 =	"000000002e00RR",
  axbr_2 =	"0000b34a0000RRE",
  axr_2 =	"000000003600RR",
  ay_2 =	"e3000000005aRXY-a",
  bakr_2 =	"0000b2400000RRE",
  bal_2 =	"000045000000RX-a",
  balr_2 =	"000000000500RR",
  bas_2 =	"00004d000000RX-a",
  basr_2 =	"000000000d00RR",
  bassm_2 =	"000000000c00RR",
  bc_2 =	"000047000000RX-b",
  bcr_2 =	"000000000700RR",
  bct_2 =	"000046000000RX-a",
  bctg_2 =	"e30000000046RXY-a",
  bctgr_2 =	"0000b9460000RRE",
  bctr_2 =	"000000000600RR",
  bras_2 =	"0000a7050000RI-b",
  brasl_2 =	"c00500000000RIL-b",
  brc_2 =	"0000a7040000RI-c",
  brcl_2 =	"c00400000000RIL-c",
  brct_2 =	"0000a7060000RI-b",
  brctg_2 =	"0000a7070000RI-b",
  brcth_2 =	"cc0600000000RIL-b",
  brxh_3 =	"000084000000RSI",
  brxhg_3 =	"ec0000000044RIE-e",
  bsa_2 =	"0000b25a0000RRE",
  bsg_2 =	"0000b2580000RRE",
  bsm_2 =	"000000000b00RR",
  bxh_3 =	"000086000000RS-a",
  bxhg_3 =	"eb0000000044RSY-a",
  bxle_3 =	"000087000000RS-a",
  bxleg_3 =	"eb0000000045RSY-a",
  c_2 =		"000059000000RX-a",
  cd_2 =	"000069000000RX-a",
  cdb_2 =	"ed0000000019RXE",
  cdbr_2 =	"0000b3190000RRE",
  cdfbr_2 =	"0000b3950000RRE",
  cdfbra_4 =	"0000b3950000RRF-e",
  cdfr_2 =	"0000b3b50000RRE",
  cdftr_2 =	"0000b9510000RRE",
  cdgbr_2 =	"0000b3a50000RRE",
  cdgbra_4 =	"0000b3a50000RRF-e",
  cdgr_2 =	"0000b3c50000RRE",
  cdgtr_2 =	"0000b3f10000RRE",
  cdr_2 =	"000000002900RR",
  cds_3 =	"0000bb000000RS-a",
  cdsg_3 =	"eb000000003eRSY-a",
  cdstr_2 =	"0000b3f30000RRE",
  cdsy_3 =	"eb0000000031RSY-a",
  cdtr_2 =	"0000b3e40000RRE",
  cdutr_2 =	"0000b3f20000RRE",
  ce_2 =	"000079000000RX-a",
  ceb_2 =	"ed0000000009RXE",
  cebr_2 =	"0000b3090000RRE",
  cedtr_2 =	"0000b3f40000RRE",
  cefbr_2 =	"0000b3940000RRE",
  cefbra_4 =	"0000b3940000RRF-e",
  cefr_2 =	"0000b3b40000RRE",
  cegbr_2 =	"0000b3a40000RRE",
  cegbra_4 =	"0000b3a40000RRF-e",
  cegr_2 =	"0000b3c40000RRE",
  cer_2 =	"000000003900RR",
  cextr_2 =	"0000b3fc0000RRE",
  cfdbr_3 =	"0000b3990000RRF-e",
  cfdbra_4 =	"0000b3990000RRF-e",
  cfebr_3 =	"0000b3980000RRF-e",
  cfebra_4 =	"0000b3980000RRF-e",
  cfi_2 =	"c20d00000000RIL-a",
  cfxbr_3 =	"0000b39a0000RRF-e",
  cfxbra_4 =	"0000b39a0000RRF-e",
  cg_2 =	"e30000000020RXY-a",
  cgdbr_3 =	"0000b3a90000RRF-e",
  cgdbra_4 =	"0000b3a90000RRF-e",
  cgebr_3 =	"0000b3a80000RRF-e",
  cgebra_4 =	"0000b3a80000RRF-e",
  cgf_2 =	"e30000000030RXY-a",
  cgfi_2 =	"c20c00000000RIL-a",
  cgfr_2 =	"0000b9300000RRE",
  cgfrl_2 =	"c60c00000000RIL-b",
  cgh_2 =	"e30000000034RXY-a",
  cghi_2 =	"0000a70f0000RI-a",
  cghrl_2 =	"c60400000000RIL-b",
  cgr_2 =	"0000b9200000RRE",
  cgrl_2 =	"c60800000000RIL-b",
  cgxbr_3 =	"0000b3aa0000RRF-e",
  cgxbra_4 =	"0000b3aa0000RRF-e",
  ch_2 =	"000049000000RX-a",
  chf_2 =	"e300000000cdRXY-a",
  chhr_2 =	"0000b9cd0000RRE",
  chi_2 =	"0000a70e0000RI-a",
  chlr_2 =	"0000b9dd0000RRE",
  chrl_2 =	"c60500000000RIL-b",
  chy_2 =	"e30000000079RXY-a",
  cih_2 =	"cc0d00000000RIL-a",
  cksm_2 =	"0000b2410000RRE",
  cl_2 =	"000055000000RX-a",
  clc_2 =	"d50000000000SS-a",
  clcl_2 =	"000000000f00RR",
  clcle_3 =	"0000a9000000RS-a",
  clclu_3 =	"eb000000008fRSY-a",
  clfi_2 =	"c20f00000000RIL-a",
  clg_2 =	"e30000000021RXY-a",
  clgf_2 =	"e30000000031RXY-a",
  clgfi_2 =	"c20e00000000RIL-a",
  clgfr_2 =	"0000b9310000RRE",
  clgfrl_2 =	"c60e00000000RIL-b",
  clghrl_2 =	"c60600000000RIL-b",
  clgr_2 =	"0000b9210000RRE",
  clgrl_2 =	"c60a00000000RIL-b",
  clhf_2 =	"e300000000cfRXY-a",
  clhhr_2 =	"0000b9cf0000RRE",
  clhlr_2 =	"0000b9df0000RRE",
  clhrl_2 =	"c60700000000RIL-b",
  cli_2 =	"000095000000SI",
  clih_2 =	"cc0f00000000RIL-a",
  clm_3 =	"0000bd000000RS-b",
  clmh_3 =	"eb0000000020RSY-b",
  clmy_3 =	"eb0000000021RSY-b",
  clr_2 =	"000000001500RR",
  clrl_2 =	"c60f00000000RIL-b",
  clst_2 =	"0000b25d0000RRE",
  cly_2 =	"e30000000055RXY-a",
  cmpsc_2 =	"0000b2630000RRE",
  cpya_2 =	"0000b24d0000RRE",
  cr_2 =	"000000001900RR",
  crl_2 =	"c60d00000000RIL-b",
  cs_3 =	"0000ba000000RS-a",
  csg_3 =	"eb0000000030RSY-a",
  csp_2 =	"0000b2500000RRE",
  cspg_2 =	"0000b98a0000RRE",
  csy_3 =	"eb0000000014RSY-a",
  cu41_2 =	"0000b9b20000RRE",
  cu42_2 =	"0000b9b30000RRE",
  cudtr_2 =	"0000b3e20000RRE",
  cuse_2 =	"0000b2570000RRE",
  cuxtr_2 =	"0000b3ea0000RRE",
  cvb_2 =	"00004f000000RX-a",
  cvbg_2 =	"e3000000000eRXY-a",
  cvby_2 =	"e30000000006RXY-a",
  cvd_2 =	"00004e000000RX-a",
  cvdg_2 =	"e3000000002eRXY-a",
  cvdy_2 =	"e30000000026RXY-a",
  cxbr_2 =	"0000b3490000RRE",
  cxfbr_2 =	"0000b3960000RRE",
  cxfbra_4 =	"0000b3960000RRF-e",
  cxfr_2 =	"0000b3b60000RRE",
  cxftr_2 =	"0000b9590000RRE",
  cxgbr_2 =	"0000b3a60000RRE",
  cxgbra_4 =	"0000b3a60000RRF-e",
  cxgr_2 =	"0000b3c60000RRE",
  cxgtr_2 =	"0000b3f90000RRE",
  cxr_2 =	"0000b3690000RRE",
  cxstr_2 =	"0000b3fb0000RRE",
  cxtr_2 =	"0000b3ec0000RRE",
  cxutr_2 =	"0000b3fa0000RRE",
  cy_2 =	"e30000000059RXY-a",
  d_2 =		"00005d000000RX-a",
  dd_2 =	"00006d000000RX-a",
  ddb_2 =	"ed000000001dRXE",
  ddbr_2 =	"0000b31d0000RRE",
  ddr_2 =	"000000002d00RR",
  de_2 =	"00007d000000RX-a",
  deb_2 =	"ed000000000dRXE",
  debr_2 =	"0000b30d0000RRE",
  der_2 =	"000000003d00RR",
  didbr_4 =	"0000b35b0000RRF-b",
  dl_2 =	"e30000000097RXY-a",
  dlg_2 =	"e30000000087RXY-a",
  dlgr_2 =	"0000b9870000RRE",
  dlr_2 =	"0000b9970000RRE",
  dr_2 =	"000000001d00RR",
  dsg_2 =	"e3000000000dRXY-a",
  dsgf_2 =	"e3000000001dRXY-a",
  dsgfr_2 =	"0000b91d0000RRE",
  dsgr_2 =	"0000b90d0000RRE",
  dxbr_2 =	"0000b34d0000RRE",
  dxr_2 =	"0000b22d0000RRE",
  ear_2 =	"0000b24f0000RRE",
  ecag_3 =	"eb000000004cRSY-a",
  ed_2 =	"de0000000000SS-a",
  edmk_2 =	"df0000000000SS-a",
  eedtr_2 =	"0000b3e50000RRE",
  eextr_2 =	"0000b3ed0000RRE",
  efpc_2 =	"0000b38c0000RRE",
  epair_2 =	"0000b99a0000RRE",
  epar_2 =	"0000b2260000RRE",
  epsw_2 =	"0000b98d0000RRE",
  ereg_2 =	"0000b2490000RRE",
  eregg_2 =	"0000b90e0000RRE",
  esair_2 =	"0000b99b0000RRE",
  esar_2 =	"0000b2270000RRE",
  esdtr_2 =	"0000b3e70000RRE",
  esea_2 =	"0000b99d0000RRE",
  esta_2 =	"0000b24a0000RRE",
  esxtr_2 =	"0000b3ef0000RRE",
  ex_2 =	"000044000000RX-a",
  exrl_2 =	"c60000000000RIL-b",
  fidbra_4 =	"0000b35f0000RRF-e",
  fidr_2 =	"0000b37f0000RRE",
  fier_2 =	"0000b3770000RRE",
  fixr_2 =	"0000b3670000RRE",
  flogr_2 =	"0000b9830000RRE",
  hdr_2 =	"000000002400RR",
  her_2 =	"000000003400RR",
  iac_2 =	"0000b2240000RRE",
  ic_2 =	"000043000000RX-a",
  icm_3 =	"0000bf000000RS-b",
  icmh_3 =	"eb0000000080RSY-b",
  icmy_3 =	"eb0000000081RSY-b",
  icy_2 =	"e30000000073RXY-a",
  iihf_2 =	"c00800000000RIL-a",
  iihh_2 =	"0000a5000000RI-a",
  iihl_2 =	"0000a5010000RI-a",
  iilf_2 =	"c00900000000RIL-a",
  iilh_2 =	"0000a5020000RI-a",
  iill_2 =	"0000a5030000RI-a",
  ipm_2 =	"0000b2220000RRE",
  iske_2 =	"0000b2290000RRE",
  ivsk_2 =	"0000b2230000RRE",
  kdbr_2 =	"0000b3180000RRE",
  kdtr_2 =	"0000b3e00000RRE",
  kebr_2 =	"0000b3080000RRE",
  kimd_2 =	"0000b93e0000RRE",
  klmd_2 =	"0000b93f0000RRE",
  km_2 =	"0000b92e0000RRE",
  kmac_2 =	"0000b91e0000RRE",
  kmc_2 =	"0000b92f0000RRE",
  kmf_2 =	"0000b92a0000RRE",
  kmo_2 =	"0000b92b0000RRE",
  kxbr_2 =	"0000b3480000RRE",
  kxtr_2 =	"0000b3e80000RRE",
  l_2 =		"000058000000RX-a",
  la_2 =	"000041000000RX-a",
  laa_3 =	"eb00000000f8RSY-a",
  laag_3 =	"eb00000000e8RSY-a",
  laal_3 =	"eb00000000faRSY-a",
  laalg_3 =	"eb00000000eaRSY-a",
  lae_2 =	"000051000000RX-a",
  laey_2 =	"e30000000075RXY-a",
  lam_3 =	"00009a000000RS-a",
  lamy_3 =	"eb000000009aRSY-a",
  lan_3 =	"eb00000000f4RSY-a",
  lang_3 =	"eb00000000e4RSY-a",
  lao_3 =	"eb00000000f6RSY-a",
  laog_3 =	"eb00000000e6RSY-a",
  larl_2 =	"c00000000000RIL-b",
  lax_3 =	"eb00000000f7RSY-a",
  laxg_3 =	"eb00000000e7RSY-a",
  lay_2 =	"e30000000071RXY-a",
  lb_2 =	"e30000000076RXY-a",
  lbh_2 =	"e300000000c0RXY-a",
  lbr_2 =	"0000b9260000RRE",
  lcdbr_2 =	"0000b3130000RRE",
  lcdfr_2 =	"0000b3730000RRE",
  lcdr_2 =	"000000002300RR",
  lcebr_2 =	"0000b3030000RRE",
  lcer_2 =	"000000003300RR",
  lcgfr_2 =	"0000b9130000RRE",
  lcgr_2 =	"0000b9030000RRE",
  lcr_2 =	"000000001300RR",
  lctl_3 =	"0000b7000000RS-a",
  lctlg_3 =	"eb000000002fRSY-a",
  lcxbr_2 =	"0000b3430000RRE",
  lcxr_2 =	"0000b3630000RRE",
  ld_2 =	"000068000000RX-a",
  ldebr_2 =	"0000b3040000RRE",
  lder_2 =	"0000b3240000RRE",
  ldgr_2 =	"0000b3c10000RRE",
  ldr_2 =	"000000002800RR",
  ldxbr_2 =	"0000b3450000RRE",
  ldxr_2 =	"000000002500RR",
  ldy_2 =	"ed0000000065RXY-a",
  le_2 =	"000078000000RX-a",
  ledbr_2 =	"0000b3440000RRE",
  ledr_2 =	"000000003500RR",
  ler_2 =	"000000003800RR",
  lexbr_2 =	"0000b3460000RRE",
  lexr_2 =	"0000b3660000RRE",
  ley_2 =	"ed0000000064RXY-a",
  lfh_2 =	"e300000000caRXY-a",
  lg_2 =	"e30000000004RXY-a",
  lgb_2 =	"e30000000077RXY-a",
  lgbr_2 =	"0000b9060000RRE",
  lgdr_2 =	"0000b3cd0000RRE",
  lgf_2 =	"e30000000014RXY-a",
  lgfi_2 =	"c00100000000RIL-a",
  lgfr_2 =	"0000b9140000RRE",
  lgfrl_2 =	"c40c00000000RIL-b",
  lgh_2 =	"e30000000015RXY-a",
  lghi_2 =	"0000a7090000RI-a",
  lghr_2 =	"0000b9070000RRE",
  lghrl_2 =	"c40400000000RIL-b",
  lgr_2 =	"0000b9040000RRE",
  lgrl_2 =	"c40800000000RIL-b",
  lh_2 =	"000048000000RX-a",
  lhh_2 =	"e300000000c4RXY-a",
  lhi_2 =	"0000a7080000RI-a",
  lhr_2 =	"0000b9270000RRE",
  lhrl_2 =	"c40500000000RIL-b",
  lhy_2 =	"e30000000078RXY-a",
  llc_2 =	"e30000000094RXY-a",
  llch_2 =	"e300000000c2RXY-a",
  llcr_2 =	"0000b9940000RRE",
  llgc_2 =	"e30000000090RXY-a",
  llgcr_2 =	"0000b9840000RRE",
  llgf_2 =	"e30000000016RXY-a",
  llgfr_2 =	"0000b9160000RRE",
  llgfrl_2 =	"c40e00000000RIL-b",
  llgh_2 =	"e30000000091RXY-a",
  llghr_2 =	"0000b9850000RRE",
  llghrl_2 =	"c40600000000RIL-b",
  llgt_2 =	"e30000000017RXY-a",
  llgtr_2 =	"0000b9170000RRE",
  llh_2 =	"e30000000095RXY-a",
  llhh_2 =	"e300000000c6RXY-a",
  llhr_2 =	"0000b9950000RRE",
  llhrl_2 =	"c40200000000RIL-b",
  llihf_2 =	"c00e00000000RIL-a",
  llihh_2 =	"0000a50c0000RI-a",
  llihl_2 =	"0000a50d0000RI-a",
  llilf_2 =	"c00f00000000RIL-a",
  llilh_2 =	"0000a50e0000RI-a",
  llill_2 =	"0000a50f0000RI-a",
  lm_3 =	"000098000000RS-a",
  lmg_3 =	"eb0000000004RSY-a",
  lmh_3 =	"eb0000000096RSY-a",
  lmy_3 =	"eb0000000098RSY-a",
  lndbr_2 =	"0000b3110000RRE",
  lndfr_2 =	"0000b3710000RRE",
  lndr_2 =	"000000002100RR",
  lnebr_2 =	"0000b3010000RRE",
  lner_2 =	"000000003100RR",
  lngfr_2 =	"0000b9110000RRE",
  lngr_2 =	"0000b9010000RRE",
  lnr_2 =	"000000001100RR",
  lnxbr_2 =	"0000b3410000RRE",
  lnxr_2 =	"0000b3610000RRE",
  loc_3 =	"eb00000000f2RSY-b",
  locg_3 =	"eb00000000e2RSY-b",
  lpdbr_2 =	"0000b3100000RRE",
  lpdfr_2 =	"0000b3700000RRE",
  lpdr_2 =	"000000002000RR",
  lpebr_2 =	"0000b3000000RRE",
  lper_2 =	"000000003000RR",
  lpgfr_2 =	"0000b9100000RRE",
  lpgr_2 =	"0000b9000000RRE",
  lpq_2 =	"e3000000008fRXY-a",
  lpr_2 =	"000000001000RR",
  lpxbr_2 =	"0000b3400000RRE",
  lpxr_2 =	"0000b3600000RRE",
  lr_2 =	"000000001800RR",
  lra_2 =	"0000b1000000RX-a",
  lrag_2 =	"e30000000003RXY-a",
  lray_2 =	"e30000000013RXY-a",
  lrdr_2 =	"000000002500RR",
  lrer_2 =	"000000003500RR",
  lrl_2 =	"c40d00000000RIL-b",
  lrv_2 =	"e3000000001eRXY-a",
  lrvg_2 =	"e3000000000fRXY-a",
  lrvgr_2 =	"0000b90f0000RRE",
  lrvh_2 =	"e3000000001fRXY-a",
  lrvr_2 =	"0000b91f0000RRE",
  lt_2 =	"e30000000012RXY-a",
  ltdbr_2 =	"0000b3120000RRE",
  ltdr_2 =	"000000002200RR",
  ltdtr_2 =	"0000b3d60000RRE",
  ltebr_2 =	"0000b3020000RRE",
  lter_2 =	"000000003200RR",
  ltg_2 =	"e30000000002RXY-a",
  ltgf_2 =	"e30000000032RXY-a",
  ltgfr_2 =	"0000b9120000RRE",
  ltgr_2 =	"0000b9020000RRE",
  ltr_2 =	"000000001200RR",
  ltxbr_2 =	"0000b3420000RRE",
  ltxr_2 =	"0000b3620000RRE",
  ltxtr_2 =	"0000b3de0000RRE",
  lura_2 =	"0000b24b0000RRE",
  lurag_2 =	"0000b9050000RRE",
  lxdbr_2 =	"0000b3050000RRE",
  lxdr_2 =	"0000b3250000RRE",
  lxebr_2 =	"0000b3060000RRE",
  lxer_2 =	"0000b3260000RRE",
  lxr_2 =	"0000b3650000RRE",
  ly_2 =	"e30000000058RXY-a",
  lzdr_2 =	"0000b3750000RRE",
  lzer_2 =	"0000b3740000RRE",
  lzxr_2 =	"0000b3760000RRE",
  m_2 =		"00005c000000RX-a",
  madb_3 =	"ed000000001eRXF",
  maeb_3 =	"ed000000000eRXF",
  maebr_3 =	"0000b30e0000RRD",
  maer_3 =	"0000b32e0000RRD",
  md_2 =	"00006c000000RX-a",
  mdb_2 =	"ed000000001cRXE",
  mdbr_2 =	"0000b31c0000RRE",
  mde_2 =	"00007c000000RX-a",
  mdeb_2 =	"ed000000000cRXE",
  mdebr_2 =	"0000b30c0000RRE",
  mder_2 =	"000000003c00RR",
  mdr_2 =	"000000002c00RR",
  me_2 =	"00007c000000RX-a",
  meeb_2 =	"ed0000000017RXE",
  meebr_2 =	"0000b3170000RRE",
  meer_2 =	"0000b3370000RRE",
  mer_2 =	"000000003c00RR",
  mfy_2 =	"e3000000005cRXY-a",
  mghi_2 =	"0000a70d0000RI-a",
  mh_2 =	"00004c000000RX-a",
  mhi_2 =	"0000a70c0000RI-a",
  mhy_2 =	"e3000000007cRXY-a",
  ml_2 =	"e30000000096RXY-a",
  mlg_2 =	"e30000000086RXY-a",
  mlgr_2 =	"0000b9860000RRE",
  mlr_2 =	"0000b9960000RRE",
  mr_2 =	"000000001c00RR",
  ms_2 =	"000071000000RX-a",
  msfi_2 =	"c20100000000RIL-a",
  msg_2 =	"e3000000000cRXY-a",
  msgf_2 =	"e3000000001cRXY-a",
  msgfi_2 =	"c20000000000RIL-a",
  msgfr_2 =	"0000b91c0000RRE",
  msgr_2 =	"0000b90c0000RRE",
  msr_2 =	"0000b2520000RRE",
  msta_2 =	"0000b2470000RRE",
  msy_2 =	"e30000000051RXY-a",
  mvc_2 =	"d20000000000SS-a",
  mvcin_2 =	"e80000000000SS-a",
  mvcl_2 =	"000000000e00RR",
  mvcle_3 =	"0000a8000000RS-a",
  mvclu_3 =	"eb000000008eRSY-a",
  mvghi_2 =	"e54800000000SIL",
  mvhhi_2 =	"e54400000000SIL",
  mvhi_2 =	"e54c00000000SIL",
  mvi_2 =	"000092000000SI",
  mvn_2 =	"d10000000000SS-a",
  mvpg_2 =	"0000b2540000RRE",
  mvst_2 =	"0000b2550000RRE",
  mvz_2 =	"d30000000000SS-a",
  mxbr_2 =	"0000b34c0000RRE",
  mxd_2 =	"000067000000RX-a",
  mxdb_2 =	"ed0000000007RXE",
  mxdbr_2 =	"0000b3070000RRE",
  mxdr_2 =	"000000002700RR",
  mxr_2 =	"000000002600RR",
  n_2 =		"000054000000RX-a",
  nc_2 =	"d40000000000SS-a",
  ng_2 =	"e30000000080RXY-a",
  ngr_2 =	"0000b9800000RRE",
  ni_2 =	"000094000000SI",
  nihf_2 =	"c00a00000000RIL-a",
  nihh_2 =	"0000a5040000RI-a",
  nihl_2 =	"0000a5050000RI-a",
  nilf_2 =	"c00b00000000RIL-a",
  nilh_2 =	"0000a5060000RI-a",
  nill_2 =	"0000a5070000RI-a",
  nr_2 =	"000000001400RR",
  ny_2 =	"e30000000054RXY-a",
  o_2 =		"000056000000RX-a",
  oc_2 =	"d60000000000SS-a",
  og_2 =	"e30000000081RXY-a",
  ogr_2 =	"0000b9810000RRE",
  oi_2 =	"000096000000SI",
  oihf_2 =	"c00c00000000RIL-a",
  oihh_2 =	"0000a5080000RI-a",
  oihl_2 =	"0000a5090000RI-a",
  oilf_2 =	"c00d00000000RIL-a",
  oilh_2 =	"0000a50a0000RI-a",
  oill_2 =	"0000a50b0000RI-a",
  or_2 =	"000000001600RR",
  oy_2 =	"e30000000056RXY-a",
  palb_2 =	"0000b2480000RRE",
  pcc_2 =	"0000b92c0000RRE",
  pckmo_2 =	"0000b9280000RRE",
  pfd_2 =	"e30000000036m",
  pfdrl_2 =	"c60200000000RIL-c",
  pfmf_2 =	"0000b9af0000RRE",
  pgin_2 =	"0000b22e0000RRE",
  pgout_2 =	"0000b22f0000RRE",
  popcnt_2 =	"0000b9e10000RRE",
  pt_2 =	"0000b2280000RRE",
  ptf_2 =	"0000b9a20000RRE",
  pti_2 =	"0000b99e0000RRE",
  rll_3 =	"eb000000001dRSY-a",
  rllg_3 =	"eb000000001cRSY-a",
  rrbe_2 =	"0000b22a0000RRE",
  rrbm_2 =	"0000b9ae0000RRE",
  s_2 =		"00005b000000RX-a",
  sar_2 =	"0000b24e0000RRE",
  sd_2 =	"00006b000000RX-a",
  sdb_2 =	"ed000000001bRXE",
  sdbr_2 =	"0000b31b0000RRE",
  sdr_2 =	"000000002b00RR",
  se_2 =	"00007b000000RX-a",
  seb_2 =	"ed000000000bRXE",
  sebr_2 =	"0000b30b0000RRE",
  ser_2 =	"000000003b00RR",
  sfasr_2 =	"0000b3850000RRE",
  sfpc_2 =	"0000b3840000RRE",
  sg_2 =	"e30000000009RXY-a",
  sgf_2 =	"e30000000019RXY-a",
  sgfr_2 =	"0000b9190000RRE",
  sgr_2 =	"0000b9090000RRE",
  sh_2 =	"00004b000000RX-a",
  shy_2 =	"e3000000007bRXY-a",
  sl_2 =	"00005f000000RX-a",
  sla_2 =	"00008b000000RS-a",
  slag_3 =	"eb000000000bRSY-a",
  slak_3 =	"eb00000000ddRSY-a",
  slb_2 =	"e30000000099RXY-a",
  slbg_2 =	"e30000000089RXY-a",
  slbgr_2 =	"0000b9890000RRE",
  slbr_2 =	"0000b9990000RRE",
  slda_2 =	"00008f000000RS-a",
  sldl_2 =	"00008d000000RS-a",
  slfi_2 =	"c20500000000RIL-a",
  slg_2 =	"e3000000000bRXY-a",
  slgf_2 =	"e3000000001bRXY-a",
  slgfi_2 =	"c20400000000RIL-a",
  slgfr_2 =	"0000b91b0000RRE",
  slgr_2 =	"0000b90b0000RRE",
  sll_2 =	"000089000000RS-a",
  sllg_3 =	"eb000000000dRSY-a",
  sllk_3 =	"eb00000000dfRSY-a",
  slr_2 =	"000000001f00RR",
  sly_2 =	"e3000000005fRXY-a",
  spm_2 =	"000000000400RR",
  sqdb_2 =	"ed0000000015RXE",
  sqdbr_2 =	"0000b3150000RRE",
  sqdr_2 =	"0000b2440000RRE",
  sqeb_2 =	"ed0000000014RXE",
  sqebr_2 =	"0000b3140000RRE",
  sqer_2 =	"0000b2450000RRE",
  sqxbr_2 =	"0000b3160000RRE",
  sqxr_2 =	"0000b3360000RRE",
  sr_2 =	"000000001b00RR",
  sra_2 =	"00008a000000RS-a",
  srag_3 =	"eb000000000aRSY-a",
  srak_3 =	"eb00000000dcRSY-a",
  srda_2 =	"00008e000000RS-a",
  srdl_2 =	"00008c000000RS-a",
  srl_2 =	"000088000000RS-a",
  srlg_3 =	"eb000000000cRSY-a",
  srlk_3 =	"eb00000000deRSY-a",
  srst_2 =	"0000b25e0000RRE",
  srstu_2 =	"0000b9be0000RRE",
  ssair_2 =	"0000b99f0000RRE",
  ssar_2 =	"0000b2250000RRE",
  st_2 =	"000050000000RX-a",
  stam_3 =	"00009b000000RS-a",
  stamy_3 =	"eb000000009bRSY-a",
  stc_2 =	"000042000000RX-a",
  stch_2 =	"e300000000c3RXY-a",
  stcm_3 =	"0000be000000RS-b",
  stcmh_3 =	"eb000000002cRSY-b",
  stcmy_3 =	"eb000000002dRSY-b",
  stctg_3 =	"eb0000000025RSY-a",
  stctl_3 =	"0000b6000000RS-a",
  stcy_2 =	"e30000000072RXY-a",
  std_2 =	"000060000000RX-a",
  stdy_2 =	"ed0000000067RXY-a",
  ste_2 =	"000070000000RX-a",
  stey_2 =	"ed0000000066RXY-a",
  stfh_2 =	"e300000000cbRXY-a",
  stfl_1 =	"0000b2b10000S",
  stg_2 =	"e30000000024RXY-a",
  stgrl_2 =	"c40b00000000RIL-b",
  sth_2 =	"000040000000RX-a",
  sthh_2 =	"e300000000c7RXY-a",
  sthrl_2 =	"c40700000000RIL-b",
  sthy_2 =	"e30000000070RXY-a",
  stm_3 =	"000090000000RS-a",
  stmg_3 =	"eb0000000024RSY-a",
  stmh_3 =	"eb0000000026RSY-a",
  stmy_3 =	"eb0000000090RSY-a",
  stoc_3 =	"eb00000000f3RSY-b",
  stocg_3 =	"eb00000000e3RSY-b",
  stpq_2 =	"e3000000008eRXY-a",
  strl_2 =	"c40f00000000RIL-b",
  strv_2 =	"e3000000003eRXY-a",
  strvg_2 =	"e3000000002fRXY-a",
  strvh_2 =	"e3000000003fRXY-a",
  stura_2 =	"0000b2460000RRE",
  sturg_2 =	"0000b9250000RRE",
  sty_2 =	"e30000000050RXY-a",
  su_2 =	"00007f000000RX-a",
  sur_2 =	"000000003f00RR",
  svc_1 =	"000000000a00I",
  sw_2 =	"00006f000000RX-a",
  swr_2 =	"000000002f00RR",
  sxbr_2 =	"0000b34b0000RRE",
  sxr_2 =	"000000003700RR",
  sy_2 =	"e3000000005bRXY-a",
  tar_2 =	"0000b24c0000RRE",
  tb_2 =	"0000b22c0000RRE",
  thder_2 =	"0000b3580000RRE",
  thdr_2 =	"0000b3590000RRE",
  tm_2 =	"000091000000SI",
  tmhh_2 =	"0000a7020000RI-a",
  tmhl_2 =	"0000a7030000RI-a",
  tmlh_2 =	"0000a7000000RI-a",
  tmll_2 =	"0000a7010000RI-a",
  tmy_2 =	"eb0000000051SIY",
  tr_2 =	"dc0000000000SS-a",
  trace_3 =	"000099000000RS-a",
  tracg_3 =	"eb000000000fRSY-a",
  tre_2 =	"0000b2a50000RRE",
  trt_2 =	"dd0000000000SS-a",
  trtr_2 =	"d00000000000SS-a",
  unpka_2 =	"ea0000000000SS-a",
  unpku_2 =	"e20000000000SS-a",
  x_2 =		"000057000000RX-a",
  xc_2 =	"d70000000000SS-a",
  xg_2 =	"e30000000082RXY-a",
  xgr_2 =	"0000b9820000RRE",
  xi_2 =	"000097000000SI",
  xihf_2 =	"c00600000000RIL-a",
  xilf_2 =	"c00700000000RIL-a",
  xr_2 =	"000000001700RR",
  xy_2 =	"e30000000057RXY-a",
}
for cond, c in pairs(map_cond) do
  -- Extended mnemonics for branches.
  -- TODO: replace 'B' with correct encoding.
  -- brc
  map_op["j"..cond.."_1"] = "0000"..tohex(0xa7040000+shl(c, 20)).."RI-c"
  -- brcl
  map_op["jg"..cond.."_1"] = tohex(0xc0040000+shl(c, 20)).."0000".."RIL-c"
  -- bc
  map_op["b"..cond.."_1"] = "0000"..tohex(0x47000000+shl(c, 20)).."RX-b"
  -- bcr
  map_op["b"..cond.."r_1"] = "0000"..tohex(0x0700+shl(c, 4)).."RR"
end
------------------------------------------------------------------------------
-- Handle opcodes defined with template strings.
local function parse_template(params, template, nparams, pos)
  -- Read the template in 16-bit chunks.
  -- Leading halfword zeroes should not be written out.
  local op0 = tonumber(sub(template, 1, 4), 16)
  local op1 = tonumber(sub(template, 5, 8), 16)
  local op2 = tonumber(sub(template, 9, 12), 16)

  -- Process each character.
  local p = sub(template, 13)
  if p == "I" then
    local imm_val, a = parse_imm8(params[1])
    op2 = op2 + imm_val
    wputhw(op2)
    if a then a() end
  elseif p == "RI-a" then
    op1 = op1 + shl(parse_reg(params[1]), 4)
    wputhw(op1)
    parse_imm16(params[2])
  elseif p == "RI-b" then
    op1 = op1 + shl(parse_reg(params[1]), 4)
    wputhw(op1)
    local mode, n, s = parse_label(params[2])
    waction("REL_"..mode, n, s)
  elseif p == "RI-c" then
    if #params > 1 then
      op1 = op1 + shl(parse_num(params[1]), 4)
    end
    wputhw(op1)
    local mode, n, s = parse_label(params[#params])
    waction("REL_"..mode, n, s)
  elseif p == "RIE-e" then
    op0 = op0 + shl(parse_reg(params[1]), 4) + parse_reg(params[2])
    wputhw1(op0)
    local mode, n, s = parse_label(params[3])
    waction("REL_"..mode, n, s)
    wputhw(op2)
  elseif p == "RIL-a" then
    op0 = op0 + shl(parse_reg(params[1]), 4)
    wputhw(op0);
    parse_imm32(params[2])
  elseif p == "RIL-b" then
    op0 = op0 + shl(parse_reg(params[1]), 4)
    wputhw(op0)
    local mode, n, s = parse_label(params[2])
    waction("REL_"..mode, n, s)
  elseif p == "RIL-c" then
    if #params > 1 then
      op0 = op0 + shl(parse_num(params[1]), 4)
    end
    wputhw(op0)
    local mode, n, s = parse_label(params[#params])
    waction("REL_"..mode, n, s)
  elseif p == "RR" then
    if #params > 1 then
      op2 = op2 + shl(parse_reg(params[1]), 4)
    end
    op2 = op2 + parse_reg(params[#params])
    wputhw(op2)
  elseif p == "RRD" then
    wputhw(op1)
    op2 = op2 + shl(parse_reg(params[1]), 12) + shl(parse_reg(params[2]), 4) + parse_reg(params[3])
    wputhw(op2)
  elseif p == "RRE" then
    op2 = op2 + shl(parse_reg(params[1]), 4) + parse_reg(params[2])
    wputhw(op1); wputhw(op2)
  elseif p == "RRF-b" then
    wputhw(op1)
    op2 = op2 + shl(parse_reg(params[1]), 4) + shl(parse_reg(params[2]), 12) + parse_reg(params[3]) + shl(parse_mask(params[4]), 8)
    wputhw(op2)
  elseif p == "RRF-e" then
    wputhw(op1)
    op2 = op2 + shl(parse_reg(params[1]), 4) + shl(parse_mask(params[2]), 12) + parse_reg(params[3])
    if params[4] then
      op2 = op2 + shl(parse_mask2(params[4]), 8)
    end
    wputhw(op2)
  elseif p == "RS-a" then
    if (params[3]) then
      local d, b, a = parse_mem_b(params[3])
      op1 = op1 + shl(parse_reg(params[1]), 4) + parse_reg(params[2])
      op2 = op2 + shl(b, 12) + d
    else
      local d, b, a = parse_mem_b(params[2])
      op1 = op1 + shl(parse_reg(params[1]), 4)
      op2 = op2 + shl(b, 12) + d
    end
    wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "RS-b" then
    local m = parse_mask(params[2])
    local d, b, a = parse_mem_b(params[3])
    op1 = op1 + shl(parse_reg(params[1]), 4) + m
    op2 = op2 + shl(b, 12) + d
    wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "RSI" then
    op1 = op1 + shl(parse_reg(params[1]), 4) + parse_reg(params[2])
    wputhw(op1)
    local mode, n, s = parse_label(params[3])
    waction("REL_"..mode, n, s)
  elseif p == "RSY-a" then
    local d, b, a = parse_mem_by(params[3])
    op0 = op0 + shl(parse_reg(params[1]), 4) + parse_reg(params[2])
    op1 = op1 + shl(b, 12) + band(d, 0xfff)
    op2 = op2 + band(shr(d, 4), 0xff00)
    wputhw(op0); wputhw(op1); wputhw(op2)
    if a then a() end -- a() emits action.
  elseif p == "RX-a" then
    local d, x, b, a = parse_mem_bx(params[2])
    op1 = op1 + shl(parse_reg(params[1]), 4) + x
    op2 = op2 + shl(b, 12) + d
    wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "RX-b" then
    local d, x, b, a = parse_mem_bx(params[#params])
    if #params > 1 then
      op1 = op1 + shl(parse_num(params[1]), 4)
    end
    op1 = op1 + x
    op2 = op2 + shl(b, 12) + d
    wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "RXE" then
    local d, x, b, a = parse_mem_bx(params[2])
    op0 = op0 + shl(parse_reg(params[1]), 4) + x
    op1 = op1 + shl(b, 12) + d
    wputhw(op0); wputhw(op1)
    if a then a() end
    wputhw(op2);
  elseif p == "RXF" then
    local d, x, b, a = parse_mem_bx(params[3])
    op0 = op0 + shl(parse_reg(params[2]), 4) + x
    op1 = op1 + shl(b, 12) + d
    wputhw(op0); wputhw(op1)
    if a then a() end
    op2 = op2 + shl(parse_reg(params[1]), 12)
    wputhw(op2)
  elseif p == "RXY-a" then
    local d, x, b, a = parse_mem_bxy(params[2])
    op0 = op0 + shl(parse_reg(params[1]), 4) + x
    op1 = op1 + shl(b, 12) + band(d, 0xfff)
    op2 = op2 + band(shr(d, 4), 0xff00)
    wputhw(op0); wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "S" then
    wputhw(op1);
    local d, b, a = parse_mem_b(params[1])
    op2 = op2 + shl(b, 12) + d
    wputhw(op2)
    if a then a() end
  elseif p == "SI" then
    local imm_val, a = parse_imm8(params[2])
    op1 = op1 + imm_val
    wputhw(op1)
    if a then a() end
    local d, b, a = parse_mem_b(params[1])
    op2 = op2 + shl(b, 12) + d
    wputhw(op2)
    if a then a() end
  elseif p == "SIL" then
    wputhw(op0)
    local d, b, a = parse_mem_b(params[1])
    op1 = op1 + shl(b, 12) + d
    wputhw(op1)
    if a then a() end
    parse_imm16(params[2])
  elseif p == "SIY" then
    local imm8, iact = parse_imm8(params[2])
    op0 = op0 + shl(imm8, 8)
    wputhw(op0)
    if iact then iact() end
    local d, b, a = parse_mem_by(params[1])
    op1 = op1 + shl(b, 12) + band(d, 0xfff)
    op2 = op2 + band(shr(d, 4), 0xff00)
    wputhw(op1); wputhw(op2)
    if a then a() end
  elseif p == "SS-a" then
    local d1, l1, b1, d1a, l1a = parse_mem_lb(params[1])
    local d2, b2, d2a = parse_mem_b(params[2])
    op0 = op0 + l1
    op1 = op1 + shl(b1, 12) + d1
    op2 = op2 + shl(b2, 12) + d2
    wputhw(op0)
    if l1a then l1a() end
    wputhw(op1)
    if d1a then d1a() end
    wputhw(op2)
    if d2a then d2a() end
  elseif p == "SS-b" then
    local high_l = true
    local d1, l1, b1, d1a, l1a = parse_mem_l2b(params[1], high_l)
    high_l = false
    local d2, l2, b2, d2a, l2a = parse_mem_l2b(params[2], high_l)
    op0 = op0 + shl(l1, 4) + l2
    op1 = op1 + shl(b1, 12) + d1
    op2 = op2 + shl(b2, 12) + d2
    wputhw(op0)
    if l1a then l1a() end
    if l2a then l2a() end
    wputhw(op1)
    if d1a then d1a() end
    wputhw(op2)
    if d2a then d2a() end
  else
    werror("unrecognized encoding")
  end
end

function op_template(params, template, nparams)
  if not params then return template:gsub("%x%x%x%x%x%x%x%x%x%x%x%x", "") end
  -- Limit number of section buffer positions used by a single dasm_put().
  -- A single opcode needs a maximum of 5 positions.
  if secpos+5 > maxsecpos then wflush() end
  local lpos, apos, spos = #actlist, #actargs, secpos
  local ok, err
  for t in gmatch(template, "[^|]+") do
    ok, err = pcall(parse_template, params, t, nparams)
    if ok then return end
    secpos = spos
    actlist[lpos+1] = nil
    actlist[lpos+2] = nil
    actlist[lpos+3] = nil
    actargs[apos+1] = nil
    actargs[apos+2] = nil
    actargs[apos+3] = nil
  end
  error(err, 0)
end
map_op[".template__"] = op_template
------------------------------------------------------------------------------
-- Pseudo-opcode to mark the position where the action list is to be emitted.
map_op[".actionlist_1"] = function(params)
  if not params then return "cvar" end
  local name = params[1] -- No syntax check. You get to keep the pieces.
  wline(function(out) writeactions(out, name) end)
end
-- Pseudo-opcode to mark the position where the global enum is to be emitted.
map_op[".globals_1"] = function(params)
  if not params then return "prefix" end
  local prefix = params[1] -- No syntax check. You get to keep the pieces.
  wline(function(out) writeglobals(out, prefix) end)
end
-- Pseudo-opcode to mark the position where the global names are to be emitted.
map_op[".globalnames_1"] = function(params)
  if not params then return "cvar" end
  local name = params[1] -- No syntax check. You get to keep the pieces.
  wline(function(out) writeglobalnames(out, name) end)
end
-- Pseudo-opcode to mark the position where the extern names are to be emitted.
map_op[".externnames_1"] = function(params)
  if not params then return "cvar" end
  local name = params[1] -- No syntax check. You get to keep the pieces.
  wline(function(out) writeexternnames(out, name) end)
end
------------------------------------------------------------------------------
-- Label pseudo-opcode (converted from trailing colon form).
map_op[".label_1"] = function(params)
  if not params then return "[1-9] | ->global | =>pcexpr" end
  if secpos+1 > maxsecpos then wflush() end
  local mode, n, s = parse_label(params[1], true)
  if mode == "EXT" then werror("bad label definition") end
  waction("LABEL_"..mode, n, s, 1)
end
------------------------------------------------------------------------------
-- Pseudo-opcodes for data storage.
map_op[".long_*"] = function(params)
  if not params then return "imm..." end
  for _, p in ipairs(params) do
    local n = tonumber(p)
    if not n then werror("bad immediate `"..p.."'") end
    if n < 0 then n = n + 2^32 end
    wputw(n)
    if secpos+2 > maxsecpos then wflush() end
  end
end
-- Alignment pseudo-opcode.
map_op[".align_1"] = function(params)
  if not params then return "numpow2" end
  if secpos+1 > maxsecpos then wflush() end
  local align = tonumber(params[1])
  if align then
    local x = align
    -- Must be a power of 2 in the range (2 ... 256).
    for i=1, 8 do
      x = x / 2
      if x == 1 then
	waction("ALIGN", align-1, nil, 1) -- Action halfword is 2**n-1.
	return
      end
    end
  end
  werror("bad alignment")
end
------------------------------------------------------------------------------
-- Pseudo-opcode for (primitive) type definitions (map to C types).
map_op[".type_3"] = function(params, nparams)
  if not params then
    return nparams == 2 and "name, ctype" or "name, ctype, reg"
  end
  local name, ctype, reg = params[1], params[2], params[3]
  if not match(name, "^[%a_][%w_]*$") then
    werror("bad type name `"..name.."'")
  end
  local tp = map_type[name]
  if tp then
    werror("duplicate type `"..name.."'")
  end
  -- Add #type to defines. A bit unclean to put it in map_archdef.
  map_archdef["#"..name] = "sizeof("..ctype..")"
  -- Add new type and emit shortcut define.
  local num = ctypenum + 1
  map_type[name] = {
    ctype = ctype,
    ctypefmt = format("Dt%X(%%s)", num),
    reg = reg,
  }
  wline(format("#define Dt%X(_V) (int)(ptrdiff_t)&(((%s *)0)_V)", num, ctype))
  ctypenum = num
end
map_op[".type_2"] = map_op[".type_3"]
-- Dump type definitions.
local function dumptypes(out, lvl)
  local t = {}
  for name in pairs(map_type) do t[#t+1] = name end
  sort(t)
  out:write("Type definitions:\n")
  for _, name in ipairs(t) do
    local tp = map_type[name]
    local reg = tp.reg or ""
    out:write(format("  %-20s %-20s %s\n", name, tp.ctype, reg))
  end
  out:write("\n")
end
------------------------------------------------------------------------------
-- Set the current section.
function _M.section(num)
  waction("SECTION", num)
  wflush(true) -- SECTION is a terminal action.
end
------------------------------------------------------------------------------
-- Dump architecture description.
function _M.dumparch(out)
  out:write(format("DynASM %s version %s, released %s\n\n",
    _info.arch, _info.version, _info.release))
  dumpactions(out)
end
-- Dump all user defined elements.
function _M.dumpdef(out, lvl)
  dumptypes(out, lvl)
  dumpglobals(out, lvl)
  dumpexterns(out, lvl)
end
------------------------------------------------------------------------------
-- Pass callbacks from/to the DynASM core.
function _M.passcb(wl, we, wf, ww)
  wline, werror, wfatal, wwarn = wl, we, wf, ww
  return wflush
end
-- Setup the arch-specific module.
function _M.setup(arch, opt)
  g_arch, g_opt = arch, opt
end
-- Merge the core maps and the arch-specific maps.
function _M.mergemaps(map_coreop, map_def)
  setmetatable(map_op, { __index = map_coreop })
  setmetatable(map_def, { __index = map_archdef })
  return map_op, map_def
end
return _M
------------------------------------------------------------------------------

