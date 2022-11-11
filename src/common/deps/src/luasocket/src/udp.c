/*=========================================================================*\
* UDP object
* LuaSocket toolkit
\*=========================================================================*/
#include "luasocket.h"

#include "auxiliar.h"
#include "socket.h"
#include "inet.h"
#include "options.h"
#include "udp.h"

#include <string.h>
#include <stdlib.h>

/* min and max macros */
#ifndef MIN
#define MIN(x, y) ((x) < (y) ? x : y)
#endif
#ifndef MAX
#define MAX(x, y) ((x) > (y) ? x : y)
#endif

/*=========================================================================*\
* Internal function prototypes
\*=========================================================================*/
static int global_create(lua_State *L);
static int global_create4(lua_State *L);
static int global_create6(lua_State *L);
static int meth_send(lua_State *L);
static int meth_sendto(lua_State *L);
static int meth_receive(lua_State *L);
static int meth_receivefrom(lua_State *L);
static int meth_getfamily(lua_State *L);
static int meth_getsockname(lua_State *L);
static int meth_getpeername(lua_State *L);
static int meth_gettimeout(lua_State *L);
static int meth_setsockname(lua_State *L);
static int meth_setpeername(lua_State *L);
static int meth_close(lua_State *L);
static int meth_setoption(lua_State *L);
static int meth_getoption(lua_State *L);
static int meth_settimeout(lua_State *L);
static int meth_getfd(lua_State *L);
static int meth_setfd(lua_State *L);
static int meth_dirty(lua_State *L);

/* udp object methods */
static luaL_Reg udp_methods[] = {
    {"__gc",        meth_close},
    {"__tostring",  auxiliar_tostring},
    {"close",       meth_close},
    {"dirty",       meth_dirty},
    {"getfamily",   meth_getfamily},
    {"getfd",       meth_getfd},
    {"getpeername", meth_getpeername},
    {"getsockname", meth_getsockname},
    {"receive",     meth_receive},
    {"receivefrom", meth_receivefrom},
    {"send",        meth_send},
    {"sendto",      meth_sendto},
    {"setfd",       meth_setfd},
    {"setoption",   meth_setoption},
    {"getoption",   meth_getoption},
    {"setpeername", meth_setpeername},
    {"setsockname", meth_setsockname},
    {"settimeout",  meth_settimeout},
    {"gettimeout",  meth_gettimeout},
    {NULL,          NULL}
};

/* socket options for setoption */
static t_opt optset[] = {
    {"dontroute",            opt_set_dontroute},
    {"broadcast",            opt_set_broadcast},
    {"reuseaddr",            opt_set_reuseaddr},
    {"reuseport",            opt_set_reuseport},
    {"ip-multicast-if",      opt_set_ip_multicast_if},
    {"ip-multicast-ttl",     opt_set_ip_multicast_ttl},
    {"ip-multicast-loop",    opt_set_ip_multicast_loop},
    {"ip-add-membership",    opt_set_ip_add_membership},
    {"ip-drop-membership",   opt_set_ip_drop_membersip},
    {"ipv6-unicast-hops",    opt_set_ip6_unicast_hops},
    {"ipv6-multicast-hops",  opt_set_ip6_unicast_hops},
    {"ipv6-multicast-loop",  opt_set_ip6_multicast_loop},
    {"ipv6-add-membership",  opt_set_ip6_add_membership},
    {"ipv6-drop-membership", opt_set_ip6_drop_membersip},
    {"ipv6-v6only",          opt_set_ip6_v6only},
	{"recv-buffer-size",     opt_set_recv_buf_size},
	{"send-buffer-size",     opt_set_send_buf_size},
    {NULL,                   NULL}
};

/* socket options for getoption */
static t_opt optget[] = {
    {"dontroute",            opt_get_dontroute},
    {"broadcast",            opt_get_broadcast},
    {"reuseaddr",            opt_get_reuseaddr},
    {"reuseport",            opt_get_reuseport},
    {"ip-multicast-if",      opt_get_ip_multicast_if},
    {"ip-multicast-loop",    opt_get_ip_multicast_loop},
    {"error",                opt_get_error},
    {"ipv6-unicast-hops",    opt_get_ip6_unicast_hops},
    {"ipv6-multicast-hops",  opt_get_ip6_unicast_hops},
    {"ipv6-multicast-loop",  opt_get_ip6_multicast_loop},
    {"ipv6-v6only",          opt_get_ip6_v6only},
	{"recv-buffer-size",     opt_get_recv_buf_size},
	{"send-buffer-size",     opt_get_send_buf_size},
    {NULL,                   NULL}
};

/* functions in library namespace */
static luaL_Reg func[] = {
    {"udp", global_create},
    {"udp4", global_create4},
    {"udp6", global_create6},
    {NULL, NULL}
};

/*-------------------------------------------------------------------------*\
* Initializes module
\*-------------------------------------------------------------------------*/
int udp_open(lua_State *L) {
    /* create classes */
    auxiliar_newclass(L, "udp{connected}", udp_methods);
    auxiliar_newclass(L, "udp{unconnected}", udp_methods);
    /* create class groups */
    auxiliar_add2group(L, "udp{connected}",   "udp{any}");
    auxiliar_add2group(L, "udp{unconnected}", "udp{any}");
    auxiliar_add2group(L, "udp{connected}",   "select{able}");
    auxiliar_add2group(L, "udp{unconnected}", "select{able}");
    /* define library functions */
    luaL_setfuncs(L, func, 0);
    /* export default UDP size */
    lua_pushliteral(L, "_DATAGRAMSIZE");
    lua_pushinteger(L, UDP_DATAGRAMSIZE);
    lua_rawset(L, -3);
    return 0;
}

/*=========================================================================*\
* Lua methods
\*=========================================================================*/
static const char *udp_strerror(int err) {
    /* a 'closed' error on an unconnected means the target address was not
     * accepted by the transport layer */
    if (err == IO_CLOSED) return "refused";
    else return socket_strerror(err);
}

/*-------------------------------------------------------------------------*\
* Send data through connected udp socket
\*-------------------------------------------------------------------------*/
static int meth_send(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkclass(L, "udp{connected}", 1);
    p_timeout tm = &udp->tm;
    size_t count, sent = 0;
    int err;
    const char *data = luaL_checklstring(L, 2, &count);
    timeout_markstart(tm);
    err = socket_send(&udp->sock, data, count, &sent, tm);
    if (err != IO_DONE) {
        lua_pushnil(L);
        lua_pushstring(L, udp_strerror(err));
        return 2;
    }
    lua_pushnumber(L, (lua_Number) sent);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Send data through unconnected udp socket
\*-------------------------------------------------------------------------*/
static int meth_sendto(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkclass(L, "udp{unconnected}", 1);
    size_t count, sent = 0;
    const char *data = luaL_checklstring(L, 2, &count);
    const char *ip = luaL_checkstring(L, 3);
    const char *port = luaL_checkstring(L, 4);
    p_timeout tm = &udp->tm;
    int err;
    struct addrinfo aihint;
    struct addrinfo *ai;
    memset(&aihint, 0, sizeof(aihint));
    aihint.ai_family = udp->family;
    aihint.ai_socktype = SOCK_DGRAM;
    aihint.ai_flags = AI_NUMERICHOST;
#ifdef AI_NUMERICSERV
    aihint.ai_flags |= AI_NUMERICSERV;
#endif
    err = getaddrinfo(ip, port, &aihint, &ai);
	if (err) {
        lua_pushnil(L);
        lua_pushstring(L, gai_strerror(err));
        return 2;
    }

    /* create socket if on first sendto if AF_UNSPEC was set */
    if (udp->family == AF_UNSPEC && udp->sock == SOCKET_INVALID) {
        struct addrinfo *ap;
        const char *errstr = NULL;
        for (ap = ai; ap != NULL; ap = ap->ai_next) {
            errstr = inet_trycreate(&udp->sock, ap->ai_family, SOCK_DGRAM, 0);
            if (errstr == NULL) {
                socket_setnonblocking(&udp->sock);
                udp->family = ap->ai_family;
                break;
            }
        }
        if (errstr != NULL) {
            lua_pushnil(L);
            lua_pushstring(L, errstr);
            freeaddrinfo(ai);
            return 2;
        }
    }

    timeout_markstart(tm);
    err = socket_sendto(&udp->sock, data, count, &sent, ai->ai_addr,
        (socklen_t) ai->ai_addrlen, tm);
    freeaddrinfo(ai);
    if (err != IO_DONE) {
        lua_pushnil(L);
        lua_pushstring(L, udp_strerror(err));
        return 2;
    }
    lua_pushnumber(L, (lua_Number) sent);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Receives data from a UDP socket
\*-------------------------------------------------------------------------*/
static int meth_receive(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    char buf[UDP_DATAGRAMSIZE];
    size_t got, wanted = (size_t) luaL_optnumber(L, 2, sizeof(buf));
    char *dgram = wanted > sizeof(buf)? (char *) malloc(wanted): buf;
    int err;
    p_timeout tm = &udp->tm;
    timeout_markstart(tm);
    if (!dgram) {
        lua_pushnil(L);
        lua_pushliteral(L, "out of memory");
        return 2;
    }
    err = socket_recv(&udp->sock, dgram, wanted, &got, tm);
    /* Unlike TCP, recv() of zero is not closed, but a zero-length packet. */
    if (err != IO_DONE && err != IO_CLOSED) {
        lua_pushnil(L);
        lua_pushstring(L, udp_strerror(err));
        if (wanted > sizeof(buf)) free(dgram);
        return 2;
    }
    lua_pushlstring(L, dgram, got);
    if (wanted > sizeof(buf)) free(dgram);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Receives data and sender from a UDP socket
\*-------------------------------------------------------------------------*/
static int meth_receivefrom(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkclass(L, "udp{unconnected}", 1);
    char buf[UDP_DATAGRAMSIZE];
    size_t got, wanted = (size_t) luaL_optnumber(L, 2, sizeof(buf));
    char *dgram = wanted > sizeof(buf)? (char *) malloc(wanted): buf;
    struct sockaddr_storage addr;
    socklen_t addr_len = sizeof(addr);
    char addrstr[INET6_ADDRSTRLEN];
    char portstr[6];
    int err;
    p_timeout tm = &udp->tm;
    timeout_markstart(tm);
    if (!dgram) {
        lua_pushnil(L);
        lua_pushliteral(L, "out of memory");
        return 2;
    }
    err = socket_recvfrom(&udp->sock, dgram, wanted, &got, (SA *) &addr,
            &addr_len, tm);
    /* Unlike TCP, recv() of zero is not closed, but a zero-length packet. */
    if (err != IO_DONE && err != IO_CLOSED) {
        lua_pushnil(L);
        lua_pushstring(L, udp_strerror(err));
        if (wanted > sizeof(buf)) free(dgram);
        return 2;
    }
    err = getnameinfo((struct sockaddr *)&addr, addr_len, addrstr,
        INET6_ADDRSTRLEN, portstr, 6, NI_NUMERICHOST | NI_NUMERICSERV);
	if (err) {
        lua_pushnil(L);
        lua_pushstring(L, gai_strerror(err));
        if (wanted > sizeof(buf)) free(dgram);
        return 2;
    }
    lua_pushlstring(L, dgram, got);
    lua_pushstring(L, addrstr);
    lua_pushinteger(L, (int) strtol(portstr, (char **) NULL, 10));
    if (wanted > sizeof(buf)) free(dgram);
    return 3;
}

/*-------------------------------------------------------------------------*\
* Returns family as string
\*-------------------------------------------------------------------------*/
static int meth_getfamily(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    if (udp->family == AF_INET6) {
        lua_pushliteral(L, "inet6");
        return 1;
    } else {
        lua_pushliteral(L, "inet4");
        return 1;
    }
}

/*-------------------------------------------------------------------------*\
* Select support methods
\*-------------------------------------------------------------------------*/
static int meth_getfd(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    lua_pushnumber(L, (int) udp->sock);
    return 1;
}

/* this is very dangerous, but can be handy for those that are brave enough */
static int meth_setfd(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    udp->sock = (t_socket) luaL_checknumber(L, 2);
    return 0;
}

static int meth_dirty(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    (void) udp;
    lua_pushboolean(L, 0);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Just call inet methods
\*-------------------------------------------------------------------------*/
static int meth_getpeername(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkclass(L, "udp{connected}", 1);
    return inet_meth_getpeername(L, &udp->sock, udp->family);
}

static int meth_getsockname(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    return inet_meth_getsockname(L, &udp->sock, udp->family);
}

/*-------------------------------------------------------------------------*\
* Just call option handler
\*-------------------------------------------------------------------------*/
static int meth_setoption(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    return opt_meth_setoption(L, optset, &udp->sock);
}

/*-------------------------------------------------------------------------*\
* Just call option handler
\*-------------------------------------------------------------------------*/
static int meth_getoption(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    return opt_meth_getoption(L, optget, &udp->sock);
}

/*-------------------------------------------------------------------------*\
* Just call tm methods
\*-------------------------------------------------------------------------*/
static int meth_settimeout(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    return timeout_meth_settimeout(L, &udp->tm);
}

static int meth_gettimeout(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    return timeout_meth_gettimeout(L, &udp->tm);
}

/*-------------------------------------------------------------------------*\
* Turns a master udp object into a client object.
\*-------------------------------------------------------------------------*/
static int meth_setpeername(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    p_timeout tm = &udp->tm;
    const char *address = luaL_checkstring(L, 2);
    int connecting = strcmp(address, "*");
    const char *port = connecting? luaL_checkstring(L, 3): "0";
    struct addrinfo connecthints;
    const char *err;
    memset(&connecthints, 0, sizeof(connecthints));
    connecthints.ai_socktype = SOCK_DGRAM;
    /* make sure we try to connect only to the same family */
    connecthints.ai_family = udp->family;
    if (connecting) {
        err = inet_tryconnect(&udp->sock, &udp->family, address,
            port, tm, &connecthints);
        if (err) {
            lua_pushnil(L);
            lua_pushstring(L, err);
            return 2;
        }
        auxiliar_setclass(L, "udp{connected}", 1);
    } else {
        /* we ignore possible errors because Mac OS X always
         * returns EAFNOSUPPORT */
        inet_trydisconnect(&udp->sock, udp->family, tm);
        auxiliar_setclass(L, "udp{unconnected}", 1);
    }
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Closes socket used by object
\*-------------------------------------------------------------------------*/
static int meth_close(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkgroup(L, "udp{any}", 1);
    socket_destroy(&udp->sock);
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Turns a master object into a server object
\*-------------------------------------------------------------------------*/
static int meth_setsockname(lua_State *L) {
    p_udp udp = (p_udp) auxiliar_checkclass(L, "udp{unconnected}", 1);
    const char *address =  luaL_checkstring(L, 2);
    const char *port = luaL_checkstring(L, 3);
    const char *err;
    struct addrinfo bindhints;
    memset(&bindhints, 0, sizeof(bindhints));
    bindhints.ai_socktype = SOCK_DGRAM;
    bindhints.ai_family = udp->family;
    bindhints.ai_flags = AI_PASSIVE;
    err = inet_trybind(&udp->sock, &udp->family, address, port, &bindhints);
    if (err) {
        lua_pushnil(L);
        lua_pushstring(L, err);
        return 2;
    }
    lua_pushnumber(L, 1);
    return 1;
}

/*=========================================================================*\
* Library functions
\*=========================================================================*/
/*-------------------------------------------------------------------------*\
* Creates a master udp object
\*-------------------------------------------------------------------------*/
static int udp_create(lua_State *L, int family) {
    /* allocate udp object */
    p_udp udp = (p_udp) lua_newuserdata(L, sizeof(t_udp));
    auxiliar_setclass(L, "udp{unconnected}", -1);
    /* if family is AF_UNSPEC, we leave the socket invalid and
     * store AF_UNSPEC into family. This will allow it to later be
     * replaced with an AF_INET6 or AF_INET socket upon first use. */
    udp->sock = SOCKET_INVALID;
    timeout_init(&udp->tm, -1, -1);
    udp->family = family;
    if (family != AF_UNSPEC) {
        const char *err = inet_trycreate(&udp->sock, family, SOCK_DGRAM, 0);
        if (err != NULL) {
            lua_pushnil(L);
            lua_pushstring(L, err);
            return 2;
        }
        socket_setnonblocking(&udp->sock);
    }
    return 1;
}

static int global_create(lua_State *L) {
    return udp_create(L, AF_UNSPEC);
}

static int global_create4(lua_State *L) {
    return udp_create(L, AF_INET);
}

static int global_create6(lua_State *L) {
    return udp_create(L, AF_INET6);
}
