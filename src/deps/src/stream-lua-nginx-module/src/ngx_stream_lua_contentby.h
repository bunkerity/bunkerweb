
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_contentby.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_CONTENT_BY_H_INCLUDED_
#define _NGX_STREAM_LUA_CONTENT_BY_H_INCLUDED_


#include "ngx_stream_lua_common.h"


ngx_int_t ngx_stream_lua_content_by_chunk(lua_State *L,
    ngx_stream_lua_request_t *r);
void ngx_stream_lua_content_wev_handler(ngx_stream_lua_request_t *r);
ngx_int_t ngx_stream_lua_content_handler_file(ngx_stream_lua_request_t *r);
ngx_int_t ngx_stream_lua_content_handler_inline(ngx_stream_lua_request_t *r);

void ngx_stream_lua_content_handler(ngx_stream_session_t *r);

ngx_int_t ngx_stream_lua_content_run_posted_threads(lua_State *L,
    ngx_stream_lua_request_t *r, ngx_stream_lua_ctx_t *ctx, int n);


#endif /* _NGX_STREAM_LUA_CONTENT_BY_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
