
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_coroutine.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_COROUTINE_H_INCLUDED_
#define _NGX_STREAM_LUA_COROUTINE_H_INCLUDED_


#include "ngx_stream_lua_common.h"


void ngx_stream_lua_inject_coroutine_api(ngx_log_t *log, lua_State *L);

int ngx_stream_lua_coroutine_create_helper(lua_State *L,
    ngx_stream_lua_request_t *r, ngx_stream_lua_ctx_t *ctx,
    ngx_stream_lua_co_ctx_t **pcoctx);


#endif /* _NGX_STREAM_LUA_COROUTINE_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
