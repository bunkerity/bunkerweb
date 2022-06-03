/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifdef WITH_LUA
#include <lua.hpp>
#endif

#include <iostream>
#include <cstdint>
#include <cstring>
#include <string>

#ifndef SRC_ENGINE_LUA_H_
#define SRC_ENGINE_LUA_H_

namespace modsecurity {
class Transaction;
namespace engine {

#ifdef WITH_LUA
class LuaScriptBlob {
 public:
    LuaScriptBlob() :
        m_data(NULL),
        m_len(0) { }

    ~LuaScriptBlob() {
        if (m_data) {
            free(m_data);
            m_data = NULL;
        }
    }


    void write(const void *data, size_t len) {
        unsigned char *d = NULL;
        d = (unsigned char *)realloc((unsigned char *)m_data, len + m_len);
        std::memcpy(d + m_len, data, len);
        m_len = m_len + len;
        m_data = d;
    }


    const char *read(size_t *len) {
        *len = m_len;
        return (const char *)m_data;
    }


    unsigned char *m_data;
    size_t m_len;
};
#endif

class Lua {
 public:
    Lua() { }

    bool load(std::string script, std::string *err);
    int run(Transaction *t, const std::string &str="");
    static bool isCompatible(std::string script, Lua *l, std::string *error);

#ifdef WITH_LUA
    static int blob_keeper(lua_State *L, const void *p, size_t sz, void *ud);
    static const char *blob_reader(lua_State *L, void *us, size_t *size);

    static int log(lua_State *L);
    static int getvar(lua_State *L);
    static int getvars(lua_State *L);
    static int setvar(lua_State *L);
    static std::string applyTransformations(lua_State *L, Transaction *t,
        int idx, std::string var);

    LuaScriptBlob m_blob;
#endif
    std::string m_scriptName;
};

#ifdef WITH_LUA
static const struct luaL_Reg mscLuaLib[] = {
    { "log", Lua::log },
    { "getvar", Lua::getvar },
    { "getvars", Lua::getvars },
    { "setvar", Lua::setvar },
    { NULL, NULL }
};
#endif

}  // namespace engine
}  // namespace modsecurity

#ifdef WITH_LUA
#if defined LUA_VERSION_NUM && LUA_VERSION_NUM < 502 && !defined WITH_LUA_JIT_2_1
/*
** Adapted from Lua 5.2.0
*/
#define LUA_OK 0

static void luaL_setfuncs(lua_State *L, const luaL_Reg *l, int nup) {
    luaL_checkstack(L, nup + 1, "too many upvalues");

    for (; l->name != NULL; l++) {  /* fill the table with given functions */
        int i;
        lua_pushstring(L, l->name);
        for (i = 0; i < nup; i++)  /* copy upvalues to the top */
          lua_pushvalue(L, -(nup + 1));
        lua_pushcclosure(L, l->func, nup);  /* closure with those upvalues */
        lua_settable(L, -(nup + 3));
    }

    lua_pop(L, nup);  /* remove upvalues */
}
#endif
#endif


#endif  // SRC_ENGINE_LUA_H_
