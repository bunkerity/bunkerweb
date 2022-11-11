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


#include "src/engine/lua.h"

#include <stdio.h>
#include <string.h>

#include <vector>
#include <string>
#include <algorithm>
#include <sstream>
#include <iterator>
#include <iostream>

#include "modsecurity/variable_value.h"
#include "modsecurity/modsecurity.h"
#include "src/utils/string.h"
#include "modsecurity/transaction.h"
#include "src/variables/variable.h"
#include "src/variables/highest_severity.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace engine {


bool Lua::isCompatible(std::string script, Lua *l, std::string *error) {
#ifdef WITH_LUA
    std::string lua(".lua");
    std::string err;

    if (!(script.size() >= lua.size() &&
        script.compare(script.size() - lua.size(), lua.size(), lua) == 0)) {
        error->assign("Expecting a Lua script: " + script);
        return false;
    }

    if (l->load(script, &err) == false) {
        error->assign("Problems load script: " + err);
        return false;
    }

    return true;
#else
    error->assign("Lua support was not enabled.");
    return false;
#endif
}


bool Lua::load(std::string script, std::string *err) {
#ifdef WITH_LUA
    lua_State *L = NULL;
    L = luaL_newstate();
    luaL_openlibs(L);

    m_scriptName = script;
    if (luaL_loadfile(L, script.c_str())) {
        const char *luaerr = lua_tostring(L, -1);
        err->assign("Failed to compile script '" + script + "");
        if (luaerr) {
            err->append(": " + std::string(luaerr));
        }
        err->append(".");
        lua_close(L);

        return false;
    }

#if defined (WITH_LUA_5_2) || defined (WITH_LUA_5_1)
    if (lua_dump(L, Lua::blob_keeper, reinterpret_cast<void *>(&m_blob))) {
#else
    if (lua_dump(L, Lua::blob_keeper, reinterpret_cast<void *>(&m_blob), 0)) {
#endif
        const char *luaerr = lua_tostring(L, -1);
        err->assign("Failed to compile script '" + script + "");
        if (luaerr) {
            err->append(": " + std::string(luaerr));
        }
        err->append(".");
        lua_close(L);

        return false;
    }

    lua_close(L);
    return true;
#else
    err->assign("Lua support was not enabled.");
    return false;
#endif
}

#ifdef WITH_LUA
int Lua::blob_keeper(lua_State *L, const void *p, size_t sz, void *ud) {
    LuaScriptBlob *lsb = static_cast<LuaScriptBlob *>(ud);
    lsb->write(p, sz);
    return 0;
}


const char *Lua::blob_reader(lua_State *L, void *ud, size_t *size) {
    LuaScriptBlob *lsb = static_cast<LuaScriptBlob *>(ud);
    const char *data = lsb->read(size);
    return data;
}
#endif


int Lua::run(Transaction *t, const std::string &str) {
#ifdef WITH_LUA
    std::string luaRet;
    const char *a = NULL;
    int ret = true;
    lua_State *L = luaL_newstate();
    luaL_openlibs(L);

    luaL_newmetatable(L, "luaL_msc");
    lua_newtable(L);

    lua_pushlightuserdata(L, reinterpret_cast<void *>(t));
    lua_setglobal(L, "__transaction");

    luaL_setfuncs(L, mscLuaLib, 0);
    lua_setglobal(L, "m");

#ifdef WITH_LUA_5_1
    int rc = lua_load(L, Lua::blob_reader, &m_blob, m_scriptName.c_str());
#else
    int rc = lua_load(L, Lua::blob_reader, &m_blob, m_scriptName.c_str(),
        NULL);
#endif
    if (rc != LUA_OK) {
        std::string e;
        e.assign("Failed to execute lua script: " + m_scriptName + ". ");
        switch (rc) {
            case LUA_ERRSYNTAX:
                e.assign("Syntax error. ");
                break;
            case LUA_ERRMEM:
                e.assign("Memory error. ");
                break;
#ifndef WITH_LUA_5_1
            case LUA_ERRGCMM:
                e.assign("Garbage Collector error. ");
                break;
#endif
        }
        e.append(lua_tostring(L, -1));
        ms_dbg_a(t, 2, e);
        ret = false;
        goto err;
    }

    if (lua_pcall(L, 0, 0, 0)) {
        std::string e;
        const char *luaerr = lua_tostring(L, -1);
        e.assign("Failed to execute lua script: " + m_scriptName \
            + " (before main)");
        if (luaerr != NULL) {
            e.append(" - ");
            e.append(luaerr);
        }
        ms_dbg_a(t, 2, e);

        ret = false;
        goto err;
    }

    lua_setglobal(L, "modsec");

    lua_getglobal(L, "main");

    ms_dbg_a(t, 1, str);

    /* Put the parameter on the stack. */
    if (!str.empty() ) {
        lua_pushlstring(L, str.c_str(), str.length());
    }

    if (lua_pcall(L, ((!str.empty()) ? 1 : 0), 1, 0)) {
        std::string e;
        const char *luaerr = lua_tostring(L, -1);
        e.assign("Failed to execute lua script: " + m_scriptName + " (main)");
        if (luaerr != NULL) {
            e.append(" - ");
            e.append(luaerr);
        }
        ms_dbg_a(t, 2, e);

        ret = false;
        goto err;
    }

    a = reinterpret_cast<const char *>(lua_tostring(L, -1));
    if (a != NULL) {
        luaRet.assign(a);
    }

    ms_dbg_a(t, 9, "Returning from lua script: " + luaRet);

    if (luaRet.size() == 0) {
        ret = false;
    }


err:
    lua_pop(L, 1);
    lua_close(L);

    return ret;
#else
    ms_dbg_a(t, 9, "Lua support was not enabled.");

    return false;
#endif
}


#ifdef WITH_LUA
int Lua::log(lua_State *L) {
    const Transaction *t = NULL;
    const char *text;
    int level;

    /* Retrieve parameters. */
    level = luaL_checknumber(L, 1);
    text = luaL_checkstring(L, 2);

    /* Retrieve msr. */
    lua_getglobal(L, "__transaction");
    t = reinterpret_cast<const Transaction *>(lua_topointer(L, -1));

    /* Log message. */
    if (t != NULL) {
        ms_dbg_a(t, level, text);
    }

    return 0;
}


int Lua::getvar(lua_State *L) {
    const char *varname = NULL;
    Transaction *t = NULL;
    void *z = NULL;

    /* Retrieve parameters. */
    varname = reinterpret_cast<const char *>(luaL_checkstring(L, 1));

    lua_getglobal(L, "__transaction");
    z = const_cast<void *>(lua_topointer(L, -1));
    t = reinterpret_cast<Transaction *>(z);

    std::string var = variables::Variable::stringMatchResolve(t, varname);
    var = applyTransformations(L, t, 2, var);

    if (var.size() == 0) {
        lua_pushnil(L);
        return 0;
    }

    lua_pushlstring(L, var.c_str(), var.size());

    return 1;
}


int Lua::getvars(lua_State *L) {
    const char *varname = NULL;
    Transaction *t = NULL;
    void *z = NULL;
    std::vector<const VariableValue *> l;
    int idx = 1;

    /* Retrieve parameters. */
    varname = reinterpret_cast<const char *>(luaL_checkstring(L, 1));

    lua_getglobal(L, "__transaction");
    z = const_cast<void *>(lua_topointer(L, -1));
    t = reinterpret_cast<Transaction *>(z);

    variables::Variable::stringMatchResolveMulti(t, varname, &l);

    lua_newtable(L);
    for (auto i : l) {
        lua_pushnumber(L, idx);
        lua_newtable(L);

        lua_pushstring(L, "name");
        lua_pushlstring(L, i->getKeyWithCollection().c_str(), i->getKeyWithCollection().size());
        lua_settable(L, -3);

        lua_pushstring(L, "value");
        lua_pushlstring(L, i->getValue().c_str(), i->getValue().size());
        lua_settable(L, -3);

        lua_settable(L, -3);
        idx++;
    }

    for (const VariableValue * i : l) {
        delete i;
    }

    return 1;
}


int Lua::setvar(lua_State *L) {
    Transaction *t = NULL;
    const char *var_value = NULL;
    const char *var_name = NULL;
    std::string vname;
    std::string collection;
    std::string variableName;
    int nargs = lua_gettop(L);
    char *chr = NULL;
    size_t pos;
    void *z = NULL;

    lua_getglobal(L, "__transaction");
    z = const_cast<void *>(lua_topointer(L, -1));
    t = reinterpret_cast<Transaction *>(z);


    if (nargs != 2) {
        ms_dbg_a(t, 8,
            "m.setvar: Failed m.setvar funtion must has 2 arguments");
        return -1;
    }
    var_value = luaL_checkstring(L, 2);
    var_name = luaL_checkstring(L, 1);

    lua_pop(L, 2);

    if (var_value == NULL || var_name == NULL) {
        return -1;
    }

    vname.assign(var_name);
    pos = vname.find(".");
    if (pos != std::string::npos) {
        collection = std::string(vname, 0, pos);
        collection = utils::string::toupper(collection);
        variableName = std::string(vname, pos + 1,
            std::string::npos);

    } else {
        ms_dbg_a(t, 8,
            "m.setvar: Must specify a collection using dot character" \
            " - ie m.setvar(tx.myvar,mydata)");
        return -1;
    }

    if (collection == "TX") {
        t->m_collections.m_tx_collection->storeOrUpdateFirst(
            variableName,
            var_value);
    }
    else if (collection == "IP") {
        t->m_collections.m_ip_collection->storeOrUpdateFirst(
            variableName, t->m_collections.m_ip_collection_key,
            t->m_rules->m_secWebAppId.m_value,
            var_value);
    }
    else if (collection == "GLOBAL") {
        t->m_collections.m_global_collection->storeOrUpdateFirst(
            variableName, t->m_collections.m_global_collection_key,
            t->m_rules->m_secWebAppId.m_value,
            var_value);
    }
    else if (collection == "RESOURCE") {
        t->m_collections.m_resource_collection->storeOrUpdateFirst(
            variableName,
            t->m_collections.m_resource_collection_key, 
            t->m_rules->m_secWebAppId.m_value,
            var_value);
    }
    else if (collection == "SESSION") {
         t->m_collections.m_session_collection->storeOrUpdateFirst(
            variableName, t->m_collections.m_session_collection_key,
                    t->m_rules->m_secWebAppId.m_value,
            var_value);
    }
    else if (collection == "USER") {
        t->m_collections.m_user_collection->storeOrUpdateFirst(
            variableName, t->m_collections.m_user_collection_key,
                    t->m_rules->m_secWebAppId.m_value,
            var_value);

    }
    return 0;
}


std::string Lua::applyTransformations(lua_State *L, Transaction *t,
    int idx, std::string var) {
    std::string newVar = var;

    if (lua_isuserdata(L, idx) || lua_isnoneornil(L, idx)) {
        return var;
    }

    if (lua_istable(L, idx)) {
        const char *name = NULL;
#ifdef WITH_LUA_5_1
        int i, n = lua_objlen(L, idx);
#else
        int i, n = lua_rawlen(L, idx);
#endif

        for (i = 1; i <= n; i++) {
            lua_rawgeti(L, idx, i);
            name = reinterpret_cast<const char *>(luaL_checkstring(L, -1));

            /* A "none" means start over */
            if (strcmp("none", name) == 0) {
                newVar = var;
                continue;
            }

            actions::transformations::Transformation *tfn = \
                actions::transformations::Transformation::instantiate(
                    "t:" + std::string(name));
            // FIXME: transformation is not yet returning null.
            if (tfn) {
                newVar = tfn->evaluate(newVar, t);
            } else {
                ms_dbg_a(t, 1,
                    "SecRuleScript: Invalid transformation function: " \
                    + std::string(name));
            }
            delete tfn;
        }

        return newVar;
    }

    if (lua_isstring(L, idx)) {
        const char *name = NULL;
        name = reinterpret_cast<const char *>(luaL_checkstring(L, idx));

        actions::transformations::Transformation *tfn = \
            actions::transformations::Transformation::instantiate(
                "t:" + std::string(name));

        // FIXME: transformation is not yet returning null.
        if (tfn) {
            newVar = tfn->evaluate(newVar, t);
            delete tfn;
        } else {
            ms_dbg_a(t, 1, "SecRuleScript: Invalid transformation function: " \
                + std::string(name));
        }
        return newVar;
    }
    ms_dbg_a(t, 8, "SecRuleScript: Transformation parameter must be a " \
        "transformation name or array of transformation names, but found " \
        "" + std::string(lua_typename(L, idx)) + " (type " \
        + std::to_string(lua_type(L, idx)) + ")");
    return newVar;
}
#endif

}  //  namespace engine
}  //  namespace modsecurity

