ffi = require "ffi"
bit = require "bit"

-- extracted from /usr/include/maxminddb.h

-- flags for open
MMDB_MODE_MMAP = 1
MMDB_MODE_MASK = 7

-- error codes
MMDB_SUCCESS = 0
MMDB_FILE_OPEN_ERROR = 1
MMDB_CORRUPT_SEARCH_TREE_ERROR = 2
MMDB_INVALID_METADATA_ERROR = 3
MMDB_IO_ERROR = 4
MMDB_OUT_OF_MEMORY_ERROR = 5
MMDB_UNKNOWN_DATABASE_FORMAT_ERROR = 6
MMDB_INVALID_DATA_ERROR = 7
MMDB_INVALID_LOOKUP_PATH_ERROR = 8
MMDB_LOOKUP_PATH_DOES_NOT_MATCH_DATA_ERROR = 9
MMDB_INVALID_NODE_NUMBER_ERROR = 10
MMDB_IPV6_LOOKUP_IN_IPV4_DATABASE_ERROR = 11

-- data types
DATA_TYPES = {
  MMDB_DATA_TYPE_EXTENDED: 0
  MMDB_DATA_TYPE_POINTER: 1
  MMDB_DATA_TYPE_UTF8_STRING: 2
  MMDB_DATA_TYPE_DOUBLE: 3
  MMDB_DATA_TYPE_BYTES: 4
  MMDB_DATA_TYPE_UINT16: 5
  MMDB_DATA_TYPE_UINT32: 6
  MMDB_DATA_TYPE_MAP: 7
  MMDB_DATA_TYPE_INT32: 8
  MMDB_DATA_TYPE_UINT64: 9
  MMDB_DATA_TYPE_UINT128: 10
  MMDB_DATA_TYPE_ARRAY: 11
  MMDB_DATA_TYPE_CONTAINER: 12
  MMDB_DATA_TYPE_END_MARKER: 13
  MMDB_DATA_TYPE_BOOLEAN: 14
  MMDB_DATA_TYPE_FLOAT: 15
}

for key in *[k for k in pairs DATA_TYPES]
  DATA_TYPES[DATA_TYPES[key]] = key

ffi.cdef [[
  const char *gai_strerror(int ecode);

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
]]

lib = ffi.load "libmaxminddb"

local consume_map, consume_array

consume_value = (current) ->
  if current == nil
    return nil, "expected value but go nothing"

  entry_data = current.entry_data

  switch entry_data.type
    when DATA_TYPES.MMDB_DATA_TYPE_MAP
      assert consume_map current
    when DATA_TYPES.MMDB_DATA_TYPE_ARRAY
      assert consume_array current
    when DATA_TYPES.MMDB_DATA_TYPE_UTF8_STRING
      value = ffi.string entry_data.utf8_string, entry_data.data_size
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_UINT32
      value = entry_data.uint32
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_UINT16
      value = entry_data.uint16
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_INT32
      value = entry_data.int32
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_UINT64
      value = entry_data.uint64
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_DOUBLE
      value = entry_data.double_value
      value, current.next
    when DATA_TYPES.MMDB_DATA_TYPE_BOOLEAN
      assert entry_data.boolean ~= nil
      value = entry_data.boolean
      value, current.next
    else
      error "unknown type: #{DATA_TYPES[entry_data.type]}"
      nil, current.next

consume_map = (current) ->
  out = {}

  map = current.entry_data
  tuple_count = map.data_size

  -- move to first value
  current = current.next

  while tuple_count > 0
    key, current = assert consume_value current
    value, current = consume_value current
    out[key] = value
    tuple_count -= 1

  out, current

consume_array = (current) ->
  out = {}

  array = current.entry_data
  length = array.data_size

  -- move to first value
  current = current.next

  while length > 0
    value, current = assert consume_value current
    table.insert out, value
    length -= 1

  out, current

class Mmdb
  new: (@file_path, @opts) =>

  load: =>
    @mmdb = ffi.new "MMDB_s"
    res = lib.MMDB_open @file_path, 0, @mmdb

    unless res == MMDB_SUCCESS
      return nil, "failed to load db: #{@file_path}"

    ffi.gc @mmdb, (assert lib.MMDB_close, "missing destructor")
    true

  _lookup_string: (ip) =>
    assert @mmdb, "mmdb database is not loaded"

    gai_error = ffi.new "int[1]"
    mmdb_error = ffi.new "int[1]"

    res = lib.MMDB_lookup_string @mmdb, ip, gai_error, mmdb_error

    unless gai_error[0] == MMDB_SUCCESS
      return nil, "gai error: #{ffi.string lib.gai_strerror gai_error[0]}"

    unless mmdb_error[0] == MMDB_SUCCESS
      return nil, "mmdb error: #{ffi.string lib.MMDB_strerror mmdb_error[0]}"

    unless res.found_entry
      return nil, "failed to find entry"

    res

  lookup_value: (ip, ...) =>
    assert (...), "missing path"
    path = {...}
    table.insert path, 0

    res, err = @_lookup_string ip
    unless res
      return nil, err

    entry_data = ffi.new "MMDB_entry_data_s"

    status = lib.MMDB_get_value res.entry, entry_data, unpack path

    if MMDB_SUCCESS != status
      return nil, "failed to find field by path"

    if entry_data.has_data
      -- the node we get don't have the data so we have to bail if path leads
      -- to a map or array
      switch entry_data.type
        when DATA_TYPES.MMDB_DATA_TYPE_MAP, DATA_TYPES.MMDB_DATA_TYPE_ARRAY
          return nil, "path holds object, not value"

      value = assert consume_value {
        :entry_data
      }

      value
    else
      nil, "entry has no data"

  lookup: (ip) =>
    res, err = @_lookup_string ip

    unless res
      return nil, err

    entry_data_list = ffi.new "MMDB_entry_data_list_s*[1]"

    status = lib.MMDB_get_entry_data_list res.entry, entry_data_list

    unless status == MMDB_SUCCESS
      return nil, "failed to load data: #{ffi.string lib.MMDB_strerror status}"

    ffi.gc entry_data_list[0], (assert lib.MMDB_free_entry_data_list, "missing destructor")

    current = entry_data_list[0]
    value = assert consume_value current

    value

load_database = (filename) ->
  mmdb = Mmdb filename
  success, err = mmdb\load!
  unless success
    return nil, err
  mmdb

{
  :Mmdb
  :load_database
  VERSION: require "geoip.version"
}
