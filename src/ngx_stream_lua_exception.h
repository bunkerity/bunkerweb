
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_exception.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_EXCEPTION_H_INCLUDED_
#define _NGX_STREAM_LUA_EXCEPTION_H_INCLUDED_


#include "ngx_stream_lua_common.h"


#define NGX_LUA_EXCEPTION_TRY                                                \
    if (setjmp(ngx_stream_lua_exception) == 0)

#define NGX_LUA_EXCEPTION_CATCH                                              \
    else

#define NGX_LUA_EXCEPTION_THROW(x)                                           \
    longjmp(ngx_stream_lua_exception, (x))


extern jmp_buf ngx_stream_lua_exception;


int ngx_stream_lua_atpanic(lua_State *L);


#endif /* _NGX_STREAM_LUA_EXCEPTION_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
