local ffi = require "ffi"

ffi.cdef [[
typedef struct _IO_FILE FILE;
FILE *fopen(const char *pathname, const char *mode);
int fileno(FILE *stream);
int fclose(FILE *stream);
int flock(int fd, int operation);
]]

local M = {}

function M.run(path, callback)
  -- Open in the worker for every acquisition: flock ownership belongs to the open
  -- file description, which must never be inherited from the NGINX master.
  local file = ffi.C.fopen(path, "a+e") -- Linux libc 'e' sets close-on-exec.
  if file == nil then return nil, "Stream lock unavailable" end
  ffi.gc(file, ffi.C.fclose)
  local fd = ffi.C.fileno(file)
  if fd < 0 or ffi.C.flock(fd, 6) ~= 0 then -- LOCK_EX | LOCK_NB
    local errno = ffi.errno()
    ffi.gc(file, nil)
    ffi.C.fclose(file)
    return nil, errno == 11 and "busy" or "Stream lock unavailable"
  end
  local ok = pcall(callback)
  ffi.gc(file, nil)
  ffi.C.fclose(file) -- Releases the lock; never unlink its shared inode.
  if not ok then return nil, "Stream synchronization failed" end
  return true
end

return M
