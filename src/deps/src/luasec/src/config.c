/*--------------------------------------------------------------------------
 * LuaSec 1.3.1
 *
 * Copyright (C) 2006-2023 Bruno Silvestre
 *
 *--------------------------------------------------------------------------*/

#include "compat.h"
#include "options.h"
#include "ec.h"

/**
 * Registre the module.
 */
LSEC_API int luaopen_ssl_config(lua_State *L)
{
  lsec_ssl_option_t *opt;

  lua_newtable(L);

  // Options
  lua_pushstring(L, "options");
  lua_newtable(L);
  for (opt = lsec_get_ssl_options(); opt->name; opt++) {
    lua_pushstring(L, opt->name);
    lua_pushboolean(L, 1);
    lua_rawset(L, -3);
  }
  lua_rawset(L, -3);

  // Protocols
  lua_pushstring(L, "protocols");
  lua_newtable(L);

  lua_pushstring(L, "tlsv1");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
  lua_pushstring(L, "tlsv1_1");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
  lua_pushstring(L, "tlsv1_2");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#ifdef TLS1_3_VERSION
  lua_pushstring(L, "tlsv1_3");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#endif

  lua_rawset(L, -3);

  // Algorithms
  lua_pushstring(L, "algorithms");
  lua_newtable(L);

#ifndef OPENSSL_NO_EC
  lua_pushstring(L, "ec");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#endif
  lua_rawset(L, -3);
 
  // Curves
  lua_pushstring(L, "curves");
  lsec_get_curves(L);
  lua_rawset(L, -3);

  // Capabilities
  lua_pushstring(L, "capabilities");
  lua_newtable(L);

  // ALPN
  lua_pushstring(L, "alpn");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);

#ifdef LSEC_ENABLE_PSK
  lua_pushstring(L, "psk");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#endif

#ifdef LSEC_ENABLE_DANE
  // DANE
  lua_pushstring(L, "dane");
#ifdef DANE_FLAG_NO_DANE_EE_NAMECHECKS
  lua_createtable(L, 0, 1);
  lua_pushstring(L, "no_ee_namechecks");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#else
  lua_pushboolean(L, 1);
#endif
  lua_rawset(L, -3);
#endif

#ifndef OPENSSL_NO_EC
  lua_pushstring(L, "curves_list");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
  lua_pushstring(L, "ecdh_auto");
  lua_pushboolean(L, 1);
  lua_rawset(L, -3);
#endif
  lua_rawset(L, -3);

  return 1;
}
