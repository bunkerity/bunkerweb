
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_ssl.c.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#if (NGX_STREAM_SSL)

#include "ngx_stream_lua_ssl.h"


int ngx_stream_lua_ssl_ctx_index = -1;
int ngx_stream_lua_ssl_key_log_index = -1;


ngx_int_t
ngx_stream_lua_ssl_init(ngx_log_t *log)
{
    if (ngx_stream_lua_ssl_ctx_index == -1) {
        ngx_stream_lua_ssl_ctx_index = SSL_get_ex_new_index(0, NULL,
                                                            NULL,
                                                            NULL,
                                                            NULL);

        if (ngx_stream_lua_ssl_ctx_index == -1) {
            ngx_ssl_error(NGX_LOG_ALERT, log, 0,
                          "lua: SSL_get_ex_new_index() for ctx failed");
            return NGX_ERROR;
        }
    }

    if (ngx_stream_lua_ssl_key_log_index == -1) {
        ngx_stream_lua_ssl_key_log_index = SSL_get_ex_new_index(0, NULL,
                                                                NULL,
                                                                NULL,
                                                                NULL);

        if (ngx_stream_lua_ssl_key_log_index == -1) {
            ngx_ssl_error(NGX_LOG_ALERT, log, 0,
                          "lua: SSL_get_ex_new_index() for key log failed");
            return NGX_ERROR;
        }
    }

    return NGX_OK;
}


ngx_ssl_conn_t *
ngx_stream_lua_ffi_get_upstream_ssl_pointer(ngx_stream_lua_request_t *r,
    const char **err)
{
    ngx_connection_t  *c;

    if (r == NULL || r->connection == NULL || r->session == NULL) {
        *err = "bad request";
        return NULL;
    }

    if (r->session->upstream == NULL
        || r->session->upstream->peer.connection == NULL)
    {
        *err = "not upstream";
        return NULL;
    }

    c = r->session->upstream->peer.connection;

    if (c->ssl == NULL || c->ssl->connection == NULL) {
        *err = "not ssl connection";
        return NULL;
    }

    return c->ssl->connection;
}


#endif /* NGX_STREAM_SSL */
