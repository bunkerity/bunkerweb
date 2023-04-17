
-- sample function to generate a DER CSR from given pkey and domains
local function create_csr(domain_pkey, ...)
  local domains = {...}

  local subject = require("resty.openssl.x509.name").new()
  local _, err = subject:add("CN", domains[1])
  if err then
    return nil, err
  end

  local alt, err
  if #{...} > 1 then
    alt, err = require("resty.openssl.x509.altname").new()
    if err then
      return nil, err
    end

    for _, domain in pairs(domains) do
      _, err = alt:add("DNS", domain)
      if err then
        return nil, err
      end
    end
  end

  local csr = require("resty.openssl.x509.csr").new()
  local _
  _, err = csr:set_subject_name(subject)
  if err then
    return nil, err
  end

  if alt then
    _, err = csr:set_subject_alt_name(alt)
    if err then
      return nil, err
    end
  end

  _, err = csr:set_pubkey(domain_pkey)
  if err then
    return nil, err
  end

  _, err = csr:sign(domain_pkey)
  if err then
    return nil, err
  end

  return csr:tostring("DER"), nil
end

-- create a EC key
local pkey, err = require("resty.openssl.pkey").new({
  type = 'EC',
  curve = 'prime256v1',
})
if err then
  error(err)
end

-- create a CSR using the key
local der, err = create_csr(pkey, "example.com", "*.example.com")
if err then
  error(err)
end

-- use openssl cli to see csr we just generated
local f = io.open("example.csr", "w")
f:write(der)
f:close()
os.execute("openssl req -in example.csr -inform der -noout -text")
os.remove("example.csr")
