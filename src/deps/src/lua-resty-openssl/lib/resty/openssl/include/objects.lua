local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  int OBJ_obj2txt(char *buf, int buf_len, const ASN1_OBJECT *a, int no_name);
  ASN1_OBJECT *OBJ_txt2obj(const char *s, int no_name);
  int OBJ_txt2nid(const char *s);
  const char *OBJ_nid2sn(int n);
  int OBJ_ln2nid(const char *s);
  int OBJ_sn2nid(const char *s);
  const char *OBJ_nid2ln(int n);
  const char *OBJ_nid2sn(int n);
  int OBJ_obj2nid(const ASN1_OBJECT *o);
  const ASN1_OBJECT *OBJ_nid2obj(int n);
  int OBJ_create(const char *oid, const char *sn, const char *ln);

  int OBJ_find_sigid_algs(int signid, int *pdig_nid, int *ppkey_nid);
]]
