
/*
 * Copyright (C) OpenResty Inc.
 */


#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_stream.h>
#include "ddebug.h"
#include "ngx_stream_lua_common.h"
#include "ngx_stream_lua_request.h"
#include "ngx_stream_lua_contentby.h"


static ngx_int_t ngx_stream_lua_set_write_handler(ngx_stream_lua_request_t *r);
static void ngx_stream_lua_writer(ngx_stream_lua_request_t *r);
static void ngx_stream_lua_request_cleanup(void *data);


ngx_stream_lua_cleanup_t *
ngx_stream_lua_cleanup_add(ngx_stream_lua_request_t *r, size_t size)
{
    ngx_stream_lua_cleanup_t    *cln;
    ngx_stream_lua_ctx_t        *ctx;

    if (size == 0) {
        ctx = ngx_stream_lua_get_module_ctx(r, ngx_stream_lua_module);

        if (ctx != NULL && ctx->free_cleanup) {
            cln = ctx->free_cleanup;
            ctx->free_cleanup = cln->next;

            dd("reuse cleanup: %p", cln);

            ngx_log_debug1(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                           "lua stream cleanup reuse: %p", cln);

            cln->handler = NULL;
            cln->next = r->cleanup;

            r->cleanup = cln;

            return cln;
        }
    }

    cln = ngx_palloc(r->pool, sizeof(ngx_stream_lua_cleanup_t));
    if (cln == NULL) {
        return NULL;
    }

    if (size) {
        cln->data = ngx_palloc(r->pool, size);
        if (cln->data == NULL) {
            return NULL;
        }

    } else {
        cln->data = NULL;
    }

    cln->handler = NULL;
    cln->next = r->cleanup;

    r->cleanup = cln;

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "stream cleanup add: %p", cln);

    return cln;
}


static void
ngx_stream_lua_request_cleanup(void *data)
{
    ngx_stream_lua_request_t    *r = data;
    ngx_stream_lua_cleanup_t    *cln;

    cln = r->cleanup;
    r->cleanup = NULL;

    while (cln) {
        if (cln->handler) {
            cln->handler(cln->data);
        }

        cln = cln->next;
    }
}


ngx_stream_lua_request_t *
ngx_stream_lua_create_request(ngx_stream_session_t *s)
{
    ngx_pool_t                  *pool;
    ngx_stream_lua_request_t    *r;
    ngx_pool_cleanup_t          *cln;

#if 0
    pool = ngx_create_pool(NGX_DEFAULT_POOL_SIZE, s->connection->log);
    if (pool == NULL) {
        return NULL;
    }
#endif

    pool = s->connection->pool;

    r = ngx_pcalloc(pool, sizeof(ngx_stream_lua_request_t));
    if (r == NULL) {
        return NULL;
    }

    r->connection = s->connection;
    r->session = s;
    r->pool = pool;

    cln = ngx_pool_cleanup_add(pool, 0);
    if (cln == NULL) {
        return NULL;
    }

    cln->handler = ngx_stream_lua_request_cleanup;
    cln->data = r;

    return r;
}


void
ngx_stream_lua_request_handler(ngx_event_t *ev)
{
    ngx_connection_t          *c;
    ngx_stream_session_t      *s;
    ngx_stream_lua_request_t  *r;
    ngx_stream_lua_ctx_t      *ctx;

    c = ev->data;
    s = c->data;

    if (ev->delayed && ev->timedout) {
        ev->delayed = 0;
        ev->timedout = 0;
    }

    ctx = ngx_stream_get_module_ctx(s, ngx_stream_lua_module);
    if (ctx == NULL) {
        return;
    }

    r = ctx->request;

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, c->log, 0,
                   "session run request: \"%p\"", r);

    if (ev->write) {
        r->write_event_handler(r);

    } else {
        r->read_event_handler(r);
    }
}


void
ngx_stream_lua_empty_handler(ngx_event_t *wev)
{
    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, wev->log, 0,
                   "stream lua empty handler");
    return;
}


void
ngx_stream_lua_block_reading(ngx_stream_lua_request_t *r)
{
    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "stream reading blocked");

    /* aio does not call this handler */

    if ((ngx_event_flags & NGX_USE_LEVEL_EVENT)
        && r->connection->read->active)
    {
        if (ngx_del_event(r->connection->read, NGX_READ_EVENT, 0) != NGX_OK) {
            ngx_stream_lua_finalize_real_request(r,
                                              NGX_STREAM_INTERNAL_SERVER_ERROR);
        }
    }
}


void
ngx_stream_lua_finalize_real_request(ngx_stream_lua_request_t *r, ngx_int_t rc)
{
#if 0
    ngx_pool_t                *pool;
#endif
    ngx_stream_session_t      *s;

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "finalize stream request: %i", rc);

    s = r->session;

    if (rc == NGX_ERROR) {
        rc = NGX_STREAM_INTERNAL_SERVER_ERROR;
    }

    if (rc == NGX_DECLINED || rc == NGX_STREAM_INTERNAL_SERVER_ERROR) {
        goto done;
    }

    if (rc == NGX_DONE) {
        return;
    }

    if (rc == NGX_OK) {
        rc = NGX_STREAM_OK;
    }

    if (r->connection->buffered) {
        if (ngx_stream_lua_set_write_handler(r) != NGX_OK) {
            goto done;
        }

        return;
    }

done:

#if 0
    pool = r->pool;
    r->pool = NULL;

    ngx_destroy_pool(pool);
#endif

    ngx_stream_finalize_session(s, rc);
    return;
}


void
ngx_stream_lua_request_empty_handler(ngx_stream_lua_request_t *r)
{
    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "stream request empty handler");

    return;
}


static void
ngx_stream_lua_writer(ngx_stream_lua_request_t *r)
{
    ngx_int_t                    rc;
    ngx_event_t                 *wev;
    ngx_connection_t            *c;
    ngx_stream_lua_srv_conf_t   *lscf;

    c = r->connection;
    wev = c->write;

    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, wev->log, 0,
                   "stream writer handler");

    lscf = ngx_stream_lua_get_module_srv_conf(r, ngx_stream_lua_module);

    if (wev->timedout) {
        ngx_log_error(NGX_LOG_INFO, c->log, NGX_ETIMEDOUT,
                      "client timed out");
        c->timedout = 1;

        ngx_stream_lua_finalize_real_request(r, NGX_ERROR);
        return;
    }

    rc = ngx_stream_top_filter(r->session, NULL, 1);

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, c->log, 0,
                   "stream writer output filter: %i", rc);

    if (rc == NGX_ERROR) {
        ngx_stream_lua_finalize_real_request(r, rc);
        return;
    }

    if (c->buffered) {
        if (!wev->delayed) {
            ngx_add_timer(wev, lscf->send_timeout);
        }

        if (ngx_handle_write_event(wev, lscf->send_lowat) != NGX_OK) {
            ngx_stream_lua_finalize_real_request(r, NGX_ERROR);
        }

        return;
    }

    ngx_log_debug0(NGX_LOG_DEBUG_STREAM, wev->log, 0,
                   "stream writer done");

    r->write_event_handler = ngx_stream_lua_request_empty_handler;

    ngx_stream_lua_finalize_real_request(r, rc);
}


static ngx_int_t
ngx_stream_lua_set_write_handler(ngx_stream_lua_request_t *r)
{
    ngx_event_t                 *wev;
    ngx_stream_lua_srv_conf_t   *lscf;

    r->read_event_handler = ngx_stream_lua_request_empty_handler;
    r->write_event_handler = ngx_stream_lua_writer;

    wev = r->connection->write;

    if (wev->ready && wev->delayed) {
        return NGX_OK;
    }

    lscf = ngx_stream_lua_get_module_srv_conf(r, ngx_stream_lua_module);
    if (!wev->delayed) {
        ngx_add_timer(wev, lscf->send_timeout);
    }

    if (ngx_handle_write_event(wev, lscf->send_lowat) != NGX_OK) {
        return NGX_ERROR;
    }

    return NGX_OK;
}


void
ngx_stream_lua_core_run_phases(ngx_stream_lua_request_t *r)
{
    ngx_stream_session_t      *s;

    s = r->session;

    ngx_log_debug1(NGX_LOG_DEBUG_STREAM, r->connection->log, 0,
                   "lua session run phases: \"%p\"", r);

    ngx_stream_core_run_phases(s);
}
