defines = {
    "output": "../lib/resty/openssl/x509/crl.lua",
    "output_test": "../t/openssl/x509/crl.t",
    "type": "X509_CRL",
    "has_extension_accessor_by_nid": True,
    "extensions_in_struct":"crl.extensions",
    "has_sign_verify": True,
    "sample": "TrustAsiaEVTLSProCAG2.crl",
    "sample_signature_nid": 668,
    "sample_signature_name": "RSA-SHA256",
    "sample_signature_digest_name": "SHA256",
    "fields":
[
{
    "field": "issuer_name",
    "type": "x509.name",
    "dup": True,
    "sample_printable": "C=CN/CN=TrustAsia EV TLS Pro CA G2/O=TrustAsia Technologies, Inc.",
},

{
    "field": "last_update",
    "type": "number",
    "sample_printable": 1580684546,
    "set_converter": '''
  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)
''',
    "get_converter": '''
  got = asn1_lib.asn1_to_unix(got)
''',
},

{
    "field": "next_update",
    "type": "number",
    "sample_printable": 1581289346,
    "set_converter": '''
  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)
''',
    "get_converter": '''
  got = asn1_lib.asn1_to_unix(got)
''',
},

{
    "field": "version",
    "type": "number",
    "sample_printable": 2,
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
]
}