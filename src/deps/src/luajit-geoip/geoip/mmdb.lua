local ffi = require("ffi")
local bit = require("bit")
local MMDB_MODE_MMAP = 1
local MMDB_MODE_MASK = 7
local MMDB_SUCCESS = 0
local MMDB_FILE_OPEN_ERROR = 1
local MMDB_CORRUPT_SEARCH_TREE_ERROR = 2
local MMDB_INVALID_METADATA_ERROR = 3
local MMDB_IO_ERROR = 4
local MMDB_OUT_OF_MEMORY_ERROR = 5
local MMDB_UNKNOWN_DATABASE_FORMAT_ERROR = 6
local MMDB_INVALID_DATA_ERROR = 7
local MMDB_INVALID_LOOKUP_PATH_ERROR = 8
local MMDB_LOOKUP_PATH_DOES_NOT_MATCH_DATA_ERROR = 9
local MMDB_INVALID_NODE_NUMBER_ERROR = 10
local MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR = 11
local DATA_TYPES = {
  MMDB_DATA_TYPE_EXTENDED = 0,
  MMDB_DATA_TYPE_POINTER = 1,
  MMDB_DATA_TYPE_UTF8_STRING = 2,
  MMDB_DATA_TYPE_DOUBLE = 3,
  MMDB_DATA_TYPE_BYTES = 4,
  MMDB_DATA_TYPE_UINT16 = 5,
  MMDB_DATA_TYPE_UINT32 = 6,
  MMDB_DATA_TYPE_MAP = 7,
  MMDB_DATA_TYPE_INT32 = 8,
  MMDB_DATA_TYPE_UINT64 = 9,
  MMDB_DATA_TYPE_UINT128 = 10,
  MMDB_DATA_TYPE_ARRAY = 11,
  MMDB_DATA_TYPE_CONTAINER = 12,
  MMDB_DATA_TYPE_END_MARKER = 13,
  MMDB_DATA_TYPE_BOOLEAN = 14,
  MMDB_DATA_TYPE_FLOAT = 15
}
local _list_0
do
  local _accum_0 = { }
  local _len_0 = 1
  for k in pairs(DATA_TYPES) do
    _accum_0[_len_0] = k
    _len_0 = _len_0 + 1
  end
  _list_0 = _accum_0
end
for _index_0 = 1, #_list_0 do
  local key = _list_0[_index_0]
  DATA_TYPES[DATA_TYPES[key]] = key
end
ffi.cdef([[  const char *gai_strerror(int ecode);

  typedef unsigned int mmdb_uint128_t __attribute__ ((__mode__(TI)));

  typedef struct MMDB_entry_s {
      const struct MMDB_s *mmdb;
      uint32_t offset;
  } MMDB_entry_s;

  typedef struct MMDB_lookup_result_s {
      bool found_entry;
      MMDB_entry_s entry;
      uint16_t netmask;
  } MMDB_lookup_result_s;


  typedef struct MMDB_entry_data_s {
      bool has_data;
      union {
          uint32_t pointer;
          const char *utf8_string;
          double double_value;
          const uint8_t *bytes;
          uint16_t uint16;
          uint32_t uint32;
          int32_t int32;
          uint64_t uint64;
          mmdb_uint128_t uint128;
          bool boolean;
          float float_value;
      };
      /* This is a 0 if a given entry cannot be found. This can only happen
       * when a call to MMDB_(v)get_value() asks for hash keys or array
       * indices that don't exist. */
      uint32_t offset;
      /* This is the next entry in the data section, but it's really only
       * relevant for entries that part of a larger map or array
       * struct. There's no good reason for an end user to look at this
       * directly. */
      uint32_t offset_to_next;
      /* This is only valid for strings, utf8_strings or binary data */
      uint32_t data_size;
      /* This is an MMDB_DATA_TYPE_* constant */
      uint32_t type;
  } MMDB_entry_data_s;

  typedef struct MMDB_entry_data_list_s {
      MMDB_entry_data_s entry_data;
      struct MMDB_entry_data_list_s *next;
      void *pool;
  } MMDB_entry_data_list_s;

  typedef struct MMDB_description_s {
      const char *language;
      const char *description;
  } MMDB_description_s;

  typedef struct MMDB_metadata_s {
      uint32_t node_count;
      uint16_t record_size;
      uint16_t ip_version;
      const char *database_type;
      struct {
          size_t count;
          const char **names;
      } languages;
      uint16_t binary_format_major_version;
      uint16_t binary_format_minor_version;
      uint64_t build_epoch;
      struct {
          size_t count;
          MMDB_description_s **descriptions;
      } description;
      /* See above warning before adding fields */
  } MMDB_metadata_s;

  typedef struct MMDB_ipv4_start_node_s {
      uint16_t netmask;
      uint32_t node_value;
      /* See above warning before adding fields */
  } MMDB_ipv4_start_node_s;

  typedef struct MMDB_s {
      uint32_t flags;
      const char *filename;
      ssize_t file_size;
      const uint8_t *file_content;
      const uint8_t *data_section;
      uint32_t data_section_size;
      const uint8_t *metadata_section;
      uint32_t metadata_section_size;
      uint16_t full_record_byte_size;
      uint16_t depth;
      MMDB_ipv4_start_node_s ipv4_start_node;
      MMDB_metadata_s metadata;
      /* See above warning before adding fields */
  } MMDB_s;

  extern int MMDB_open(const char *const filename, uint32_t flags,
                     MMDB_s *const mmdb);

  extern void MMDB_close(MMDB_s *const mmdb);

  extern MMDB_lookup_result_s MMDB_lookup_string(const MMDB_s *const mmdb,
                                                 const char *const ipstr,
                                                 int *const gai_error,
                                                 int *const mmdb_error);

  extern const char *MMDB_strerror(int error_code);

  extern int MMDB_get_entry_data_list(
      MMDB_entry_s *start, MMDB_entry_data_list_s **const entry_data_list);

  extern void MMDB_free_entry_data_list(
      MMDB_entry_data_list_s *const entry_data_list);

  extern int MMDB_get_value(MMDB_entry_s *const start,
                            MMDB_entry_data_s *const entry_data,
                            ...);
]])
local lib = ffi.load("libmaxminddb")
local consume_map, consume_array
local consume_value
consume_value = function(current)
  if current == nil then
    return nil, "expected value but go nothing"
  end
  local entry_data = current.entry_data
  local _exp_0 = entry_data.type
  if DATA_TYPES.MMDB_DATA_TYPE_MAP == _exp_0 then
    return assert(consume_map(current))
  elseif DATA_TYPES.MMDB_DATA_TYPE_ARRAY == _exp_0 then
    return assert(consume_array(current))
  elseif DATA_TYPES.MMDB_DATA_TYPE_UTF8_STRING == _exp_0 then
    local value = ffi.string(entry_data.utf8_string, entry_data.data_size)
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_UINT32 == _exp_0 then
    local value = entry_data.uint32
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_UINT16 == _exp_0 then
    local value = entry_data.uint16
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_INT32 == _exp_0 then
    local value = entry_data.int32
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_UINT64 == _exp_0 then
    local value = entry_data.uint64
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_DOUBLE == _exp_0 then
    local value = entry_data.double_value
    return value, current.next
  elseif DATA_TYPES.MMDB_DATA_TYPE_BOOLEAN == _exp_0 then
    assert(entry_data.boolean ~= nil)
    local value = entry_data.boolean
    return value, current.next
  else
    error("unknown type: " .. tostring(DATA_TYPES[entry_data.type]))
    return nil, current.next
  end
end
consume_map = function(current)
  local out = { }
  local map = current.entry_data
  local tuple_count = map.data_size
  current = current.next
  while tuple_count > 0 do
    local key
    key, current = assert(consume_value(current))
    local value
    value, current = consume_value(current)
    out[key] = value
    tuple_count = tuple_count - 1
  end
  return out, current
end
consume_array = function(current)
  local out = { }
  local array = current.entry_data
  local length = array.data_size
  current = current.next
  while length > 0 do
    local value
    value, current = assert(consume_value(current))
    table.insert(out, value)
    length = length - 1
  end
  return out, current
end
local Mmdb
do
  local _class_0
  local _base_0 = {
    load = function(self)
      self.mmdb = ffi.new("MMDB_s")
      local res = lib.MMDB_open(self.file_path, 0, self.mmdb)
      if not (res == MMDB_SUCCESS) then
        return nil, "failed to load db: " .. tostring(self.file_path)
      end
      ffi.gc(self.mmdb, (assert(lib.MMDB_close, "missing destructor")))
      return true
    end,
    _lookup_string = function(self, ip)
      assert(self.mmdb, "mmdb database is not loaded")
      local gai_error = ffi.new("int[1]")
      local mmdb_error = ffi.new("int[1]")
      local res = lib.MMDB_lookup_string(self.mmdb, ip, gai_error, mmdb_error)
      if not (gai_error[0] == MMDB_SUCCESS) then
        return nil, "gai error: " .. tostring(ffi.string(lib.gai_strerror(gai_error[0])))
      end
      if not (mmdb_error[0] == MMDB_SUCCESS) then
        return nil, "mmdb error: " .. tostring(ffi.string(lib.MMDB_strerror(mmdb_error[0])))
      end
      if not (res.found_entry) then
        return nil, "failed to find entry"
      end
      return res
    end,
    lookup_value = function(self, ip, ...)
      assert((...), "missing path")
      local path = {
        ...
      }
      table.insert(path, 0)
      local res, err = self:_lookup_string(ip)
      if not (res) then
        return nil, err
      end
      local entry_data = ffi.new("MMDB_entry_data_s")
      local status = lib.MMDB_get_value(res.entry, entry_data, unpack(path))
      if MMDB_SUCCESS ~= status then
        return nil, "failed to find field by path"
      end
      if entry_data.has_data then
        local _exp_0 = entry_data.type
        if DATA_TYPES.MMDB_DATA_TYPE_MAP == _exp_0 or DATA_TYPES.MMDB_DATA_TYPE_ARRAY == _exp_0 then
          return nil, "path holds object, not value"
        end
        local value = assert(consume_value({
          entry_data = entry_data
        }))
        return value
      else
        return nil, "entry has no data"
      end
    end,
    lookup = function(self, ip)
      local res, err = self:_lookup_string(ip)
      if not (res) then
        return nil, err
      end
      local entry_data_list = ffi.new("MMDB_entry_data_list_s*[1]")
      local status = lib.MMDB_get_entry_data_list(res.entry, entry_data_list)
      if not (status == MMDB_SUCCESS) then
        return nil, "failed to load data: " .. tostring(ffi.string(lib.MMDB_strerror(status)))
      end
      ffi.gc(entry_data_list[0], (assert(lib.MMDB_free_entry_data_list, "missing destructor")))
      local current = entry_data_list[0]
      local value = assert(consume_value(current))
      return value
    end
  }
  _base_0.__index = _base_0
  _class_0 = setmetatable({
    __init = function(self, file_path, opts)
      self.file_path, self.opts = file_path, opts
    end,
    __base = _base_0,
    __name = "Mmdb"
  }, {
    __index = _base_0,
    __call = function(cls, ...)
      local _self_0 = setmetatable({}, _base_0)
      cls.__init(_self_0, ...)
      return _self_0
    end
  })
  _base_0.__class = _class_0
  Mmdb = _class_0
end
local load_database
load_database = function(filename)
  local mmdb = Mmdb(filename)
  local success, err = mmdb:load()
  if not (success) then
    return nil, err
  end
  return mmdb
end
return {
  Mmdb = Mmdb,
  load_database = load_database,
  VERSION = require("geoip.version")
}
