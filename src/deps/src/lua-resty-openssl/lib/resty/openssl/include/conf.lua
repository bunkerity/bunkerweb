local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
    CONF *NCONF_new(CONF_METHOD *meth);
    void NCONF_free(CONF *conf);
    int NCONF_load_bio(CONF *conf, BIO *bp, long *eline);
]]