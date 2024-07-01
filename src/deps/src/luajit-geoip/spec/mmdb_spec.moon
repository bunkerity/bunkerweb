
country_db = "/var/lib/GeoIP/GeoLite2-Country.mmdb"
city_db = "/var/lib/GeoIP/GeoLite2-City.mmdb"
asnum_db = "/var/lib/GeoIP/GeoLite2-ASN.mmdb"

mmdb = require "geoip.mmdb"

describe "mmdb", ->
  it "handles invalid database path", ->
    assert.same {nil, "failed to load db: hello.world.db"}, {
      mmdb.load_database "hello.world.db"
    }

  it "handles invalid database file", ->
    assert.same {nil, "failed to load db: README.md"}, {
      mmdb.load_database "README.md"
    }

  describe "asnum_db", ->
    local db
    before_each ->
      db = assert mmdb.load_database asnum_db

    it "looks up address", ->
      out = assert db\lookup "1.1.1.1"
      assert.same {
        autonomous_system_organization: "CLOUDFLARENET"
        autonomous_system_number: 13335
      }, out

    it "looks up localhost", ->
      assert.same {nil, "failed to find entry"}, {db\lookup "127.0.0.1"}

    it "looks up invalid address", ->
      assert.same {
        nil, "gai error: Name or service not known"
      }, {db\lookup "efjlewfk"}

    it "looks up ipv6", ->
      assert.same {
        autonomous_system_number: 15169
        autonomous_system_organization: "GOOGLE"
      }, db\lookup "2001:4860:4860::8888"

  describe "country_db", ->
    local db
    before_each ->
      db = assert mmdb.load_database country_db

    it "looks up address", ->
      out = assert db\lookup "8.8.8.8"
      assert.same {
        continent: {
          code: 'NA'
          geoname_id: 6255149
          names: {
            "de": 'Nordamerika'
            "en": 'North America'
            "es": 'Norteamérica'
            "fr": 'Amérique du Nord'
            "ja": '北アメリカ'
            "pt-BR": 'América do Norte'
            "ru": 'Северная Америка'
            "zh-CN": '北美洲'
          }
        }
        country: {
          geoname_id: 6252001
          iso_code: 'US'
          names: {
            "de": 'USA'
            "en": 'United States'
            "es": 'Estados Unidos'
            "fr": 'États-Unis'
            "ja": 'アメリカ合衆国'
            "pt-BR": 'Estados Unidos'
            "ru": 'США'
            "zh-CN": '美国'
          }
        }
        registered_country: {
          geoname_id: 6252001
          iso_code: 'US'
          names: {
            "de": 'USA'
            "en": 'United States'
            "es": 'Estados Unidos'
            "fr": 'États-Unis'
            "ja": 'アメリカ合衆国'
            "pt-BR": 'Estados Unidos'
            "ru": 'США'
            "zh-CN": '美国'
          }
        }
      }, out

    it "looks up EU address 212.237.134.97", ->
      out = assert db\lookup "212.237.134.97"
      assert.same {
        continent: {
          code: 'EU'
          geoname_id: 6255148
          names: {
            "de": 'Europa'
            "en": 'Europe'
            "es": 'Europa'
            "fr": 'Europe'
            "ja": 'ヨーロッパ'
            "pt-BR": 'Europa'
            "ru": 'Европа'
            "zh-CN": '欧洲'
          }
        }
        country: {
          geoname_id: 2623032
          is_in_european_union: true
          iso_code: 'DK'
          names: {
            "de": 'Dänemark'
            "en": 'Denmark'
            "es": 'Dinamarca'
            "fr": 'Danemark'
            "ja": 'デンマーク王国'
            "pt-BR": 'Dinamarca'
            "ru": 'Дания'
            "zh-CN": '丹麦'
          }
        }
        registered_country: {
          geoname_id: 2623032
          is_in_european_union: true
          iso_code: 'DK'
          names: {
            "de": 'Dänemark'
            "en": 'Denmark'
            "es": 'Dinamarca'
            "fr": 'Danemark'
            "ja": 'デンマーク王国'
            "pt-BR": 'Dinamarca'
            "ru": 'Дания'
            "zh-CN": '丹麦'
          }
        }
      }, out

    describe "lookup_value", ->
      it "looks up string value", ->
        res = assert db\lookup_value "8.8.8.8", "country", "iso_code"
        assert.same "US", res

      it "looks up number value", ->
        res = assert db\lookup_value "8.8.8.8", "continent", "geoname_id"
        assert.same 6255149, res

      it "handles looking up invalid path", ->
        assert.same {nil, "failed to find field by path"}, {
          db\lookup_value "8.8.8.8", "continent", "fart"
        }

      it "handles missing path", ->
        assert.has_error(
          -> db\lookup_value "8.8.8.8"
          "missing path"
        )

      it "handles invalid root", ->
        assert.same {nil, "failed to find field by path"}, {
          db\lookup_value "8.8.8.8", "butt"
        }

      it "returning object field", ->
        assert.same {nil, "path holds object, not value"}, {
          db\lookup_value "8.8.8.8", "continent"
        }

  describe "city_db", ->
    local db
    before_each ->
      db = assert mmdb.load_database city_db

    it "looks up address", ->
      out = assert db\lookup "1.1.1.1"
      assert.same {
        accuracy_radius: 1000
        longitude: 143.2104
        latitude: -33.494
        time_zone: "Australia/Sydney"
      }, out.location

    it "looks up address with subdivisions (an array)", ->
      out = assert db\lookup "173.255.250.29"
      assert.same {
        {
          names: {
            "en": "California"
            "zh-CN": "加利福尼亚州"
            "fr": "Californie"
            "ru": "Калифорния"
            "es": "California"
            "pt-BR": "Califórnia"
            "de": "Kalifornien"
            "ja": "カリフォルニア州"
          }
          iso_code: "CA"
          geoname_id: 5332921
        }
      }, out.subdivisions

      assert.same "94536", out.postal.code

