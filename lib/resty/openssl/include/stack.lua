--[[
  The OpenSSL stack library. Note `safestack` is not usable here in ffi because
  those symbols are eaten after preprocessing.
  Instead, we should do a Lua land type checking by having a nested field indicating
  which type of cdata its ctx holds.
]]

local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.ossl_typ"
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local _M = {}

ffi.cdef [[
  typedef char *OPENSSL_STRING;
]]

if OPENSSL_11_OR_LATER and not BORINGSSL then
  ffi.cdef [[
    typedef struct stack_st OPENSSL_STACK;

    OPENSSL_STACK *OPENSSL_sk_new_null(void);
    int OPENSSL_sk_push(OPENSSL_STACK *st, const void *data);
    void OPENSSL_sk_pop_free(OPENSSL_STACK *st, void (*func) (void *));
    int OPENSSL_sk_num(const OPENSSL_STACK *);
    void *OPENSSL_sk_value(const OPENSSL_STACK *, int);
    OPENSSL_STACK *OPENSSL_sk_dup(const OPENSSL_STACK *st);
    void OPENSSL_sk_free(OPENSSL_STACK *);
    void *OPENSSL_sk_delete(OPENSSL_STACK *st, int loc);

    typedef void (*OPENSSL_sk_freefunc)(void *);
    typedef void *(*OPENSSL_sk_copyfunc)(const void *);
    OPENSSL_STACK *OPENSSL_sk_deep_copy(const OPENSSL_STACK *,
                                    OPENSSL_sk_copyfunc c,
                                    OPENSSL_sk_freefunc f);
  ]]
  _M.OPENSSL_sk_pop_free = C.OPENSSL_sk_pop_free

  _M.OPENSSL_sk_new_null = C.OPENSSL_sk_new_null
  _M.OPENSSL_sk_push = C.OPENSSL_sk_push
  _M.OPENSSL_sk_pop_free = C.OPENSSL_sk_pop_free
  _M.OPENSSL_sk_num = C.OPENSSL_sk_num
  _M.OPENSSL_sk_value = C.OPENSSL_sk_value
  _M.OPENSSL_sk_dup = C.OPENSSL_sk_dup
  _M.OPENSSL_sk_delete = C.OPENSSL_sk_delete
  _M.OPENSSL_sk_free = C.OPENSSL_sk_free
  _M.OPENSSL_sk_deep_copy = C.OPENSSL_sk_deep_copy
elseif OPENSSL_10 or BORINGSSL then
  ffi.cdef [[
    typedef struct stack_st _STACK;
    // i made this up
    typedef struct stack_st OPENSSL_STACK;

    _STACK *sk_new_null(void);
    void sk_pop_free(_STACK *st, void (*func) (void *));
    _STACK *sk_dup(_STACK *st);
    void sk_free(_STACK *st);

    _STACK *sk_deep_copy(_STACK *, void *(*)(void *), void (*)(void *));
  ]]

  if BORINGSSL then -- indices are using size_t instead of int
    ffi.cdef [[
      size_t sk_push(_STACK *st, void *data);
      size_t sk_num(const _STACK *);
      void *sk_value(const _STACK *, size_t);
      void *sk_delete(_STACK *st, size_t loc);
    ]]
  else -- normal OpenSSL 1.0
    ffi.cdef [[
      int sk_push(_STACK *st, void *data);
      int sk_num(const _STACK *);
      void *sk_value(const _STACK *, int);
      void *sk_delete(_STACK *st, int loc);
    ]]
  end

  _M.OPENSSL_sk_pop_free = C.sk_pop_free

  _M.OPENSSL_sk_new_null = C.sk_new_null
  _M.OPENSSL_sk_push = function(...) return tonumber(C.sk_push(...)) end
  _M.OPENSSL_sk_pop_free = C.sk_pop_free
  _M.OPENSSL_sk_num = function(...) return tonumber(C.sk_num(...)) end
  _M.OPENSSL_sk_value = C.sk_value
  _M.OPENSSL_sk_delete = C.sk_delete
  _M.OPENSSL_sk_dup = C.sk_dup
  _M.OPENSSL_sk_free = C.sk_free
  _M.OPENSSL_sk_deep_copy = C.sk_deep_copy
end

return _M
