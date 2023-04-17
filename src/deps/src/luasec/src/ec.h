/*--------------------------------------------------------------------------
 * LuaSec 1.3.1
 *
 * Copyright (C) 2006-2023 Bruno Silvestre
 *
 *--------------------------------------------------------------------------*/

#ifndef LSEC_EC_H
#define LSEC_EC_H

#include <lua.h>

#ifndef OPENSSL_NO_EC
#include <openssl/ec.h>

EC_KEY *lsec_find_ec_key(lua_State *L, const char *str);
#endif

void lsec_get_curves(lua_State *L);
void lsec_load_curves(lua_State *L);

#endif
