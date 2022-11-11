
import lookup_addr from require "geoip"

describe "geoip", ->
  it "looks up address", ->
    assert.same {
      asnum: "AS15169 GOOGLE"
      country_code: "US"
      country_name: "United States"
    }, lookup_addr "8.8.8.8"

  it "looks up bad address", ->
    assert.same nil, (lookup_addr "helloo.world")


  it "manually instantiates database with memory lookup", ->
    import GeoIP from require "geoip"
    geoip = GeoIP!
    geoip\load_databases "memory"
    assert.truthy lookup_addr "8.8.8.8"


