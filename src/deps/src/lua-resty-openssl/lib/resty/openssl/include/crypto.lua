local ffi = require "ffi"
local C = ffi.C

ffi.cdef [[
  int FIPS_mode(void);
  int FIPS_mode_set(int ONOFF);
  void CRYPTO_free(void *ptr, const char *file, int line);
]]

local OPENSSL_free = function(ptr)
  -- file and line is for debuggin only, since we can't know the c file info
  -- the macro is expanded, just ignore this
  C.CRYPTO_free(ptr, "", 0)
end


return {
  OPENSSL_free = OPENSSL_free,
}
