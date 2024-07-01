defines = {
    "output": "../lib/resty/openssl/x509/csr.lua",
    "output_test": "../t/openssl/x509/csr.t",
    "type": "X509_REQ",
    "has_sign_verify": True,
    "sample": "test.csr",
    "sample_signature_nid": 65,
    "sample_signature_name": "RSA-SHA1",
    "sample_signature_digest_name": "SHA1",
    "fields":
[
{
    "field": "subject_name",
    "type": "x509.name",
    "dup": True,
    "sample_printable": "C=US/CN=example.com/L=Los Angeles/O=SSL Support/OU=SSL Support/ST=California",
},

{
    "field": "pubkey",
    "type": "pkey",
    "sample_printable": '''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwPOIBIoblSLFv/ifj8GD
CNL5NhDX2JVUQKcWC19KtWYQg1HPnaGIy+Dj9tYSBw8T8xc9hbJ1TYGbBIMKfBUz
KoTt5yLdVIM/HJm3m9ImvAbK7TYcx1U9TJEMxN6686whAUMBr4B7ql4VTXqu6TgD
cdbcQ5wsPVOiFHJTTwgVwt7eVCBMFAkZn+qQz+WigM5HEp8KFrzwAK142H2ucuyf
gGS4+XQSsUdwNWh9GPRZgRt3R2h5ymYkQB/cbg596alCquoizI6QCfwQx3or9Dg1
f3rlwf8H5HIVH3hATGIr7GpbKka/JH2PYNGfi5KqsJssVQfu84m+5WXDB+90KHJE
cwIDAQAB
-----END PUBLIC KEY-----
''',
},

{
    "field": "version",
    "type": "number",
    "sample_printable": 1,
    "set_converter":
'''
  -- Note: this is defined by standards (X.509 et al) to be one less than the certificate version.
  -- So a version 3 certificate will return 2 and a version 1 certificate will return 0.
  toset = toset - 1
''',
    "get_converter":
'''
  got = tonumber(got) + 1
''',
},

################## extensions ######################

{
    "field": "subject_alt_name",
    "type": "x509.altname",
    "dup": True,
    "extension_nid": "subjectAltName",
    "sample_printable": 'DNS=example.com',
    "get_converter": '''
  -- Note: here we only free the stack itself not elements
  -- since there seems no way to increase ref count for a GENERAL_NAME
  -- we left the elements referenced by the new-dup'ed stack
  local got_ref = got
  ffi_gc(got_ref, stack_lib.gc_of("GENERAL_NAME"))
  got = ffi_cast("GENERAL_NAMES*", got_ref)''',
},
]
}