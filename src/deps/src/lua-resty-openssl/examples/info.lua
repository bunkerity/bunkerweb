local version=require "resty.openssl.version"

print("VERSION:")

local version_table = {
  "VERSION",
  "CFLAGS",
  "BUILT_ON",
  "PLATFORM",
  "DIR",
  "ENGINES_DIR",
  "VERSION_STRING",
  "FULL_VERSION_STRING",
  "MODULES_DIR",
  "CPU_INFO",
}

for _, k in ipairs(version_table) do
	print(string.format("%20s: %s", k, version.version(version[k])))
end

print(string.rep("-", 64))

if version.OPENSSL_3X then

  print("INFO:")
  local info_table = {
    "INFO_CONFIG_DIR",
    "INFO_ENGINES_DIR",
    "INFO_MODULES_DIR",
    "INFO_DSO_EXTENSION",
    "INFO_DIR_FILENAME_SEPARATOR",
    "INFO_LIST_SEPARATOR",
    "INFO_SEED_SOURCE",
    "INFO_CPU_SETTINGS",
  }

  for _, k in ipairs(info_table) do
    print(string.format("%20s: %s", k, version.info(version[k])))
  end

  print(string.rep("-", 64))

  print("PROVIDER:")
  local pro = require "resty.openssl.provider"

  for _, n in ipairs({"default", "legacy", "fips", "null"}) do
    local ok, err = pro.load(n)
    print(string.format("%10s  load: %s", n, ok or err))
  end
end

