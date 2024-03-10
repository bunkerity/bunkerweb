local geoip = require "geoip.mmdb"

return {
	country_db = geoip.load_database "/var/cache/bunkerweb/jobs/country.mmdb",
	asn_db = geoip.load_database "/var/cache/bunkerweb/jobs/asn.mmdb",
}
