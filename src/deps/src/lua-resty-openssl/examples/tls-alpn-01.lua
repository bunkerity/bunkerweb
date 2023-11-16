local pkey = require("resty.openssl.pkey")
local digest = require("resty.openssl.digest")
local x509 = require("resty.openssl.x509")
local altname = require("resty.openssl.x509.altname")
local extension = require("resty.openssl.x509.extension")
local objects = require("resty.openssl.objects")

-- creates the ACME Identifier NID into openssl's internal lookup table
-- if it doesn't exist
local id_pe_acmeIdentifier = "1.3.6.1.5.5.7.1.31"
local nid = objects.txt2nid(id_pe_acmeIdentifier)
if not nid or nid == 0 then
  nid = objects.create(
    id_pe_acmeIdentifier, -- nid
    "pe-acmeIdentifier",  -- sn
    "ACME Identifier"     -- ln
  )
end

-- generate the tls-alpn-01 challenge certificate/key per
-- https://tools.ietf.org/html/draft-ietf-acme-tls-alpn-07
-- with given domain name and challenge token
local function serve_challenge_cert(domain, challenge)
  local dgst = assert(digest.new("sha256"):final(challenge))

  -- There're two ways to set ASN.1 octect string to the extension
  -- The recommanded way is to pass the string directly to extension.from_der()
  local _, err = extension.from_der(dgst, nid, true)
  if err then
    return nil, nil, err
  end
  -- OR we put the ASN.1 signature for this string by ourselves
  -- 0x04: OCTET STRING
  -- 0x20: length
  local dgst_hex = "DER:0420" .. dgst:gsub("(.)", function(s) return string.format("%02x", string.byte(s)) end)
  local ext, err = extension.new(nid, dgst_hex)
  if err then
    return nil, nil, err
  end
  ext:set_critical(true)

  local key = pkey.new()
  local cert = x509.new()
  cert:set_pubkey(key)

  cert:add_extension(ext)

  local alt = assert(altname.new():add(
    "DNS", domain
  ))
  local _, err = cert:set_subject_alt_name(alt)
  if err then
    return nil, nil, err
  end
  cert:sign(key)

  return key, cert
end
