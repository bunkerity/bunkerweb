
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_ctx.c.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_util.h"
#include "ngx_stream_lua_ssl.h"
#include "ngx_stream_lua_ctx.h"


typedef struct {
    int              ref;
    lua_State       *vm;
} ngx_stream_lua_ngx_ctx_cleanup_data_t;


static ngx_int_t ngx_stream_lua_ngx_ctx_add_cleanup(ngx_stream_lua_request_t *r,
    ngx_pool_t *pool, int ref);
static void ngx_stream_lua_ngx_ctx_cleanup(void *data);


int
ngx_stream_lua_ngx_set_ctx_helper(lua_State *L, ngx_stream_lua_request_t *r,
    ngx_stream_lua_ctx_t *ctx, int index)
{
    ngx_pool_t              *pool;

    if (index < 0) {
        index = lua_gettop(L) + index + 1;
    }

    if (ctx->ctx_ref == LUA_NOREF) {
        ngx_log_debug0(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                       "lua create ngx.ctx table for the current request");

        lua_pushliteral(L, ngx_stream_lua_ctx_tables_key);
        lua_rawget(L, LUA_REGISTRYINDEX);
        lua_pushvalue(L, index);
        ctx->ctx_ref = luaL_ref(L, -2);
        lua_pop(L, 1);

        pool = r->pool;
        if (ngx_stream_lua_ngx_ctx_add_cleanup(r, pool, ctx->ctx_ref) != NGX_OK) {
            return luaL_error(L, "no memory");
        }

        return 0;
    }

    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "lua fetching existing ngx.ctx table for the current "
                   "request");

    lua_pushliteral(L, ngx_stream_lua_ctx_tables_key);
    lua_rawget(L, LUA_REGISTRYINDEX);
    luaL_unref(L, -1, ctx->ctx_ref);
    lua_pushvalue(L, index);
    ctx->ctx_ref = luaL_ref(L, -2);
    lua_pop(L, 1);

    return 0;
}


int
ngx_stream_lua_ffi_get_ctx_ref(ngx_stream_lua_request_t *r, int *in_ssl_phase,
    int *ssl_ctx_ref)
{
    ngx_stream_lua_ctx_t                    *ctx;
#if (NGX_STREAM_SSL)
    ngx_stream_lua_ssl_ctx_t                *ssl_ctx;
#endif

    ctx = ngx_stream_lua_get_module_ctx(r, ngx_stream_lua_module);
    if (ctx == NULL) {
        return NGX_STREAM_LUA_FFI_NO_REQ_CTX;
    }

    if (ctx->ctx_ref >= 0 || in_ssl_phase == NULL) {
        return ctx->ctx_ref;
    }

    *in_ssl_phase = ctx->context & (NGX_STREAM_LUA_CONTEXT_SSL_CERT
                                    | NGX_STREAM_LUA_CONTEXT_SSL_CLIENT_HELLO);
    *ssl_ctx_ref = LUA_NOREF;

#if (NGX_STREAM_SSL)
    if (r->connection->ssl != NULL) {
        ssl_ctx = ngx_stream_lua_ssl_get_ctx(r->connection->ssl->connection);

        if (ssl_ctx != NULL) {
            *ssl_ctx_ref = ssl_ctx->ctx_ref;
        }
    }
#endif

    return LUA_NOREF;
}


int
ngx_stream_lua_ffi_set_ctx_ref(ngx_stream_lua_request_t *r, int ref)
{
    ngx_pool_t                      *pool;
    ngx_stream_lua_ctx_t            *ctx;
#if (NGX_STREAM_SSL)
    ngx_connection_t                *c;
    ngx_stream_lua_ssl_ctx_t        *ssl_ctx;
#endif

    ctx = ngx_stream_lua_get_module_ctx(r, ngx_stream_lua_module);
    if (ctx == NULL) {
        return NGX_STREAM_LUA_FFI_NO_REQ_CTX;
    }

#if (NGX_STREAM_SSL)
    if (ctx->context & (NGX_STREAM_LUA_CONTEXT_SSL_CERT
                        | NGX_STREAM_LUA_CONTEXT_SSL_CLIENT_HELLO))
    {
        ssl_ctx = ngx_stream_lua_ssl_get_ctx(r->connection->ssl->connection);
        if (ssl_ctx == NULL) {
            return NGX_ERROR;
        }

        ssl_ctx->ctx_ref = ref;
        c = ngx_ssl_get_connection(r->connection->ssl->connection);
        pool = c->pool;

    } else {
        pool = r->pool;
    }

#else
    pool = r->pool;
#endif

    ctx->ctx_ref = ref;

    if (ngx_stream_lua_ngx_ctx_add_cleanup(r, pool, ref) != NGX_OK) {
        return NGX_ERROR;
    }

    return NGX_OK;
}


static ngx_int_t
ngx_stream_lua_ngx_ctx_add_cleanup(ngx_stream_lua_request_t *r, ngx_pool_t *pool,
    int ref)
{
    lua_State                   *L;
    ngx_pool_cleanup_t          *cln;

    ngx_stream_lua_ctx_t                           *ctx;
    ngx_stream_lua_ngx_ctx_cleanup_data_t          *data;

    ctx = ngx_stream_lua_get_module_ctx(r, ngx_stream_lua_module);
    L = ngx_stream_lua_get_lua_vm(r, ctx);

    cln = ngx_pool_cleanup_add(pool,
                               sizeof(ngx_stream_lua_ngx_ctx_cleanup_data_t));
    if (cln == NULL) {
        return NGX_ERROR;
    }

    cln->handler = ngx_stream_lua_ngx_ctx_cleanup;

    data = cln->data;
    data->vm = L;
    data->ref = ref;

    return NGX_OK;
}


static void
ngx_stream_lua_ngx_ctx_cleanup(void *data)
{
    lua_State       *L;

    ngx_stream_lua_ngx_ctx_cleanup_data_t          *clndata = data;

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, ngx_cycle->log, 0,
                   "lua release ngx.ctx at ref %d", clndata->ref);

    L = clndata->vm;

    lua_pushliteral(L, ngx_stream_lua_ctx_tables_key);
    lua_rawget(L, LUA_REGISTRYINDEX);
    luaL_unref(L, -1, clndata->ref);
    lua_pop(L, 1);
}


/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
