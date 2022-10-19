#include <openssl/objects.h>

#include "ec.h"

#ifndef OPENSSL_NO_EC

EC_KEY *lsec_find_ec_key(lua_State *L, const char *str)
{
  int nid;
  lua_pushstring(L, "SSL:EC:CURVES");
  lua_rawget(L, LUA_REGISTRYINDEX);
  lua_pushstring(L, str);
  lua_rawget(L, -2);

  if (!lua_isnumber(L, -1))
    return NULL;

  nid = (int)lua_tonumber(L, -1);
  return EC_KEY_new_by_curve_name(nid);
}

void lsec_load_curves(lua_State *L)
{
  size_t i;
  size_t size;
  const char *name;
  EC_builtin_curve *curves = NULL;

  lua_pushstring(L, "SSL:EC:CURVES");
  lua_newtable(L);

  size = EC_get_builtin_curves(NULL, 0);
  if (size > 0) {
    curves = (EC_builtin_curve*)malloc(sizeof(EC_builtin_curve) * size);
    EC_get_builtin_curves(curves, size);
    for (i = 0; i < size; i++) {
      name = OBJ_nid2sn(curves[i].nid);
      if (name != NULL) {
        lua_pushstring(L, name);
        lua_pushnumber(L, curves[i].nid);
        lua_rawset(L, -3);
      }
      switch (curves[i].nid) {
      case NID_X9_62_prime256v1:
        lua_pushstring(L, "P-256");
        lua_pushnumber(L, curves[i].nid);
        lua_rawset(L, -3);
        break;
      case NID_secp384r1:
        lua_pushstring(L, "P-384");
        lua_pushnumber(L, curves[i].nid);
        lua_rawset(L, -3);
        break;
      case NID_secp521r1:
        lua_pushstring(L, "P-521");
        lua_pushnumber(L, curves[i].nid);
        lua_rawset(L, -3);
        break;
      }
    }
    free(curves);
  }

  /* These are special so are manually added here */
#ifdef NID_X25519
  lua_pushstring(L, "X25519");
  lua_pushnumber(L, NID_X25519);
  lua_rawset(L, -3);
#endif

#ifdef NID_X448
  lua_pushstring(L, "X448");
  lua_pushnumber(L, NID_X448);
  lua_rawset(L, -3);
#endif

  lua_rawset(L,  LUA_REGISTRYINDEX);
}

void lsec_get_curves(lua_State *L)
{
  lua_newtable(L);

  lua_pushstring(L, "SSL:EC:CURVES");
  lua_rawget(L, LUA_REGISTRYINDEX);

  lua_pushnil(L);
  while (lua_next(L, -2) != 0) {
    lua_pop(L, 1);
    lua_pushvalue(L, -1);
    lua_pushboolean(L, 1);
    lua_rawset(L, -5);
  }
  lua_pop(L, 1);
}

#else

void lsec_load_curves(lua_State *L)
{
  // do nothing
}

void lsec_get_curves(lua_State *L)
{
  lua_newtable(L);
}

#endif
