local geoip = require "geoip.mmdb"
local logger = require("bunkerweb.logger"):new("MMDB")

local ERR = ngx.ERR
local open = io.open

-- Databases are refreshed by the geoip core plugin's jobs. load_database returns nil
-- when the file is missing, which is the normal state for city : it is opt-in
-- (GEOIP_CITY) and is not bundled in the images, so callers must handle a nil db.
--
-- A file that IS on disk and still fails to open is a fault, not a configuration : a
-- truncated cache push, a corrupt download, a permission problem. Discarding load_database's
-- error made the two indistinguishable -- utils.get_city/get_country then return false
-- ("not loaded") forever, $bw_city / $bw_country stay empty, and nothing anywhere says why.
-- Report that case, and only that case, so "opt-in and off" stays quiet.
local function load(kind, path)
	local db, err = geoip.load_database(path)
	if db then
		return db
	end
	local file = open(path, "r")
	if not file then
		-- Absent: the normal state for city, and for country/asn before the first job run.
		return nil
	end
	file:close()
	logger:log(ERR, path .. " exists but could not be opened as a " .. kind .. " database : " .. tostring(err))
	return nil
end

return {
	country_db = load("country", "/var/cache/bunkerweb/geoip/country.mmdb"),
	asn_db = load("asn", "/var/cache/bunkerweb/geoip/asn.mmdb"),
	city_db = load("city", "/var/cache/bunkerweb/geoip/city.mmdb"),
}
