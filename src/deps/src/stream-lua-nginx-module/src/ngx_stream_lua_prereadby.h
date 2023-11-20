
/*
 * Copyright (C) OpenResty Inc.
 */


#ifndef _NGX_STREAM_LUA_PREREAD_H_INCLUDED_
#define _NGX_STREAM_LUA_PREREAD_H_INCLUDED_


#include "ngx_stream_lua_common.h"


ngx_int_t ngx_stream_lua_preread_handler(ngx_stream_session_t *s);
ngx_int_t ngx_stream_lua_preread_handler_inline(ngx_stream_lua_request_t *r);
ngx_int_t ngx_stream_lua_preread_handler_file(ngx_stream_lua_request_t *r);


#endif /* _NGX_STREAM_LUA_PREREAD_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
