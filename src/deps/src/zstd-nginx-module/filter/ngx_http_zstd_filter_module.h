/*
 * Copyright (C) Alex Zhang
 */

#ifndef NGX_HTTP_ZSTD_FILTER_MODULE_H
#define NGX_HTTP_ZSTD_FILTER_MODULE_H

#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

#define ZSTD_STATIC_LINKING_ONLY
#include <zstd.h>


#define NGX_HTTP_ZSTD_FILTER_COMPRESS       0
#define NGX_HTTP_ZSTD_FILTER_FLUSH          1
#define NGX_HTTP_ZSTD_FILTER_END            2


typedef struct {
    ngx_flag_t                   enable;
    ngx_int_t                    level;
    ssize_t                      min_length;

    ngx_hash_t                   types;

    ngx_bufs_t                   bufs;

    ngx_array_t                 *types_keys;

    ZSTD_CDict                  *dict;
} ngx_http_zstd_loc_conf_t;


typedef struct {
    ngx_chain_t                 *in;
    ngx_chain_t                 *free;
    ngx_chain_t                 *busy;
    ngx_chain_t                 *out;
    ngx_chain_t                **last_out;

    ngx_buf_t                   *in_buf;
    ngx_buf_t                   *out_buf;
    ngx_int_t                    bufs;

    ZSTD_inBuffer                buffer_in;
    ZSTD_outBuffer               buffer_out;

    ZSTD_CStream                *cstream;

    ngx_http_request_t          *request;

    size_t                       bytes_in;
    size_t                       bytes_out;

    unsigned                     action:2;
    unsigned                     last:1;
    unsigned                     redo:1;
    unsigned                     flush:1;
    unsigned                     done:1;
    unsigned                     nomem:1;
} ngx_http_zstd_ctx_t;


extern ngx_module_t  ngx_http_zstd_filter_module;


#if defined(__GNUC__)
__attribute__((visibility("hidden")))
#endif
ngx_int_t ngx_http_zstd_filter_init(ngx_conf_t *cf);


#endif /* NGX_HTTP_ZSTD_FILTER_MODULE_H */
