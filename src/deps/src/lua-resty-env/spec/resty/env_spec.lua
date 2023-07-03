local _M = require 'resty.env'

describe('env', function()
  local env
  before_each(function() env = _M.env end)
  after_each(function() _M.env = env end)

  describe('.list', function()
    it('returns contents of the ENV variable', function()
      local list = _M.list()

      assert.truthy(list.PATH)
      assert.truthy(list.HOME)
      assert.truthy(list.PWD)
    end)
  end)

  describe('.get', function()

    local path = os.getenv("PATH")

    it('returns contents of the ENV variable', function()
      assert.equal(path, _M.get('PATH'))
    end)

    it('caches the result', function()
      _M.get('PATH')

      assert.equal(path, _M.env.PATH)
    end)

    it('reads from the cache first', function()
      _M.env = { ['SOME_MISSING_ENV_VAR'] = 'somevalue' }

      assert.equal('somevalue', _M.get("SOME_MISSING_ENV_VAR"))
    end)
  end)

  describe('.value', function()
    it('returns false instead of empty value', function()
      _M.set('KEY', '')
      assert.equal(false, _M.value('KEY'))
    end)

    it('returns the value if not emptu', function()
      _M.set('KEY', 'value')
      assert.equal('value', _M.value('KEY'))
    end)
  end)

  describe('.set', function()
    it('saves value to the cache', function()
      _M.set('SOME_MISSING_KEY', 'val')

      assert.equal('val', _M.env.SOME_MISSING_KEY)
    end)

    it('calls setenv', function()
      local key = 'SOME_UNUSED_KEY'
      assert.falsy(os.getenv(key))
      _M.set(key, 'value')
      assert.equal('value', os.getenv(key))
    end)

    it('converts the value to string', function()
      _M.set('NUMERIC_VALUE', 1234)

      assert.equal('1234', _M.env.NUMERIC_VALUE)
    end)

    it('works with nil', function()
      assert.truthy(_M.get('_'))

      _M.set('_', nil)

      assert.equal(nil, os.getenv('_'))
    end)
  end)

  describe('.reset', function()
    it('cleans the cache', function()
      _M.env.SOMETHING_EMPTY = 'foo'

      _M.reset()

      assert.same(nil, _M.env.SOMETHING_EMPTY)
    end)
  end)
end)
