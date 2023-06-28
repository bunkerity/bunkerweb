local GEN_OTHERNAME = 0
local GEN_EMAIL = 1
local GEN_DNS = 2
local GEN_X400 = 3
local GEN_DIRNAME = 4
local GEN_EDIPARTY = 5
local GEN_URI = 6
local GEN_IPADD = 7
local GEN_RID = 8

local default_types = {
  OtherName = GEN_OTHERNAME, -- otherName
  RFC822Name = GEN_EMAIL, -- email
  RFC822 = GEN_EMAIL,
  Email = GEN_EMAIL,
  DNSName = GEN_DNS, -- dns
  DNS = GEN_DNS,
  X400 = GEN_X400, -- x400
  DirName = GEN_DIRNAME, -- dirName
  EdiParty = GEN_EDIPARTY, -- EdiParty
  UniformResourceIdentifier = GEN_URI, -- uri
  URI = GEN_URI,
  IPAddress = GEN_IPADD, -- ipaddr
  IP = GEN_IPADD,
  RID = GEN_RID, -- rid
}

local literals = {
  [GEN_OTHERNAME] = "OtherName",
  [GEN_EMAIL] = "email",
  [GEN_DNS] = "DNS",
  [GEN_X400] = "X400",
  [GEN_DIRNAME] = "DirName",
  [GEN_EDIPARTY] = "EdiParty",
  [GEN_URI] = "URI",
  [GEN_IPADD] = "IP",
  [GEN_RID] = "RID",
}

local types = {}
for t, gid in pairs(default_types) do
  types[t:lower()] = gid
  types[t] = gid
end

return {
  types = types,
  literals = literals,
}