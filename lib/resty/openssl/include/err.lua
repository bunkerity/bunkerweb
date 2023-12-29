local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

ffi.cdef [[
  unsigned long ERR_peek_error(void);
  unsigned long ERR_peek_last_error(void);
  void ERR_clear_error(void);
  void ERR_error_string_n(unsigned long e, char *buf, size_t len);
  const char *ERR_lib_error_string(unsigned long e);
  const char *ERR_reason_error_string(unsigned long e);
]]

if OPENSSL_3X then
  ffi.cdef [[
    unsigned long ERR_get_error_all(const char **file, int *line,
                                    const char **func,
                                    const char **data, int *flags);
    unsigned long ERR_peek_last_error_all(const char **file, int *line,
                                          const char **func,
                                          const char **data, int *flags);
    ]]

else
  ffi.cdef [[
    unsigned long ERR_get_error_line(const char **file, int *line);
    unsigned long ERR_peek_last_error_line(const char **file, int *line);
  ]]
end