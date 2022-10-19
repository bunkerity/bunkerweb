local geoip = require "geoip.mmdb"

return {
	country_db = geoip.load_database("/opt/bunkerweb/cache/country.mmdb"),
	asn_db = geoip.load_database("/opt/bunkerweb/cache/asn.mmdb")
}