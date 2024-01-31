
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_pcrefix.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_PCREFIX_H_INCLUDED_
#define _NGX_STREAM_LUA_PCREFIX_H_INCLUDED_


#include "ngx_stream_lua_common.h"


#if (NGX_PCRE)
ngx_pool_t *ngx_stream_lua_pcre_malloc_init(ngx_pool_t *pool);
void ngx_stream_lua_pcre_malloc_done(ngx_pool_t *old_pool);

#if (NGX_PCRE2)
void *ngx_stream_lua_pcre_malloc(size_t size, void *data);
void ngx_stream_lua_pcre_free(void *ptr, void *data);
#endif
#endif


#endif /* _NGX_STREAM_LUA_PCREFIX_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
