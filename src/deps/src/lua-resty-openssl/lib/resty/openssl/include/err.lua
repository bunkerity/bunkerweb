local ffi = require "ffi"

ffi.cdef [[
  unsigned long ERR_peek_error(void);
  unsigned long ERR_peek_last_error_line(const char **file, int *line);
  unsigned long ERR_get_error_line(const char **file, int *line);
  void ERR_clear_error(void);
  void ERR_error_string_n(unsigned long e, char *buf, size_t len);
]]
