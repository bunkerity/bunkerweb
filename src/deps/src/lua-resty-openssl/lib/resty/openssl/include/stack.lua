--[[
  The OpenSSL stack library. Note `safestack` is not usable here in ffi because
  those symbols are eaten after preprocessing.
  Instead, we should do a Lua land type checking by having a nested field indicating
  which type of cdata its ctx holds.
]]

local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  typedef char *OPENSSL_STRING;
  typedef struct stack_st OPENSSL_STACK;

  OPENSSL_STACK *OPENSSL_sk_new_null(void);
  int OPENSSL_sk_push(OPENSSL_STACK *st, const void *data);
  void OPENSSL_sk_pop_free(OPENSSL_STACK *st, void (*func) (void *));
  int OPENSSL_sk_num(const OPENSSL_STACK *);
  void *OPENSSL_sk_value(const OPENSSL_STACK *, int);
  OPENSSL_STACK *OPENSSL_sk_dup(const OPENSSL_STACK *st);
  void OPENSSL_sk_free(OPENSSL_STACK *);
  // void *OPENSSL_sk_delete(OPENSSL_STACK *st, int loc);

  typedef void (*OPENSSL_sk_freefunc)(void *);
  typedef void *(*OPENSSL_sk_copyfunc)(const void *);
  OPENSSL_STACK *OPENSSL_sk_deep_copy(const OPENSSL_STACK *,
                                  OPENSSL_sk_copyfunc c,
                                  OPENSSL_sk_freefunc f);
]]
