
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_logby.h.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_LOGBY_H_INCLUDED_
#define _NGX_STREAM_LUA_LOGBY_H_INCLUDED_


#include "ngx_stream_lua_common.h"


ngx_int_t ngx_stream_lua_log_handler(ngx_stream_session_t *r);

ngx_int_t ngx_stream_lua_log_handler_inline(ngx_stream_lua_request_t *r);
ngx_int_t ngx_stream_lua_log_handler_file(ngx_stream_lua_request_t *r);


#endif /* _NGX_STREAM_LUA_LOGBY_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
