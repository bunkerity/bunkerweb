#ifndef LSEC_CONTEXT_H
#define LSEC_CONTEXT_H

/*--------------------------------------------------------------------------
 * LuaSec 1.3.1
 *
 * Copyright (C) 2006-2023 Bruno Silvestre
 *
 *--------------------------------------------------------------------------*/

#include <lua.h>
#include <openssl/ssl.h>

#include "compat.h"

#define LSEC_MODE_INVALID 0
#define LSEC_MODE_SERVER  1
#define LSEC_MODE_CLIENT  2

#define LSEC_VERIFY_CONTINUE        1
#define LSEC_VERIFY_IGNORE_PURPOSE  2

typedef struct t_context_ {
  SSL_CTX *context;
  lua_State *L;
  DH *dh_param;
  void *alpn;
  int mode;
} t_context;
typedef t_context* p_context;

/* Retrieve the SSL context from the Lua stack */
SSL_CTX *lsec_checkcontext(lua_State *L, int idx);
SSL_CTX *lsec_testcontext(lua_State *L, int idx);

/* Retrieve the mode from the context in the Lua stack */
int lsec_getmode(lua_State *L, int idx);

/* Registre the module. */
LSEC_API int luaopen_ssl_context(lua_State *L);

/* Compat - Lua 5.1 */
#if (LUA_VERSION_NUM == 501)
void *lsec_testudata (lua_State *L, int ud, const char *tname);
#endif

#endif
