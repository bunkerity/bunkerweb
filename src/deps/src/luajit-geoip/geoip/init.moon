ffi = require "ffi"
bit = require "bit"

ffi.cdef [[
  typedef struct GeoIP {} GeoIP;

  typedef enum {
    GEOIP_STANDARD = 0,
    GEOIP_MEMORY_CACHE = 1,
    GEOIP_CHECK_CACHE = 2,
    GEOIP_INDEX_CACHE = 4,
    GEOIP_MMAP_CACHE = 8,
    GEOIP_SILENCE = 16,
  } GeoIPOptions;

  typedef enum {
    GEOIP_COUNTRY_EDITION = 1,
    GEOIP_CITY_EDITION_REV1 = 2,
    GEOIP_ASNUM_EDITION = 9,
  } GeoIPDBTypes;

  typedef enum {
    GEOIP_CHARSET_ISO_8859_1 = 0,
    GEOIP_CHARSET_UTF8 = 1
  } GeoIPCharset;

  int GeoIP_db_avail(int type);
  GeoIP * GeoIP_open_type(int type, int flags);

  void GeoIP_delete(GeoIP * gi);
  char *GeoIP_database_info(GeoIP * gi);

  int GeoIP_charset(GeoIP * gi);
  int GeoIP_set_charset(GeoIP * gi, int charset);

  unsigned long _GeoIP_lookupaddress(const char *host);

  char *GeoIP_name_by_addr(GeoIP * gi, const char *addr);
  int GeoIP_id_by_addr(GeoIP * gi, const char *addr);

  unsigned GeoIP_num_countries(void);
  const char * GeoIP_code_by_id(int id);
  const char * GeoIP_country_name_by_id(GeoIP * gi, int id);
]]

lib = ffi.load "GeoIP"

DATABASE_TYPES = {
  lib.GEOIP_COUNTRY_EDITION
  lib.GEOIP_ASNUM_EDITION
}

CACHE_TYPES = {
  standard: lib.GEOIP_STANDARD
  memory: lib.GEOIP_MEMORY_CACHE
  check: lib.GEOIP_CHECK_CACHE
  index: lib.GEOIP_INDEX_CACHE
}

class GeoIP
  new: =>

  load_databases: (mode=lib.GEOIP_STANDARD) =>
    mode = CACHE_TYPES[mode] or mode
    return if @databases
    @databases = for i in *DATABASE_TYPES
      continue unless 1 == lib.GeoIP_db_avail(i)

      gi = lib.GeoIP_open_type i, bit.bor mode, lib.GEOIP_SILENCE
      continue if gi == nil
      ffi.gc gi, (assert lib.GeoIP_delete, "missing destructor")
      lib.GeoIP_set_charset gi, lib.GEOIP_CHARSET_UTF8

      {
        type: i
        :gi
      }

    true

  country_by_id: (gi, id) =>
    if id < 0 or id >= lib.GeoIP_num_countries!
      return

    code = lib.GeoIP_code_by_id id
    country = lib.GeoIP_country_name_by_id gi, id

    code = code != nil and ffi.string(code) or nil
    country = country != nil and ffi.string(country) or nil
    code = nil if code == "--"

    code, country

  lookup_addr: (ip) =>
    @load_databases!

    out = {}
    for {:type, :gi} in *@databases
      switch type
        when lib.GEOIP_COUNTRY_EDITION
          cid = lib.GeoIP_id_by_addr gi, ip
          out.country_code, out.country_name = @country_by_id gi, cid
        when lib.GEOIP_ASNUM_EDITION
          asnum = lib.GeoIP_name_by_addr gi, ip
          continue if asnum == nil
          out.asnum = ffi.string asnum

    out if next out

{
  :GeoIP
  lookup_addr: GeoIP!\lookup_addr
  VERSION: require "geoip.version"
}

