/*=========================================================================*\
* Simple exception support
* LuaSocket toolkit
\*=========================================================================*/
#include "luasocket.h"
#include "except.h"
#include <stdio.h>

#if LUA_VERSION_NUM < 502
#define lua_pcallk(L, na, nr, err, ctx, cont) \
    (((void)ctx),((void)cont),lua_pcall(L, na, nr, err))
#endif

#if LUA_VERSION_NUM < 503
typedef int lua_KContext;
#endif

/*=========================================================================*\
* Internal function prototypes.
\*=========================================================================*/
static int global_protect(lua_State *L);
static int global_newtry(lua_State *L);
static int protected_(lua_State *L);
static int finalize(lua_State *L);
static int do_nothing(lua_State *L);

/* except functions */
static luaL_Reg func[] = {
    {"newtry",    global_newtry},
    {"protect",   global_protect},
    {NULL,        NULL}
};

/*-------------------------------------------------------------------------*\
* Try factory
\*-------------------------------------------------------------------------*/
static void wrap(lua_State *L) {
    lua_createtable(L, 1, 0);
    lua_pushvalue(L, -2);
    lua_rawseti(L, -2, 1);
    lua_pushvalue(L, lua_upvalueindex(1));
    lua_setmetatable(L, -2);
}

static int finalize(lua_State *L) {
    if (!lua_toboolean(L, 1)) {
        lua_pushvalue(L, lua_upvalueindex(2));
        lua_call(L, 0, 0);
        lua_settop(L, 2);
        wrap(L);
        lua_error(L);
        return 0;
    } else return lua_gettop(L);
}

static int do_nothing(lua_State *L) {
    (void) L;
    return 0;
}

static int global_newtry(lua_State *L) {
    lua_settop(L, 1);
    if (lua_isnil(L, 1)) lua_pushcfunction(L, do_nothing);
    lua_pushvalue(L, lua_upvalueindex(1));
    lua_insert(L, -2);
    lua_pushcclosure(L, finalize, 2);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Protect factory
\*-------------------------------------------------------------------------*/
static int unwrap(lua_State *L) {
    if (lua_istable(L, -1) && lua_getmetatable(L, -1)) {
        int r = lua_rawequal(L, -1, lua_upvalueindex(1));
        lua_pop(L, 1);
        if (r) {
            lua_pushnil(L);
            lua_rawgeti(L, -2, 1);
            return 1;
        }
    }
    return 0;
}

static int protected_finish(lua_State *L, int status, lua_KContext ctx) {
    (void)ctx;
    if (status != 0 && status != LUA_YIELD) {
        if (unwrap(L)) return 2;
        else return lua_error(L);
    } else return lua_gettop(L);
}

#if LUA_VERSION_NUM == 502
static int protected_cont(lua_State *L) {
    int ctx = 0;
    int status = lua_getctx(L, &ctx);
    return protected_finish(L, status, ctx);
}
#else
#define protected_cont protected_finish
#endif

static int protected_(lua_State *L) {
    int status;
    lua_pushvalue(L, lua_upvalueindex(2));
    lua_insert(L, 1);
    status = lua_pcallk(L, lua_gettop(L) - 1, LUA_MULTRET, 0, 0, protected_cont);
    return protected_finish(L, status, 0);
}

static int global_protect(lua_State *L) {
    lua_settop(L, 1);
    lua_pushvalue(L, lua_upvalueindex(1));
    lua_insert(L, 1);
    lua_pushcclosure(L, protected_, 2);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Init module
\*-------------------------------------------------------------------------*/
int except_open(lua_State *L) {
    lua_newtable(L); /* metatable for wrapped exceptions */
    lua_pushboolean(L, 0);
    lua_setfield(L, -2, "__metatable");
    luaL_setfuncs(L, func, 1);
    return 0;
}
