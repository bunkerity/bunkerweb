/*=========================================================================*\
* TCP object
* LuaSocket toolkit
\*=========================================================================*/
#include "luasocket.h"

#include "auxiliar.h"
#include "socket.h"
#include "inet.h"
#include "options.h"
#include "tcp.h"

#include <string.h>

/*=========================================================================*\
* Internal function prototypes
\*=========================================================================*/
static int global_create(lua_State *L);
static int global_create4(lua_State *L);
static int global_create6(lua_State *L);
static int global_connect(lua_State *L);
static int meth_connect(lua_State *L);
static int meth_listen(lua_State *L);
static int meth_getfamily(lua_State *L);
static int meth_bind(lua_State *L);
static int meth_send(lua_State *L);
static int meth_getstats(lua_State *L);
static int meth_setstats(lua_State *L);
static int meth_getsockname(lua_State *L);
static int meth_getpeername(lua_State *L);
static int meth_shutdown(lua_State *L);
static int meth_receive(lua_State *L);
static int meth_accept(lua_State *L);
static int meth_close(lua_State *L);
static int meth_getoption(lua_State *L);
static int meth_setoption(lua_State *L);
static int meth_gettimeout(lua_State *L);
static int meth_settimeout(lua_State *L);
static int meth_getfd(lua_State *L);
static int meth_setfd(lua_State *L);
static int meth_dirty(lua_State *L);

/* tcp object methods */
static luaL_Reg tcp_methods[] = {
    {"__gc",        meth_close},
    {"__tostring",  auxiliar_tostring},
    {"accept",      meth_accept},
    {"bind",        meth_bind},
    {"close",       meth_close},
    {"connect",     meth_connect},
    {"dirty",       meth_dirty},
    {"getfamily",   meth_getfamily},
    {"getfd",       meth_getfd},
    {"getoption",   meth_getoption},
    {"getpeername", meth_getpeername},
    {"getsockname", meth_getsockname},
    {"getstats",    meth_getstats},
    {"setstats",    meth_setstats},
    {"listen",      meth_listen},
    {"receive",     meth_receive},
    {"send",        meth_send},
    {"setfd",       meth_setfd},
    {"setoption",   meth_setoption},
    {"setpeername", meth_connect},
    {"setsockname", meth_bind},
    {"settimeout",  meth_settimeout},
    {"gettimeout",  meth_gettimeout},
    {"shutdown",    meth_shutdown},
    {NULL,          NULL}
};

/* socket option handlers */
static t_opt optget[] = {
    {"keepalive",   opt_get_keepalive},
    {"reuseaddr",   opt_get_reuseaddr},
    {"reuseport",   opt_get_reuseport},
    {"tcp-nodelay", opt_get_tcp_nodelay},
#ifdef TCP_KEEPIDLE
    {"tcp-keepidle", opt_get_tcp_keepidle},
#endif
#ifdef TCP_KEEPCNT
    {"tcp-keepcnt", opt_get_tcp_keepcnt},
#endif
#ifdef TCP_KEEPINTVL
    {"tcp-keepintvl", opt_get_tcp_keepintvl},
#endif
    {"linger",      opt_get_linger},
    {"error",       opt_get_error},
	{"recv-buffer-size",     opt_get_recv_buf_size},
	{"send-buffer-size",     opt_get_send_buf_size},
    {NULL,          NULL}
};

static t_opt optset[] = {
    {"keepalive",   opt_set_keepalive},
    {"reuseaddr",   opt_set_reuseaddr},
    {"reuseport",   opt_set_reuseport},
    {"tcp-nodelay", opt_set_tcp_nodelay},
#ifdef TCP_KEEPIDLE
    {"tcp-keepidle", opt_set_tcp_keepidle},
#endif
#ifdef TCP_KEEPCNT
    {"tcp-keepcnt", opt_set_tcp_keepcnt},
#endif
#ifdef TCP_KEEPINTVL
    {"tcp-keepintvl", opt_set_tcp_keepintvl},
#endif
    {"ipv6-v6only", opt_set_ip6_v6only},
    {"linger",      opt_set_linger},
	{"recv-buffer-size",     opt_set_recv_buf_size},
	{"send-buffer-size",     opt_set_send_buf_size},
    {NULL,          NULL}
};

/* functions in library namespace */
static luaL_Reg func[] = {
    {"tcp", global_create},
    {"tcp4", global_create4},
    {"tcp6", global_create6},
    {"connect", global_connect},
    {NULL, NULL}
};

/*-------------------------------------------------------------------------*\
* Initializes module
\*-------------------------------------------------------------------------*/
int tcp_open(lua_State *L)
{
    /* create classes */
    auxiliar_newclass(L, "tcp{master}", tcp_methods);
    auxiliar_newclass(L, "tcp{client}", tcp_methods);
    auxiliar_newclass(L, "tcp{server}", tcp_methods);
    /* create class groups */
    auxiliar_add2group(L, "tcp{master}", "tcp{any}");
    auxiliar_add2group(L, "tcp{client}", "tcp{any}");
    auxiliar_add2group(L, "tcp{server}", "tcp{any}");
    /* define library functions */
    luaL_setfuncs(L, func, 0);
    return 0;
}

/*=========================================================================*\
* Lua methods
\*=========================================================================*/
/*-------------------------------------------------------------------------*\
* Just call buffered IO methods
\*-------------------------------------------------------------------------*/
static int meth_send(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{client}", 1);
    return buffer_meth_send(L, &tcp->buf);
}

static int meth_receive(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{client}", 1);
    return buffer_meth_receive(L, &tcp->buf);
}

static int meth_getstats(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{client}", 1);
    return buffer_meth_getstats(L, &tcp->buf);
}

static int meth_setstats(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{client}", 1);
    return buffer_meth_setstats(L, &tcp->buf);
}

/*-------------------------------------------------------------------------*\
* Just call option handler
\*-------------------------------------------------------------------------*/
static int meth_getoption(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return opt_meth_getoption(L, optget, &tcp->sock);
}

static int meth_setoption(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return opt_meth_setoption(L, optset, &tcp->sock);
}

/*-------------------------------------------------------------------------*\
* Select support methods
\*-------------------------------------------------------------------------*/
static int meth_getfd(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    lua_pushnumber(L, (int) tcp->sock);
    return 1;
}

/* this is very dangerous, but can be handy for those that are brave enough */
static int meth_setfd(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    tcp->sock = (t_socket) luaL_checknumber(L, 2);
    return 0;
}

static int meth_dirty(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    lua_pushboolean(L, !buffer_isempty(&tcp->buf));
    return 1;
}

/*-------------------------------------------------------------------------*\
* Waits for and returns a client object attempting connection to the
* server object
\*-------------------------------------------------------------------------*/
static int meth_accept(lua_State *L)
{
    p_tcp server = (p_tcp) auxiliar_checkclass(L, "tcp{server}", 1);
    p_timeout tm = timeout_markstart(&server->tm);
    t_socket sock;
    const char *err = inet_tryaccept(&server->sock, server->family, &sock, tm);
    /* if successful, push client socket */
    if (err == NULL) {
        p_tcp clnt = (p_tcp) lua_newuserdata(L, sizeof(t_tcp));
        auxiliar_setclass(L, "tcp{client}", -1);
        /* initialize structure fields */
        memset(clnt, 0, sizeof(t_tcp));
        socket_setnonblocking(&sock);
        clnt->sock = sock;
        io_init(&clnt->io, (p_send) socket_send, (p_recv) socket_recv,
                (p_error) socket_ioerror, &clnt->sock);
        timeout_init(&clnt->tm, -1, -1);
        buffer_init(&clnt->buf, &clnt->io, &clnt->tm);
        clnt->family = server->family;
        return 1;
    } else {
        lua_pushnil(L);
        lua_pushstring(L, err);
        return 2;
    }
}

/*-------------------------------------------------------------------------*\
* Binds an object to an address
\*-------------------------------------------------------------------------*/
static int meth_bind(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{master}", 1);
    const char *address =  luaL_checkstring(L, 2);
    const char *port = luaL_checkstring(L, 3);
    const char *err;
    struct addrinfo bindhints;
    memset(&bindhints, 0, sizeof(bindhints));
    bindhints.ai_socktype = SOCK_STREAM;
    bindhints.ai_family = tcp->family;
    bindhints.ai_flags = AI_PASSIVE;
    err = inet_trybind(&tcp->sock, &tcp->family, address, port, &bindhints);
    if (err) {
        lua_pushnil(L);
        lua_pushstring(L, err);
        return 2;
    }
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Turns a master tcp object into a client object.
\*-------------------------------------------------------------------------*/
static int meth_connect(lua_State *L) {
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    const char *address =  luaL_checkstring(L, 2);
    const char *port = luaL_checkstring(L, 3);
    struct addrinfo connecthints;
    const char *err;
    memset(&connecthints, 0, sizeof(connecthints));
    connecthints.ai_socktype = SOCK_STREAM;
    /* make sure we try to connect only to the same family */
    connecthints.ai_family = tcp->family;
    timeout_markstart(&tcp->tm);
    err = inet_tryconnect(&tcp->sock, &tcp->family, address, port,
        &tcp->tm, &connecthints);
    /* have to set the class even if it failed due to non-blocking connects */
    auxiliar_setclass(L, "tcp{client}", 1);
    if (err) {
        lua_pushnil(L);
        lua_pushstring(L, err);
        return 2;
    }
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Closes socket used by object
\*-------------------------------------------------------------------------*/
static int meth_close(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    socket_destroy(&tcp->sock);
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Returns family as string
\*-------------------------------------------------------------------------*/
static int meth_getfamily(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    if (tcp->family == AF_INET6) {
        lua_pushliteral(L, "inet6");
        return 1;
    } else if (tcp->family == AF_INET) {
        lua_pushliteral(L, "inet4");
        return 1;
    } else {
        lua_pushliteral(L, "inet4");
        return 1;
    }
}

/*-------------------------------------------------------------------------*\
* Puts the sockt in listen mode
\*-------------------------------------------------------------------------*/
static int meth_listen(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{master}", 1);
    int backlog = (int) luaL_optnumber(L, 2, 32);
    int err = socket_listen(&tcp->sock, backlog);
    if (err != IO_DONE) {
        lua_pushnil(L);
        lua_pushstring(L, socket_strerror(err));
        return 2;
    }
    /* turn master object into a server object */
    auxiliar_setclass(L, "tcp{server}", 1);
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Shuts the connection down partially
\*-------------------------------------------------------------------------*/
static int meth_shutdown(lua_State *L)
{
    /* SHUT_RD,  SHUT_WR,  SHUT_RDWR  have  the value 0, 1, 2, so we can use method index directly */
    static const char* methods[] = { "receive", "send", "both", NULL };
    p_tcp tcp = (p_tcp) auxiliar_checkclass(L, "tcp{client}", 1);
    int how = luaL_checkoption(L, 2, "both", methods);
    socket_shutdown(&tcp->sock, how);
    lua_pushnumber(L, 1);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Just call inet methods
\*-------------------------------------------------------------------------*/
static int meth_getpeername(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return inet_meth_getpeername(L, &tcp->sock, tcp->family);
}

static int meth_getsockname(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return inet_meth_getsockname(L, &tcp->sock, tcp->family);
}

/*-------------------------------------------------------------------------*\
* Just call tm methods
\*-------------------------------------------------------------------------*/
static int meth_settimeout(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return timeout_meth_settimeout(L, &tcp->tm);
}

static int meth_gettimeout(lua_State *L)
{
    p_tcp tcp = (p_tcp) auxiliar_checkgroup(L, "tcp{any}", 1);
    return timeout_meth_gettimeout(L, &tcp->tm);
}

/*=========================================================================*\
* Library functions
\*=========================================================================*/
/*-------------------------------------------------------------------------*\
* Creates a master tcp object
\*-------------------------------------------------------------------------*/
static int tcp_create(lua_State *L, int family) {
    p_tcp tcp = (p_tcp) lua_newuserdata(L, sizeof(t_tcp));
    memset(tcp, 0, sizeof(t_tcp));
    /* set its type as master object */
    auxiliar_setclass(L, "tcp{master}", -1);
    /* if family is AF_UNSPEC, we leave the socket invalid and
     * store AF_UNSPEC into family. This will allow it to later be
     * replaced with an AF_INET6 or AF_INET socket upon first use. */
    tcp->sock = SOCKET_INVALID;
    tcp->family = family;
    io_init(&tcp->io, (p_send) socket_send, (p_recv) socket_recv,
            (p_error) socket_ioerror, &tcp->sock);
    timeout_init(&tcp->tm, -1, -1);
    buffer_init(&tcp->buf, &tcp->io, &tcp->tm);
    if (family != AF_UNSPEC) {
        const char *err = inet_trycreate(&tcp->sock, family, SOCK_STREAM, 0);
        if (err != NULL) {
            lua_pushnil(L);
            lua_pushstring(L, err);
            return 2;
        }
        socket_setnonblocking(&tcp->sock);
    }
    return 1;
}

static int global_create(lua_State *L) {
    return tcp_create(L, AF_UNSPEC);
}

static int global_create4(lua_State *L) {
    return tcp_create(L, AF_INET);
}

static int global_create6(lua_State *L) {
    return tcp_create(L, AF_INET6);
}

static int global_connect(lua_State *L) {
    const char *remoteaddr = luaL_checkstring(L, 1);
    const char *remoteserv = luaL_checkstring(L, 2);
    const char *localaddr  = luaL_optstring(L, 3, NULL);
    const char *localserv  = luaL_optstring(L, 4, "0");
    int family = inet_optfamily(L, 5, "unspec");
    p_tcp tcp = (p_tcp) lua_newuserdata(L, sizeof(t_tcp));
    struct addrinfo bindhints, connecthints;
    const char *err = NULL;
    /* initialize tcp structure */
    memset(tcp, 0, sizeof(t_tcp));
    io_init(&tcp->io, (p_send) socket_send, (p_recv) socket_recv,
            (p_error) socket_ioerror, &tcp->sock);
    timeout_init(&tcp->tm, -1, -1);
    buffer_init(&tcp->buf, &tcp->io, &tcp->tm);
    tcp->sock = SOCKET_INVALID;
    tcp->family = AF_UNSPEC;
    /* allow user to pick local address and port */
    memset(&bindhints, 0, sizeof(bindhints));
    bindhints.ai_socktype = SOCK_STREAM;
    bindhints.ai_family = family;
    bindhints.ai_flags = AI_PASSIVE;
    if (localaddr) {
        err = inet_trybind(&tcp->sock, &tcp->family, localaddr,
            localserv, &bindhints);
        if (err) {
            lua_pushnil(L);
            lua_pushstring(L, err);
            return 2;
        }
    }
    /* try to connect to remote address and port */
    memset(&connecthints, 0, sizeof(connecthints));
    connecthints.ai_socktype = SOCK_STREAM;
    /* make sure we try to connect only to the same family */
    connecthints.ai_family = tcp->family;
    err = inet_tryconnect(&tcp->sock, &tcp->family, remoteaddr, remoteserv,
         &tcp->tm, &connecthints);
    if (err) {
        socket_destroy(&tcp->sock);
        lua_pushnil(L);
        lua_pushstring(L, err);
        return 2;
    }
    auxiliar_setclass(L, "tcp{client}", -1);
    return 1;
}
