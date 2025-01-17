local openssl_bignum = require "resty.openssl.bn"
local openssl_rand = require "resty.openssl.rand"
local openssl_pkey = require "resty.openssl.pkey"
local x509 = require "resty.openssl.x509"
local x509_extension = require "resty.openssl.x509.extension"
local x509_name = require "resty.openssl.x509.name"

-- taken from https://github.com/Kong/kong/blob/master/kong/cmd/utils/prefix_handler.lua
local function generate_self_signed()
  local key = openssl_pkey.new { bits = 2048 }

  local crt = x509.new()
  assert(crt:set_pubkey(key))
  assert(crt:set_version(3))
  assert(crt:set_serial_number(openssl_bignum.from_binary(openssl_rand.bytes(16))))

  -- last for 20 years
  local now = os.time()
  assert(crt:set_not_before(now))
  assert(crt:set_not_after(now + 86400 * 20 * 365))

  local name = assert(x509_name.new()
    :add("C", "US")
    :add("ST", "California")
    :add("L", "San Francisco")
    :add("O", "Kong")
    :add("OU", "IT Department")
    :add("CN", "localhost"))

  assert(crt:set_subject_name(name))
  assert(crt:set_issuer_name(name))

  -- Not a CA
  assert(crt:set_basic_constraints { CA = false })
  assert(crt:set_basic_constraints_critical(true))

  -- Only allowed to be used for TLS connections (client or server)
  assert(crt:add_extension(x509_extension.new("extendedKeyUsage",
                                              "serverAuth,clientAuth")))

  -- RFC-3280 4.2.1.2
  assert(crt:add_extension(x509_extension.new("subjectKeyIdentifier", "hash", {
    subject = crt
  })))

  -- All done; sign
  assert(crt:sign(key))

  return crt, key
end


local crt, key = generate_self_signed()

do -- write key out
  local fd = assert(io.open("key.pem", "w+b"))
  local pem = assert(key:to_PEM("private"))
  assert(fd:write(pem))
  fd:close()
end

print("================== private key =================")
os.execute("openssl pkey -in key.pem -noout -text")
os.remove("key.pem")

do -- write cert out
  local fd = assert(io.open("cert.pem", "w+b"))
  local pem = assert(crt:to_PEM("private"))
  assert(fd:write(pem))
  fd:close()
end

print("\n\n")
print("================== certificate =================")
os.execute("openssl x509 -in cert.pem -noout -text")
os.remove("cert.pem")