local geoip = require "geoip.mmdb"

-- Databases are refreshed by the geoip core plugin's jobs. load_database returns nil
-- when the file is missing, which is the normal state for city : it is opt-in
-- (GEOIP_CITY) and is not bundled in the images, so callers must handle a nil db.
return {
	country_db = geoip.load_database "/var/cache/bunkerweb/geoip/country.mmdb",
	asn_db = geoip.load_database "/var/cache/bunkerweb/geoip/asn.mmdb",
	city_db = geoip.load_database "/var/cache/bunkerweb/geoip/city.mmdb",
}
