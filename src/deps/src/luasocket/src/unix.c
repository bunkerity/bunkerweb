/*=========================================================================*\
* Unix domain socket
* LuaSocket toolkit
\*=========================================================================*/
#include "luasocket.h"

#include "unixstream.h"
#include "unixdgram.h"

/*-------------------------------------------------------------------------*\
* Modules and functions
\*-------------------------------------------------------------------------*/
static const luaL_Reg mod[] = {
    {"stream", unixstream_open},
    {"dgram", unixdgram_open},
    {NULL, NULL}
};

static void add_alias(lua_State *L, int index, const char *name, const char *target)
{
    lua_getfield(L, index, target);
    lua_setfield(L, index, name);
}

static int compat_socket_unix_call(lua_State *L)
{
    /* Look up socket.unix.stream in the socket.unix table (which is the first
     * argument). */
    lua_getfield(L, 1, "stream");

    /* Replace the stack entry for the socket.unix table with the
     * socket.unix.stream function. */
    lua_replace(L, 1);

    /* Call socket.unix.stream, passing along any arguments. */
    int n = lua_gettop(L);
    lua_call(L, n-1, LUA_MULTRET);

    /* Pass along the return values from socket.unix.stream. */
    n = lua_gettop(L);
    return n;
}

/*-------------------------------------------------------------------------*\
* Initializes module
\*-------------------------------------------------------------------------*/
LUASOCKET_API int luaopen_socket_unix(lua_State *L)
{
    int i;
    lua_newtable(L);
    int socket_unix_table = lua_gettop(L);

    for (i = 0; mod[i].name; i++)
        mod[i].func(L);

    /* Add backwards compatibility aliases "tcp" and "udp" for the "stream" and
     * "dgram" functions. */
    add_alias(L, socket_unix_table, "tcp", "stream");
    add_alias(L, socket_unix_table, "udp", "dgram");

    /* Add a backwards compatibility function and a metatable setup to call it
     * for the old socket.unix() interface. */
    lua_pushcfunction(L, compat_socket_unix_call);
    lua_setfield(L, socket_unix_table, "__call");
    lua_pushvalue(L, socket_unix_table);
    lua_setmetatable(L, socket_unix_table);

    return 1;
}
