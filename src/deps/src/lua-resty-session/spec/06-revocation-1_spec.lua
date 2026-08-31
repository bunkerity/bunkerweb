---
-- Ensure to keep the tests consistent with those in 07-revocation-2_spec.lua


local session = require "resty.session"
local utils = require "resty.session.utils"


local before_each = before_each
local after_each = after_each
local lazy_setup = lazy_setup
local describe = describe
local ipairs = ipairs
local assert = assert
local sleep = ngx.sleep
local time = ngx.time
local it = it


local storage_configs = {
  file = {
    suffix = "revocation",
  },
  shm = {
    prefix = "revocations",
  },
  redis = {
    prefix = "revocations",
    password = "password",
  },
  memcached = {
    prefix = "revocations",
  },
}


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


for _, st in ipairs({
  "file",
  "shm",
  "redis",
  "memcached",
}) do
  describe("Revocation tests 1", function()
    local current_time
    local store
    local long_ttl  = 60
    local short_ttl = 2
    local key       = "test_key_1iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key1      = "test_key_2iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key2      = "test_key_3iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local name      = "session_cookie"
    local mark      = "1"

    lazy_setup(function()
      local conf = {
        storage = "cookie",
        revocation = st,
      }
      conf[st] = storage_configs[st]
      store = utils.load_storage(st, conf)
      assert.is_not_nil(store)
    end)

    before_each(function()
      current_time = time()
    end)

    describe("[#" .. st .. "] revocation storage: SET + GET", function()
      after_each(function()
        store:delete(name, key, current_time)
        store:delete(name, key1, current_time)
        store:delete(name, key2, current_time)
      end)

      it("SET: stores revocation mark and GET observes it", function()
        local ok = store:set(name, key, mark, long_ttl, current_time)
        assert.is_not_nil(ok)

        local data, err = store:get(name, key, current_time)
        assert.is_nil(err)
        assert.equals(mark, data)
      end)

      it("GET: missing revocation key returns not revoked", function()
        local data, err = store:get(name, key1, current_time)
        assert.is_nil(data)
        assert.is_nil(err)
      end)

      it("SET: ttl expires revocation entry", function()
        local ok = store:set(name, key2, mark, short_ttl, current_time)
        assert.is_not_nil(ok)

        local data, err = store:get(name, key2, current_time)
        assert.is_nil(err)
        assert.equals(mark, data)

        sleep(short_ttl + 1)

        data, err = store:get(name, key2, time())
        assert.is_nil(data)
        assert.is_nil(err)
      end)

      it("SET: re-mark refreshes ttl", function()
        local ok = store:set(name, key, mark, short_ttl, current_time)
        assert.is_not_nil(ok)

        sleep(1)

        ok = store:set(name, key, mark, long_ttl, time())
        assert.is_not_nil(ok)

        sleep(short_ttl + 1)

        local data, err = store:get(name, key, time())
        assert.is_nil(err)
        assert.equals(mark, data)
      end)
    end)

    describe("[#" .. st .. "] session: revocation lifecycle", function()
      local cookie_name = "session_cookie"
      local test_key    = "test_key"
      local value       = "test_data"

      local function save_session(s, cookies)
        session.__set_ngx_header(cookies)
        s:set(test_key, value)
        local ok, err = s:save()
        assert.is_true(ok)
        assert.is_nil(err)
        return extract_cookie(cookie_name, cookies["Set-Cookie"])
      end

      local function open_session(session_cookie)
        local s = session.new()
        session.__set_ngx_var({
          ["cookie_" .. cookie_name] = session_cookie,
        })

        local ok, err = s:open()
        if not ok then
          return nil, err
        end

        return s
      end

      before_each(function()
        local conf = {
          cookie_name = cookie_name,
          storage = "cookie",
          revocation = st,
        }
        conf[st] = storage_configs[st]
        session.init(conf)
      end)

      it("open succeeds for a valid session with revocation enabled", function()
        local cookies = {}
        local s = session.new()
        local session_cookie = save_session(s, cookies)
        s:close()

        local s2, err = open_session(session_cookie)
        assert.is_not_nil(s2)
        assert.is_nil(err)
        assert.equals(value, s2:get(test_key))
        s2:close()
      end)

      it("destroy: rejected cookie cannot be reopened", function()
        local cookies = {}
        local s = session.new()
        local session_cookie = save_session(s, cookies)
        assert.is_not_equal("", session_cookie)
        s:close()

        local s2, err = open_session(session_cookie)
        assert.is_not_nil(s2)
        assert.is_nil(err)
        assert.equals(value, s2:get(test_key))

        session.__set_ngx_header(cookies)
        local ok
        ok, err = s2:destroy()
        assert.is_true(ok)
        assert.is_nil(err)

        local s3
        s3, err = open_session(session_cookie)
        assert.is_nil(s3)
        assert.equals("session revoked", err)
      end)

      it("save rotation does not revoke the previous cookie", function()
        local cookies = {}
        local s = session.new()
        local session_cookie = save_session(s, cookies)
        s:close()

        local s2, err = open_session(session_cookie)
        assert.is_not_nil(s2)
        assert.is_nil(err)

        s2:set(test_key, "rotated")
        session.__set_ngx_header(cookies)
        local ok
        ok, err = s2:save()
        assert.is_true(ok)
        assert.is_nil(err)
        s2:close()

        local s3
        s3, err = open_session(session_cookie)
        assert.is_not_nil(s3)
        assert.is_nil(err)
        assert.equals(value, s3:get(test_key))
        s3:close()
      end)
    end)
  end)
end


describe("Revocation tests 1 session: configuration", function()
  local cookie_name = "session_cookie"

  it("cookie session without revocation remains usable after destroy", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
    })

    local cookies = {}
    local s = session.new()
    session.__set_ngx_header(cookies)
    s:set("test_key", "test_data")
    local ok, err = s:save()
    assert.is_true(ok)
    assert.is_nil(err)
    local session_cookie = extract_cookie(cookie_name, cookies["Set-Cookie"])
    s:close()

    session.__set_ngx_var({
      ["cookie_" .. cookie_name] = session_cookie,
    })
    local s2 = session.new()
    ok, err = s2:open()
    assert.is_true(ok)
    assert.is_nil(err)

    session.__set_ngx_header(cookies)
    ok, err = s2:destroy()
    assert.is_true(ok)
    assert.is_nil(err)

    session.__set_ngx_var({
      ["cookie_" .. cookie_name] = session_cookie,
    })
    local s3 = session.new()
    ok, err = s3:open()
    assert.is_true(ok)
    assert.is_nil(err)
    assert.is_not_equal("session revoked", err)
  end)

  it("skips revocation when storage backend is configured", function()
    session.init({
      cookie_name = cookie_name,
      storage = "redis",
      revocation = "shm",
      redis = {
        prefix = "sessions",
        password = "password",
      },
      shm = {
        prefix = "revocations",
      },
    })

    local s = session.new()
    assert.is_nil(s.revocation)
  end)

  it("does not infer revocation storage from backend configuration", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
      redis = {
        host = "127.0.0.1",
        password = "password",
      },
    })

    local s = session.new()
    assert.is_nil(s.revocation)
  end)

  it("skips revocation when revocation is explicitly false", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
      redis = {
        host = "127.0.0.1",
        password = "password",
      },
      revocation = false,
    })

    local s = session.new()
    assert.is_nil(s.revocation)
  end)
end)
