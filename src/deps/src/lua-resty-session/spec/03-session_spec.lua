local session = require "resty.session"


local before_each = before_each
local describe = describe
local assert = assert
local pcall = pcall
local it = it


local function extract_cookie(cookie_name, cookies)
  local session_cookie
  if type(cookies) == "table" then
    for _, v in ipairs(cookies) do
      session_cookie = ngx.re.match(v, cookie_name .. "=([\\w-]+);")
      if session_cookie then
        return session_cookie[1]
      end
    end
    return ""
  end
  session_cookie = ngx.re.match(cookies, cookie_name .. "=([\\w-]+);")
  return session_cookie and session_cookie[1] or ""
end


describe("Session", function()
  local configuration = {}

  describe("instance methods behave as expected", function()
    local cookie_name          = "session_cookie"
    local remember_cookie_name = "remember_cookie"
    local test_key             = "test_key"
    local data                 = "test_data"
    local test_subject         = "test_subject"
    local test_audience        = "test_audience"
    local lout_subject         = "lout_subject"
    local lout_audience        = "lout_audience"

    local function test_session_set_get(s)
      assert.is_nil(
        s:get(test_key)      or
        s:get(test_subject)  or
        s:get(test_audience)
      )

      s:set(test_key, data)
      s:set_subject(test_subject)
      s:set_audience(test_audience)

      assert.equals(s:get(test_key), data)
      assert.equals(s:get_subject(), test_subject)
      assert.equals(s:get_audience(), test_audience)
    end

    local function test_session_save(s, cookies)
      session.__set_ngx_header(cookies)

      local ok, err = s:save()

      assert.equals(s.state, "open")
      assert.is_true(ok)
      assert.is_nil(err)
      assert.is_not_nil(s.meta)
      assert.is_not_nil(s.meta.data_size)
      assert(s.meta.data_size > 0)

      local session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      return session_cookie
    end

    local function test_session_close_open(s, session_cookie)
      s:close()

      assert.equals(s.state, "closed")

      local ok, err = pcall(s.get, s, "anything")
      assert.is_false(ok)
      assert.matches("unable to get session data", err)

      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie
      })

      ok, err = s:open()
      assert.is_true(ok)
      assert.is_nil(err)
      assert.equals(s.state, "open")
      assert.equals(data, s:get(test_key))
    end

    local function test_session_get_property(s)
      assert.equals(43, #s:get_property("id"))
      assert.equals(32, #s:get_property("nonce"))
      assert.equals(test_audience, s:get_property("audience"))
      assert.equals(test_subject, s:get_property("subject"))
      assert.match.is_number(s:get_property("timeout"))
      assert.match.is_number(s:get_property("idling-timeout"))
      assert.match.is_number(s:get_property("rolling-timeout"))
      assert.match.is_number(s:get_property("absolute-timeout"))
    end

    local function test_session_touch(s)
       local ok, err = s:touch()
       assert.is_true(ok)
       assert.is_nil(err)
       assert.equals(s.state, "open")
    end

    local function test_session_destroy_open(s)
      local cookies = {}

      session.__set_ngx_header(cookies)

      local ok, err = s:destroy()
      assert.is_true(ok)
      assert.is_nil(err)
      assert.equals(s.state, "closed")

      ok, err = pcall(s.get, s, "anything")
      assert.is_false(ok)
      assert.matches("unable to get session data", err)

      local session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"]) -- empty

      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie
      })

      ok, err = s:open()
      assert.is_nil(ok)
      assert.equals("invalid session header", err)
      assert.equals(s.state, "closed")

      ok, err = pcall(s.get, s, "anything")
      assert.is_false(ok)
      assert.matches("unable to get session data", err)
    end

    local function test_session(s)
      local session_cookie
      local cookies = {}

      test_session_set_get(s)
      session_cookie = test_session_save(s, cookies)
      test_session_close_open(s, session_cookie)
      test_session_get_property(s)
      test_session_touch(s)
      test_session_destroy_open(s)
    end

    before_each(function()
      configuration = {
        cookie_name = cookie_name,
        remember_cookie_name = remember_cookie_name
      }
    end)

    it("with default values", function()
      session.init(configuration)

      local s = session.new()
      assert.is_not_nil(s)
      test_session(s)
    end)

    it("with custom secret", function()
      configuration.secret = "t"
      session.init(configuration)

      local s = session.new()
      assert.is_not_nil(s)
      test_session(s)
    end)

    it("custom ikm takes precedence on secret", function()
      configuration.secret = "t"
      configuration.ikm = "00000000000000000000000000000000"
      session.init(configuration)

      local s = session.new()
      assert.is_not_nil(s)
      test_session(s)

      assert.equals(configuration.ikm, s.meta.ikm)
    end)

    it("logout individual audience and subject", function()
      local cookies = {}
      session.__set_ngx_header(cookies)
      session.init(configuration)

      configuration.audience = test_audience
      configuration.subject  = test_subject
      local s1 = session.new(configuration)
      assert.is_not_nil(s1)
      test_session_save(s1, cookies)
      local session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie
      })
      assert.is_not_nil(session_cookie)
      assert.is_not_equal("", session_cookie)
      assert.match(s1:get_audience(), configuration.audience)

      configuration.audience = lout_audience
      configuration.subject  = lout_subject
      local s2 = session.open(configuration)
      assert.is_not_nil(s2)
      test_session_save(s2, cookies)
      session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie
      })
      assert.is_not_nil(session_cookie)
      assert.is_not_equal("", session_cookie)
      assert.equals(configuration.audience, s2:get_audience())

      s2:logout()
      assert.equals(s1.state, "open")
      assert.equals(s2.state, "closed")
      session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie
      })
      assert.is_not_nil(session_cookie)
      assert.is_not_equal("", session_cookie)

      s1:logout()
      assert.equals(s1.state, "closed")
      session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      assert.is_not_nil(session_cookie)
      assert.equals("", session_cookie)
    end)

    it("set_remember=true produces remember cookie, get_remember returns expected values", function()
      local cookies = {}
      session.__set_ngx_header(cookies)
      session.init(configuration)

      local s = session.new()
      assert.is_not_nil(s)
      assert.is_false(s:get_remember())
      s:save()
      assert.equals(s.state, "open")
      local session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
      local remember_cookie = extract_cookie(remember_cookie_name, cookies["Set-Cookie"])
      assert.is_not_nil(remember_cookie)
      assert.equals("", remember_cookie)

      session.__set_ngx_var({
        ["cookie_" .. cookie_name] = session_cookie,
        ["cookie_" .. remember_cookie_name] = remember_cookie,
      })
      s:set_remember(true)
      assert.is_true(s:get_remember())
      s:save()
      assert.equals(s.state, "open")
      remember_cookie = extract_cookie(remember_cookie_name, cookies["Set-Cookie"])
      assert.is_not_nil(remember_cookie)
      assert.is_not_equal(remember_cookie, "")
    end)

    describe("with custom cookie attribute", function()
      it("Domain", function()
        configuration.cookie_domain = "example.org"
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("Domain=example.org", s.cookie_flags)
      end)

      it("Path", function()
        configuration.cookie_path = "/test"
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("Path=/test", s.cookie_flags)
      end)

      it("SameSite", function()
        configuration.cookie_same_site = "Default"
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("SameSite=Default", s.cookie_flags)
      end)

      it("HttpOnly", function()
        configuration.cookie_http_only = false
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.does_not.match("HttpOnly", s.cookie_flags)
      end)

      it("Secure", function()
        configuration.cookie_secure = true
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("Secure", s.cookie_flags)
      end)

      it("Priority", function()
        configuration.cookie_priority = "High"
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("Priority=High", s.cookie_flags)
      end)

      it("Partitioned", function()
        configuration.cookie_partitioned = true
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("Partitioned", s.cookie_flags)
      end)

      it("SameParty", function()
        configuration.cookie_same_party = true
        session.init(configuration)

        local s = session.new()
        assert.is_not_nil(s)
        test_session(s)
        assert.matches("SameParty", s.cookie_flags)
      end)
    end)
  end)

  describe("Fields validation", function()
    describe("init validates fields", function()
      before_each(function()
        configuration = {}
      end)

      it("custom ikm must be 32 bytes", function()
        configuration.ikm = "12345"

        local ok, err = pcall(session.init,configuration)
        assert.is_false(ok)
        assert.matches("invalid ikm size", err)
      end)

      it("custom ikm_fallbacks must be 32 bytes", function()
        configuration.ikm_fallbacks = {
          "00000000000000000000000000000000",
          "123456",
        }

        local ok, err = pcall(session.init,configuration)
        assert.is_false(ok)
        assert.matches("invalid ikm size in ikm_fallbacks", err)
      end)
    end)

    describe("new validates fields", function()
      before_each(function()
        configuration = {}
      end)

      it("custom ikm must be 32 bytes", function()
        configuration.ikm = "12345"
        local ok, err = pcall(session.new, configuration)
        assert.is_false(ok)
        assert.matches("invalid ikm size", err)
      end)

      it("custom ikm_fallbacks must be 32 bytes", function()
        configuration.ikm_fallbacks = {
          "00000000000000000000000000000000",
          "123456",
        }
        local ok, err = pcall(session.new, configuration)
        assert.is_false(ok)
        assert.matches("invalid ikm size", err)
      end)

      it("SameParty and SameSite=strict fails to instantiate session", function()
        configuration.cookie_same_party = true
        configuration.cookie_same_site = "Strict"

        local ok, err = pcall(session.new, configuration)
        assert.is_false(ok)
        assert.matches("SameParty session cookies cannot use SameSite=Strict", err)
      end)
    end)
  end)
end)
