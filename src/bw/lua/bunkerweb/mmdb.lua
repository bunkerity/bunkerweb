local geoip = require "geoip.mmdb"

return {
	country_db = geoip.load_database("/var/cache/bunkerweb/country.mmdb"),
	asn_db = geoip.load_database("/var/cache/bunkerweb/asn.mmdb")
}
