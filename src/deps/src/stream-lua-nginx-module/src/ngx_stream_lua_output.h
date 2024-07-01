
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_output.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_OUTPUT_H_INCLUDED_
#define _NGX_STREAM_LUA_OUTPUT_H_INCLUDED_


#include "ngx_stream_lua_common.h"


void ngx_stream_lua_inject_output_api(lua_State *L);

size_t ngx_stream_lua_calc_strlen_in_table(lua_State *L, int index, int arg_i,
    unsigned strict);

u_char *ngx_stream_lua_copy_str_in_table(lua_State *L, int index, u_char *dst);

ngx_int_t ngx_stream_lua_flush_resume_helper(ngx_stream_lua_request_t *r,
    ngx_stream_lua_ctx_t *ctx);


#endif /* _NGX_STREAM_LUA_OUTPUT_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
