#ifndef COMPAT_H
#define COMPAT_H

#if LUA_VERSION_NUM==501

#ifndef _WIN32
#pragma GCC visibility push(hidden)
#endif

void luasocket_setfuncs (lua_State *L, const luaL_Reg *l, int nup);
void *luasocket_testudata ( lua_State *L, int arg, const char *tname);

#ifndef _WIN32
#pragma GCC visibility pop
#endif

#define luaL_setfuncs luasocket_setfuncs
#define luaL_testudata luasocket_testudata

#endif

#endif
