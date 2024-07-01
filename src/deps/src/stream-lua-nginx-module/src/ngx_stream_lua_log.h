
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_log.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_LOG_H_INCLUDED_
#define _NGX_STREAM_LUA_LOG_H_INCLUDED_


#include "ngx_stream_lua_common.h"


void ngx_stream_lua_inject_log_api(lua_State *L);

#ifdef HAVE_INTERCEPT_ERROR_LOG_PATCH
ngx_int_t ngx_stream_lua_capture_log_handler(ngx_log_t *log,
    ngx_uint_t level, u_char *buf, size_t n);
#endif


#endif /* _NGX_STREAM_LUA_LOG_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
