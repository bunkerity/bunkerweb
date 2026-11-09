/*
 * Copyright (C) Alex Zhang
 */


#include "ngx_http_zstd_filter_module.h"

#include "../ngx_http_zstd_accept_encoding.h"


static ngx_http_output_header_filter_pt  ngx_http_next_header_filter;
static ngx_http_output_body_filter_pt  ngx_http_next_body_filter;


static ngx_int_t ngx_http_zstd_header_filter(ngx_http_request_t *r);
static ngx_int_t ngx_http_zstd_body_filter(ngx_http_request_t *r,
    ngx_chain_t *in);
static ngx_int_t ngx_http_zstd_filter_add_data(ngx_http_request_t *r,
    ngx_http_zstd_ctx_t *ctx);
static ngx_int_t ngx_http_zstd_filter_get_buf(ngx_http_request_t *r,
    ngx_http_zstd_ctx_t *ctx);
static ZSTD_CStream *ngx_http_zstd_filter_create_cstream(ngx_http_request_t *r,
    ngx_http_zstd_ctx_t *ctx);
static ngx_int_t ngx_http_zstd_filter_compress(ngx_http_request_t *r,
    ngx_http_zstd_ctx_t *ctx);
static ngx_int_t ngx_http_zstd_ok(ngx_http_request_t *r);
static void *ngx_http_zstd_filter_alloc(void *opaque, size_t size);
static void ngx_http_zstd_filter_free(void *opaque, void *address);


static ngx_int_t
ngx_http_zstd_header_filter(ngx_http_request_t *r)
{
    ngx_table_elt_t           *h;
    ngx_http_zstd_loc_conf_t  *zlcf;
    ngx_http_zstd_ctx_t       *ctx;

    zlcf = ngx_http_get_module_loc_conf(r, ngx_http_zstd_filter_module);

    if (!zlcf->enable
        || r->headers_out.status < NGX_HTTP_OK
        || r->headers_out.status == NGX_HTTP_NO_CONTENT
        || r->headers_out.status == 205
        || r->headers_out.status == NGX_HTTP_PARTIAL_CONTENT
        || (r->headers_out.status > 299
            && r->headers_out.status != NGX_HTTP_FORBIDDEN
            && r->headers_out.status != NGX_HTTP_NOT_FOUND)
       || (r->headers_out.content_encoding
           && r->headers_out.content_encoding->value.len)
       || (r->headers_out.content_length_n != -1
           && r->headers_out.content_length_n < zlcf->min_length)
       || ngx_http_test_content_type(r, &zlcf->types) == NULL
       || r->header_only)
    {
        return ngx_http_next_header_filter(r);
    }

    if (ngx_http_zstd_vary_accept_encoding(r) != NGX_OK) {
        return NGX_ERROR;
    }

    if (ngx_http_zstd_ok(r) != NGX_OK) {
        return ngx_http_next_header_filter(r);
    }

    /*
     * We are committed to compressing this response, so suppress gzip for it.
     * ngx_http_zstd_ok() deliberately leaves these flags alone: a request it
     * declines must stay eligible for gzip.
     */

    r->gzip_tested = 1;
    r->gzip_ok = 0;

    ctx = ngx_pcalloc(r->pool, sizeof(ngx_http_zstd_ctx_t));
    if (ctx == NULL) {
        return NGX_ERROR;
    }

    ngx_http_set_ctx(r, ctx, ngx_http_zstd_filter_module);

    ctx->request = r;
    ctx->last_out = &ctx->out;

    h = ngx_list_push(&r->headers_out.headers);
    if (h == NULL) {
        return NGX_ERROR;
    }

    h->hash = 1;
#if (nginx_version >= 1023000)
    h->next = NULL;
#endif
    ngx_str_set(&h->key, "Content-Encoding");
    ngx_str_set(&h->value, "zstd");
    r->headers_out.content_encoding = h;

    r->main_filter_need_in_memory = 1;

    ngx_http_clear_content_length(r);
    ngx_http_clear_accept_ranges(r);
    ngx_http_weak_etag(r);

    return ngx_http_next_header_filter(r);
}


static ngx_int_t
ngx_http_zstd_body_filter(ngx_http_request_t *r, ngx_chain_t *in)
{
    size_t                rv;
    ngx_int_t             flush, rc;
    ngx_chain_t          *cl;
    ngx_http_zstd_ctx_t  *ctx;


    ctx = ngx_http_get_module_ctx(r, ngx_http_zstd_filter_module);

    if (ctx == NULL || ctx->done || r->header_only) {
        return ngx_http_next_body_filter(r, in);
    }

    ngx_log_debug0(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "http zstd filter");

    if (ctx->cstream == NULL) {
        ctx->cstream = ngx_http_zstd_filter_create_cstream(r, ctx);
        if (ctx->cstream == NULL) {
            goto failed;
        }
    }

    if (in) {
        if (ngx_chain_add_copy(r->pool, &ctx->in, in) != NGX_OK) {
            goto failed;
        }

        r->connection->buffered |= NGX_HTTP_GZIP_BUFFERED;
    }

    if (ctx->nomem) {

        /* flush busy buffers */

        if (ngx_http_next_body_filter(r, NULL) == NGX_ERROR) {
            goto failed;
        }

        cl = NULL;

        ngx_chain_update_chains(r->pool, &ctx->free, &ctx->busy, &cl,
                                (ngx_buf_tag_t) &ngx_http_zstd_filter_module);

        flush = 0;
        ctx->nomem = 0;

    } else {
        flush = ctx->busy ? 1 : 0;
    }

    for ( ;; ) {

        /* cycle while we can write to a client */

        for ( ;; ) {

            rc = ngx_http_zstd_filter_add_data(r, ctx);

            if (rc == NGX_DECLINED) {
                break;
            }

            if (rc == NGX_AGAIN) {
                continue;
            }

            rc = ngx_http_zstd_filter_get_buf(r, ctx);

            if (rc == NGX_ERROR) {
                goto failed;
            }

            if (rc == NGX_DECLINED) {
                break;
            }

            rc = ngx_http_zstd_filter_compress(r, ctx);

            if (rc == NGX_ERROR) {
                goto failed;
            }

            if (rc == NGX_OK) {
                break;
            }

            /* rc == NGX_AGAIN */
        }

        if (ctx->out == NULL && !flush) {
            return ctx->busy ? NGX_AGAIN : NGX_OK;
        }

        rc = ngx_http_next_body_filter(r, ctx->out);

        if (rc == NGX_ERROR) {
            goto failed;
        }

        ngx_chain_update_chains(r->pool, &ctx->free, &ctx->busy, &ctx->out,
                                (ngx_buf_tag_t) &ngx_http_zstd_filter_module);

        ctx->last_out = &ctx->out;
        ctx->nomem = 0;
        flush = 0;

        if (ctx->done) {
            rv = ZSTD_freeCStream(ctx->cstream);
            if (ZSTD_isError(rv)) {
                ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                              "ZSTD_freeCStream() failed: %s",
                              ZSTD_getErrorName(rv));

                rc = NGX_ERROR;
            }

            ctx->cstream = NULL;

            return rc;
        }
    }

failed:

    ctx->done = 1;

    if (ctx->cstream) {
        rv = ZSTD_freeCStream(ctx->cstream);
        if (ZSTD_isError(rv)) {
            ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                          "ZSTD_freeCStream() failed: %s",
                          ZSTD_getErrorName(rv));
        }

        ctx->cstream = NULL;
    }

    return NGX_ERROR;
}


static ngx_int_t
ngx_http_zstd_filter_compress(ngx_http_request_t *r, ngx_http_zstd_ctx_t *ctx)
{
    size_t             rc, pos_in, pos_out;
    ngx_uint_t         flushed, last;
    ZSTD_EndDirective  directive;
    ngx_chain_t       *cl;
    ngx_buf_t         *b;

    ngx_log_debug8(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "zstd compress in: src:%p pos:%ud size: %ud, "
                   "dst:%p pos:%ud size:%ud flush:%d redo:%d",
                   ctx->buffer_in.src, ctx->buffer_in.pos, ctx->buffer_in.size,
                   ctx->buffer_out.dst, ctx->buffer_out.pos,
                   ctx->buffer_out.size, ctx->flush, ctx->redo);

    pos_in = ctx->buffer_in.pos;
    pos_out = ctx->buffer_out.pos;

    switch (ctx->action) {
    case NGX_HTTP_ZSTD_FILTER_END:
        directive = ZSTD_e_end;
        break;
    case NGX_HTTP_ZSTD_FILTER_FLUSH:
        directive = ZSTD_e_flush;
        break;
    default:
        directive = ctx->flush ? ZSTD_e_flush : ZSTD_e_continue;
        break;
    }

    rc = ZSTD_compressStream2(ctx->cstream, &ctx->buffer_out,
                              &ctx->buffer_in, directive);

    if (ZSTD_isError(rc)) {
        ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                      "ZSTD_compressStream2() failed: %s",
                      ZSTD_getErrorName(rc));

        return NGX_ERROR;
    }

    ngx_log_debug6(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "zstd compress out: src:%p pos:%ud size: %ud, "
                   "dst:%p pos:%ud size:%ud",
                   ctx->buffer_in.src, ctx->buffer_in.pos, ctx->buffer_in.size,
                   ctx->buffer_out.dst, ctx->buffer_out.pos,
                   ctx->buffer_out.size);

    if (ctx->buffer_in.pos != pos_in) {
        ctx->in_buf->pos += ctx->buffer_in.pos - pos_in;
    }

    if (ctx->buffer_out.pos != pos_out) {
        ctx->out_buf->last += ctx->buffer_out.pos - pos_out;
    }

    ctx->redo = 0;

    if (rc > 0) {
        if (ctx->action == NGX_HTTP_ZSTD_FILTER_COMPRESS) {
            ctx->action = NGX_HTTP_ZSTD_FILTER_FLUSH;
        }

        ctx->redo = 1;

    } else if (ctx->last && ctx->action != NGX_HTTP_ZSTD_FILTER_END
               && ctx->buffer_in.pos >= ctx->buffer_in.size
               && ctx->in == NULL)
    {
        ctx->action = NGX_HTTP_ZSTD_FILTER_END;
        ctx->redo = 1;

        if (ctx->buffer_out.pos - pos_out == 0) {
            return NGX_AGAIN;
        }

    } else if (ctx->action != NGX_HTTP_ZSTD_FILTER_END) {
        ctx->action = NGX_HTTP_ZSTD_FILTER_COMPRESS;
    }

    last = (rc == 0 && ctx->last && directive == ZSTD_e_end);
    flushed = (rc == 0 && ctx->flush);

    if (ngx_buf_size(ctx->out_buf) == 0 && !last) {
        if (flushed) {
            r->connection->buffered &= ~NGX_HTTP_GZIP_BUFFERED;
            ctx->flush = 0;
        }

        return NGX_AGAIN;
    }

    cl = ngx_alloc_chain_link(r->pool);
    if (cl == NULL) {
        return NGX_ERROR;
    }

    b = ctx->out_buf;

    if (last || flushed) {
        r->connection->buffered &= ~NGX_HTTP_GZIP_BUFFERED;

        b->flush = flushed && !ctx->last;
        b->last_buf = last;

        ctx->done = last;
        ctx->flush = 0;
    }

    if (ngx_buf_size(b) == 0) {
        b->temporary = 0;
        b->recycled = 0;
    }

    ctx->bytes_out += ngx_buf_size(b);

    cl->next = NULL;
    cl->buf = b;

    *ctx->last_out = cl;
    ctx->last_out = &cl->next;

    ngx_memzero(&ctx->buffer_out, sizeof(ZSTD_outBuffer));

    return last ? NGX_OK : NGX_AGAIN;
}


static ngx_int_t
ngx_http_zstd_filter_add_data(ngx_http_request_t *r, ngx_http_zstd_ctx_t *ctx)
{
    if (ctx->buffer_in.pos < ctx->buffer_in.size
        || ctx->flush
        || ctx->last
        || ctx->redo)
    {
        return NGX_OK;
    }

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "zstd in: %p", ctx->in);

    if (ctx->in == NULL) {
        return NGX_DECLINED;
    }

    ctx->in_buf = ctx->in->buf;
    ctx->in = ctx->in->next;

    if (ctx->in_buf->last_buf) {
        ctx->last = 1;

    } else if (ctx->in_buf->flush) {
        ctx->flush = 1;
    }

    ctx->buffer_in.src = ctx->in_buf->pos;
    ctx->buffer_in.pos = 0;
    ctx->buffer_in.size = ngx_buf_size(ctx->in_buf);

    ctx->bytes_in += ngx_buf_size(ctx->in_buf);

    if (ctx->buffer_in.size == 0) {
        return (ctx->last || ctx->flush) ? NGX_OK : NGX_AGAIN;
    }

    return NGX_OK;
}


static ngx_int_t
ngx_http_zstd_filter_get_buf(ngx_http_request_t *r, ngx_http_zstd_ctx_t *ctx)
{
    ngx_chain_t               *cl;
    ngx_http_zstd_loc_conf_t  *zlcf;

    if (ctx->buffer_out.pos < ctx->buffer_out.size) {
        return NGX_OK;
    }

    zlcf = ngx_http_get_module_loc_conf(r, ngx_http_zstd_filter_module);

    if (ctx->free) {
        cl = ctx->free;
        ctx->free = ctx->free->next;
        ctx->out_buf = cl->buf;
        ngx_free_chain(r->pool, cl);

        /*
         * ngx_chain_update_chains() rewinds pos and last for us, but it leaves
         * the control flags alone, and a buffer comes back round still carrying
         * whatever it was sent with. ngx_http_zstd_filter_compress() only
         * assigns flush and last_buf on the branch where the frame ends, so a
         * stale flag would be re-emitted on an unrelated buffer and mark the
         * response complete early.
         */

        ctx->out_buf->flush = 0;
        ctx->out_buf->sync = 0;
        ctx->out_buf->last_buf = 0;
        ctx->out_buf->last_in_chain = 0;
        ctx->out_buf->shadow = NULL;

    } else if (ctx->bufs < zlcf->bufs.num) {
        ctx->out_buf = ngx_create_temp_buf(r->pool, zlcf->bufs.size);
        if (ctx->out_buf == NULL) {
            return NGX_ERROR;
        }

        ctx->out_buf->tag = (ngx_buf_tag_t) &ngx_http_zstd_filter_module;
        ctx->out_buf->recycled = 1;
        ctx->bufs++;

    } else {
        ctx->nomem = 1;
        return NGX_DECLINED;
    }

    ctx->buffer_out.dst = ctx->out_buf->pos;
    ctx->buffer_out.pos = 0;
    ctx->buffer_out.size = ctx->out_buf->end - ctx->out_buf->start;

    return NGX_OK;
}


static ZSTD_CStream *
ngx_http_zstd_filter_create_cstream(ngx_http_request_t *r,
    ngx_http_zstd_ctx_t *ctx)
{
    size_t                      rc;
    ZSTD_CStream               *cstream;
    ZSTD_customMem              cmem;
    ngx_http_zstd_loc_conf_t   *zlcf;

    zlcf = ngx_http_get_module_loc_conf(r, ngx_http_zstd_filter_module);

    cmem.customAlloc = ngx_http_zstd_filter_alloc;
    cmem.customFree = ngx_http_zstd_filter_free;
    cmem.opaque = ctx;

    cstream = ZSTD_createCStream_advanced(cmem);
    if (cstream == NULL) {
        ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                      "ZSTD_createCStream_advanced() failed");

        return NULL;
    }

    /* TODO use the advanced initialize functions */

    if (zlcf->dict) {
#if ZSTD_VERSION_NUMBER >= 10500
        rc = ZSTD_CCtx_reset(cstream, ZSTD_reset_session_only);
        if (ZSTD_isError(rc)) {
            ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                          "ZSTD_CCtx_reset() failed: %s",
                          ZSTD_getErrorName(rc));
            goto failed;
        }

        rc = ZSTD_CCtx_refCDict(cstream, zlcf->dict);
        if (ZSTD_isError(rc)) {
            ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                          "ZSTD_CCtx_refCDict() failed: %s",
                          ZSTD_getErrorName(rc));
            goto failed;
        }
#else
        rc = ZSTD_initCStream_usingCDict(cstream, zlcf->dict);
#endif
        if (ZSTD_isError(rc)) {
            ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                          "ZSTD_initCStream_usingCDict() failed: %s",
                          ZSTD_getErrorName(rc));

            goto failed;
        }

    } else {
        rc = ZSTD_initCStream(cstream, zlcf->level);
        if (ZSTD_isError(rc)) {
            ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                          "ZSTD_initCStream() failed: %s",
                          ZSTD_getErrorName(rc));

            goto failed;
        }
    }

    return cstream;

failed:
    rc = ZSTD_freeCStream(cstream);
    if (ZSTD_isError(rc)) {
        ngx_log_error(NGX_LOG_ALERT, r->connection->log, 0,
                      "ZSTD_freeCStream() failed: %s", ZSTD_getErrorName(rc));
    }

    return NULL;
}


static ngx_int_t
ngx_http_zstd_ok(ngx_http_request_t *r)
{
    ngx_table_elt_t  *ae;

    if (r != r->main) {
        return NGX_DECLINED;
    }

    ae = r->headers_in.accept_encoding;
    if (ae == NULL) {
        return NGX_DECLINED;
    }

    return ngx_http_zstd_accept_encoding(&ae->value);
}


ngx_int_t
ngx_http_zstd_filter_init(ngx_conf_t *cf)
{
    ngx_http_next_header_filter = ngx_http_top_header_filter;
    ngx_http_top_header_filter = ngx_http_zstd_header_filter;

    ngx_http_next_body_filter = ngx_http_top_body_filter;
    ngx_http_top_body_filter = ngx_http_zstd_body_filter;

    return NGX_OK;
}


static void *
ngx_http_zstd_filter_alloc(void *opaque, size_t size)
{
    ngx_http_zstd_ctx_t *ctx = opaque;

    void  *p;

    p = ngx_palloc(ctx->request->pool, size);

    ngx_log_debug2(NGX_LOG_DEBUG_HTTP, ctx->request->connection->log, 0,
                   "zstd alloc: %p, size: %uz", p, size);

    return p;
}


static void
ngx_http_zstd_filter_free(void *opaque, void *address)
{
#if (NGX_DEBUG)

    ngx_http_zstd_ctx_t *ctx = opaque;

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, ctx->request->connection->log, 0,
                   "zstd free: %p", address);

#endif
}
