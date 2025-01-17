
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_script.h.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_SCRIPT_H_INCLUDED_
#define _NGX_STREAM_LUA_SCRIPT_H_INCLUDED_


#include "ngx_stream_lua_common.h"


typedef struct {
    ngx_log_t                  *log;
    ngx_pool_t                 *pool;
    ngx_str_t                  *source;

    ngx_array_t               **lengths;
    ngx_array_t               **values;

    ngx_uint_t                  variables;

    unsigned                    complete_lengths:1;
    unsigned                    complete_values:1;
} ngx_stream_lua_script_compile_t;


typedef struct {
    ngx_str_t                   value;
    void                       *lengths;
    void                       *values;
} ngx_stream_lua_complex_value_t;


typedef struct {
    ngx_log_t                       *log;
    ngx_pool_t                      *pool;
    ngx_str_t                       *value;

    ngx_stream_lua_complex_value_t          *complex_value;
} ngx_stream_lua_compile_complex_value_t;


typedef struct {
    u_char                     *ip;
    u_char                     *pos;

    ngx_str_t                   buf;

    int                        *captures;
    ngx_uint_t                  ncaptures;
    u_char                     *captures_data;

    unsigned                    skip:1;

    ngx_log_t                  *log;
} ngx_stream_lua_script_engine_t;


typedef void (*ngx_stream_lua_script_code_pt) (
    ngx_stream_lua_script_engine_t *e);
typedef size_t (*ngx_stream_lua_script_len_code_pt)
    (ngx_stream_lua_script_engine_t *e);


typedef struct {
    ngx_stream_lua_script_code_pt           code;
    uintptr_t                               len;
} ngx_stream_lua_script_copy_code_t;


typedef struct {
    ngx_stream_lua_script_code_pt           code;
    uintptr_t                               n;
} ngx_stream_lua_script_capture_code_t;


ngx_int_t ngx_stream_lua_compile_complex_value(
    ngx_stream_lua_compile_complex_value_t *ccv);
ngx_int_t ngx_stream_lua_complex_value(ngx_stream_lua_request_t *r,
    ngx_str_t *subj, size_t offset, ngx_int_t count, int *cap,
    ngx_stream_lua_complex_value_t *val, luaL_Buffer *luabuf);


#endif /* _NGX_STREAM_LUA_SCRIPT_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
