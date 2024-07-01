
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_initworkerby.h.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_INITWORKERBY_H_INCLUDED_
#define _NGX_STREAM_LUA_INITWORKERBY_H_INCLUDED_


#include "ngx_stream_lua_common.h"


ngx_int_t ngx_stream_lua_init_worker_by_inline(ngx_log_t *log,
    ngx_stream_lua_main_conf_t *lmcf, lua_State *L);

ngx_int_t ngx_stream_lua_init_worker_by_file(ngx_log_t *log,
    ngx_stream_lua_main_conf_t *lmcf, lua_State *L);

ngx_int_t ngx_stream_lua_init_worker(ngx_cycle_t *cycle);


#endif /* _NGX_STREAM_LUA_INITWORKERBY_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
