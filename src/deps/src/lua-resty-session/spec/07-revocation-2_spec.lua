---
-- For now these tests don't run on CI.
-- Ensure to keep the tests consistent with those in 06-revocation-1_spec.lua


local session = require "resty.session"
local utils = require "resty.session.utils"


local before_each = before_each
local after_each = after_each
local lazy_setup = lazy_setup
local describe = describe
local ipairs = ipairs
local assert = assert
local pcall = pcall
local sleep = ngx.sleep
local time = ngx.time
local it = it


local storage_configs = {
  mysql = {
    username = "root",
    password = "password",
    database = "test",
  },
  postgres = {
    username = "postgres",
    password = "password",
    database = "test",
  },
  redis_sentinel = {
    prefix = "revocations",
    password = "password",
    sentinels = {
      { host = "127.0.0.1", port = "26379" }
    },
  },
  redis_cluster = {
    prefix = "revocations",
    password = "password",
    nodes = {
      { ip = "127.0.0.1", port = "6380" }
    },
    name = "somecluster",
    lock_zone = "sessions",
  },
  dshm = {
    prefix = "revocations",
  },
}


local function storage_type(ty)
  if ty == "redis_cluster" or ty == "redis_sentinel" then
    return "redis"
  end
  return ty
end


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
  "mysql",
  "postgres",
  "redis_cluster",
  "redis_sentinel",
  "dshm",
}) do
  describe("Revocation tests 2 #noci", function()
    local current_time
    local store
    local long_ttl  = 60
    local short_ttl = 2
    local key       = "test_key_1iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key1      = "test_key_2iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key2      = "test_key_3iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local name      = "session_cookie"
    local mark      = "1"
    local ty        = storage_type(st)

    lazy_setup(function()
      local conf = {
        storage = "cookie",
        revocation = ty,
      }
      conf[ty] = storage_configs[st]
      store = utils.load_storage(ty, conf)
      assert.is_not_nil(store)
    end)

    before_each(function()
      current_time = time()
    end)

    describe("[#" .. st .. "] revocation storage: SET + GET", function()
      after_each(function()
        current_time = time()
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
          revocation = ty,
        }
        conf[ty] = storage_configs[st]
        session.init(conf)
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
    end)
  end)
end


describe("Revocation tests 2 session: revocation_fail_mode", function()
  local cookie_name = "session_cookie"
  local test_key    = "test_key"
  local value       = "test_data"
  local session_cookie
  local cookies

  local function save_session(s, header_cookies)
    session.__set_ngx_header(header_cookies)
    s:set(test_key, value)
    local ok, err = s:save()
    assert.is_true(ok)
    assert.is_nil(err)
    return extract_cookie(cookie_name, header_cookies["Set-Cookie"])
  end

  local function open_session(cookie_value)
    local s = session.new()
    session.__set_ngx_var({
      ["cookie_" .. cookie_name] = cookie_value,
    })

    local ok, err = s:open()
    if not ok then
      return nil, err
    end

    return s
  end

  before_each(function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
    })

    cookies = {}
    local s = session.new()
    session_cookie = save_session(s, cookies)
    s:close()
  end)

  it("open: default fail mode allows open when store is unreachable", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
      revocation = {
        set = function()
          return nil, "connection refused"
        end,
        get = function()
          return nil, "connection refused"
        end,
      },
    })

    local opened, err = open_session(session_cookie)
    assert.is_not_nil(opened)
    assert.is_nil(err)
    assert.equals("open", opened.revocation_fail_mode)
    assert.equals(value, opened:get(test_key))
  end)

  it("destroy: open fail mode succeeds when marking revoked fails", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
      revocation = {
        set = function()
          return nil, "connection refused"
        end,
        get = function()
          return nil
        end,
      },
      revocation_fail_mode = "open",
    })

    local s = session.new()
    session.__set_ngx_var({
      ["cookie_" .. cookie_name] = session_cookie,
    })

    local ok, err = s:open()
    assert.is_true(ok)
    assert.is_nil(err)

    session.__set_ngx_header(cookies)
    ok, err = s:destroy()
    assert.is_true(ok)
    assert.is_nil(err)
    assert.equals("closed", s.state)
  end)

  it("open: closed fail mode rejects when store is unreachable", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
      revocation = {
        set = function()
          return nil, "connection refused"
        end,
        get = function()
          return nil, "connection refused"
        end,
      },
      revocation_fail_mode = "closed",
    })

    local opened, err = open_session(session_cookie)
    assert.is_nil(opened)
    assert.matches("unable to check session revocation", err)
  end)

  it("destroy: closed fail mode fails when marking revoked fails", function()
    local s = session.new({
      revocation = {
        set = function()
          return nil, "connection refused"
        end,
        get = function()
          return nil
        end,
      },
      revocation_fail_mode = "closed",
    })
    session.__set_ngx_var({
      ["cookie_" .. cookie_name] = session_cookie,
    })

    local ok, err = s:open()
    assert.is_true(ok)
    assert.is_nil(err)

    session.__set_ngx_header(cookies)
    ok, err = s:destroy()
    assert.is_nil(ok)
    assert.matches("unable to mark session revoked", err)
    assert.equals("open", s.state)
  end)
end)


describe("Revocation tests 2 session: Fields validation", function()
  local cookie_name = "session_cookie"

  it("new defaults revocation_fail_mode to open", function()
    session.init({
      cookie_name = cookie_name,
      storage = "cookie",
    })

    local s = session.new()
    assert.equals("open", s.revocation_fail_mode)
  end)

  it("new requires an explicit revocation storage name", function()
    local ok, err = pcall(session.new, {
      revocation = true,
    })
    assert.is_false(ok)
    assert.matches("invalid session revocation", err)
  end)

  it("new validates revocation configuration", function()
    local ok, err = pcall(session.new, {
      revocation = 123,
    })
    assert.is_false(ok)
    assert.matches("invalid session revocation", err)
  end)

  it("new rejects a store table without set and get", function()
    local ok, err = pcall(session.new, {
      revocation = {
        set = function() end,
      },
    })
    assert.is_false(ok)
    assert.matches("invalid session revocation", err)
  end)

  it("new rejects an invalid fail mode", function()
    local ok, err = pcall(session.new, {
      revocation_fail_mode = "deny",
    })
    assert.is_false(ok)
    assert.matches("invalid revocation fail mode", err)
  end)
end)
