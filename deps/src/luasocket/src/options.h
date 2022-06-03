#ifndef OPTIONS_H
#define OPTIONS_H
/*=========================================================================*\
* Common option interface 
* LuaSocket toolkit
*
* This module provides a common interface to socket options, used mainly by
* modules UDP and TCP. 
\*=========================================================================*/

#include "luasocket.h"
#include "socket.h"

/* option registry */
typedef struct t_opt {
  const char *name;
  int (*func)(lua_State *L, p_socket ps);
} t_opt;
typedef t_opt *p_opt;

#ifndef _WIN32
#pragma GCC visibility push(hidden)
#endif

int opt_meth_setoption(lua_State *L, p_opt opt, p_socket ps);
int opt_meth_getoption(lua_State *L, p_opt opt, p_socket ps);

int opt_set_reuseaddr(lua_State *L, p_socket ps);
int opt_get_reuseaddr(lua_State *L, p_socket ps);

int opt_set_reuseport(lua_State *L, p_socket ps);
int opt_get_reuseport(lua_State *L, p_socket ps);

int opt_set_tcp_nodelay(lua_State *L, p_socket ps);
int opt_get_tcp_nodelay(lua_State *L, p_socket ps);

#ifdef TCP_KEEPIDLE
int opt_set_tcp_keepidle(lua_State *L, p_socket ps);
int opt_get_tcp_keepidle(lua_State *L, p_socket ps);
#endif

#ifdef TCP_KEEPCNT
int opt_set_tcp_keepcnt(lua_State *L, p_socket ps);
int opt_get_tcp_keepcnt(lua_State *L, p_socket ps);
#endif

#ifdef TCP_KEEPINTVL
int opt_set_tcp_keepintvl(lua_State *L, p_socket ps);
int opt_get_tcp_keepintvl(lua_State *L, p_socket ps);
#endif

int opt_set_keepalive(lua_State *L, p_socket ps);
int opt_get_keepalive(lua_State *L, p_socket ps);

int opt_set_dontroute(lua_State *L, p_socket ps);
int opt_get_dontroute(lua_State *L, p_socket ps);

int opt_set_broadcast(lua_State *L, p_socket ps);
int opt_get_broadcast(lua_State *L, p_socket ps);

int opt_set_recv_buf_size(lua_State *L, p_socket ps);
int opt_get_recv_buf_size(lua_State *L, p_socket ps);

int opt_set_send_buf_size(lua_State *L, p_socket ps);
int opt_get_send_buf_size(lua_State *L, p_socket ps);

int opt_set_ip6_unicast_hops(lua_State *L, p_socket ps);
int opt_get_ip6_unicast_hops(lua_State *L, p_socket ps);

int opt_set_ip6_multicast_hops(lua_State *L, p_socket ps);
int opt_get_ip6_multicast_hops(lua_State *L, p_socket ps);

int opt_set_ip_multicast_loop(lua_State *L, p_socket ps);
int opt_get_ip_multicast_loop(lua_State *L, p_socket ps);

int opt_set_ip6_multicast_loop(lua_State *L, p_socket ps);
int opt_get_ip6_multicast_loop(lua_State *L, p_socket ps);

int opt_set_linger(lua_State *L, p_socket ps);
int opt_get_linger(lua_State *L, p_socket ps);

int opt_set_ip_multicast_ttl(lua_State *L, p_socket ps);

int opt_set_ip_multicast_if(lua_State *L, p_socket ps);
int opt_get_ip_multicast_if(lua_State *L, p_socket ps);

int opt_set_ip_add_membership(lua_State *L, p_socket ps);
int opt_set_ip_drop_membersip(lua_State *L, p_socket ps);

int opt_set_ip6_add_membership(lua_State *L, p_socket ps);
int opt_set_ip6_drop_membersip(lua_State *L, p_socket ps);

int opt_set_ip6_v6only(lua_State *L, p_socket ps);
int opt_get_ip6_v6only(lua_State *L, p_socket ps);

int opt_get_error(lua_State *L, p_socket ps);

#ifndef _WIN32
#pragma GCC visibility pop
#endif

#endif
