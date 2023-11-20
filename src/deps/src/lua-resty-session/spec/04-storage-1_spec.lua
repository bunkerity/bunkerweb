---
-- Ensure to keep the tests consistent with those in 05-storage-1_spec.lua


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
    suffix = "session",
  },
  shm = {
    prefix = "sessions",
    connect_timeout = 10000,
    send_timeout = 10000,
    read_timeout = 10000,
  },
  redis = {
    prefix = "sessions",
    password = "password",
  },
  memcached = {
    prefix = "sessions",
    connect_timeout = 10000,
    send_timeout    = 10000,
    read_timeout    = 10000,
  },
}


for _, st in ipairs({
  "file",
  "shm",
  "redis",
  "memcached",
}) do
  describe("Storage tests 1", function()
    local current_time
    local storage
    local long_ttl  = 60
    local short_ttl = 2
    local key       = "test_key_1iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key1      = "test_key_2iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local key2      = "test_key_3iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local old_key   = "old_key_iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
    local name      = "test_name"
    local value     = "test_value"

    lazy_setup(function()
      local conf = {
        remember = true,
        store_metadata = true,
      }
      conf[st] = storage_configs[st]
      storage = utils.load_storage(st, conf)
      assert.is_not_nil(storage)
    end)

    before_each(function()
      current_time = time()
    end)

    describe("[#" .. st .. "] storage: SET + GET", function()
      local audiences = { "foo", "bar" }
      local subjects = { "john", "jane" }

      local metadata = {
        audiences = audiences,
        subjects = subjects,
      }

      after_each(function()
        storage:delete(name, key, current_time, metadata)
        storage:delete(name, key1, current_time, metadata)
        storage:delete(name, key2, current_time, metadata)
      end)

      it("SET: simple set does not return errors, GET fetches value correctly", function()
        local ok = storage:set(name, key, value, long_ttl, current_time)
        assert.is_not_nil(ok)

        local v, err = storage:get(name, key, current_time)
        assert.is_not_nil(v)
        assert.is_nil(err)
        assert.equals(v, value)
      end)

      it("SET: with metadata and remember works correctly", function()
        local ok = storage:set(name, key, value, long_ttl, current_time, nil, nil, metadata, true)
        assert.is_not_nil(ok)

        sleep(1)

        local v, err = storage:get(name, key, time())
        assert.is_not_nil(v)
        assert.is_nil(err)
        assert.equals(v, value)
      end)

      it("SET: with metadata (long ttl) correctly appends metadata to collection", function()
        local ok = storage:set(name, key, value, long_ttl, current_time, nil, nil, metadata, true)
        ok = ok and storage:set(name, key1, value, long_ttl, current_time, nil, nil, metadata, true)
        ok = ok and storage:set(name, key2, value, long_ttl, current_time, nil, nil, metadata, true)
        assert.is_not_nil(ok)

        sleep(1)

        for i = 1, #audiences do
          local meta_values = storage:read_metadata(name, audiences[i], subjects[i], time())
          assert.is_not_nil(meta_values)
          assert.truthy(meta_values[key ])
          assert.truthy(meta_values[key1])
          assert.truthy(meta_values[key2])
        end
      end)

      it("SET: with metadata (short ttl) correctly expires metadata", function()
        local ok = storage:set(name, key, value, short_ttl, current_time, nil, nil, metadata, true)

        sleep(short_ttl + 1)

        ok = ok and storage:set(name, key1, value, long_ttl, time(), nil, nil, metadata, true)
        assert.is_not_nil(ok)

        sleep(1)

        for i = 1, #audiences do
          local meta_values = storage:read_metadata(name, audiences[i], subjects[i], time())
          assert.falsy(meta_values[key])
          assert.truthy(meta_values[key1])
        end
      end)

      it("SET: with old_key correctly applies stale ttl on old key", function()
        local stale_ttl = 1

        local ok = storage:set(name, old_key, value, long_ttl, current_time)
        assert.is_not_nil(ok)

        ok = storage:set(name, key, value, long_ttl, current_time, old_key, stale_ttl, nil, false)
        assert.is_not_nil(ok)

        sleep(3)

        local v = storage:get(name, old_key, time())
        assert.is_nil(v)
      end)

      it("SET: remember deletes file in old_key", function()
        local stale_ttl = long_ttl

        local ok = storage:set(name, old_key, value, long_ttl, current_time)
        assert.is_not_nil(ok)

        ok = storage:set(name, key, value, long_ttl, current_time, old_key, stale_ttl, nil, true)
        assert.is_not_nil(ok)

        local v = storage:get(name, old_key, current_time)
        assert.is_nil(v)
      end)

      it("SET: ttl works as expected", function()
        local ok = storage:set(name, key, value, short_ttl, current_time)
        assert.is_not_nil(ok)

        sleep(3)

        local v = storage:get(name, key, time())
        assert.is_nil(v)
      end)
    end)

    describe("[#" .. st .. "] storage: DELETE", function()
      local audiences = { "foo" }
      local subjects = { "john" }

      local metadata = {
        audiences = audiences,
        subjects = subjects,
      }

      it("deleted file is really deleted", function()
        local ok = storage:set(name, key, value, short_ttl, current_time)
        assert.is_not_nil(ok)

        storage:delete(name, key, current_time, nil)

        local v = storage:get(name, key, current_time)
        assert.is_nil(v)
      end)

      it("with metadata correctly deletes metadata collection", function()
        local ok = storage:set(name, key1, value, long_ttl, current_time, nil, nil, metadata, true)
        assert.is_not_nil(ok)

        sleep(1)

        for i = 1, #audiences do
          local meta_values = storage:read_metadata(name, audiences[i], subjects[i], time())
          assert.truthy(meta_values[key1])
          ok = storage:delete(name, key1, time(), metadata)
          assert.is_not_nil(ok)

          sleep(2)

          meta_values = storage:read_metadata(name, audiences[i], subjects[i], time()) or {}
          assert.falsy(meta_values[key1])
        end
      end)
    end)
  end)
end
