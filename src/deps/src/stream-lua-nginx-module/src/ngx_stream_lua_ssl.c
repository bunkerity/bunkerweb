
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


int ngx_stream_lua_ssl_ctx_index = -1;


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

    return NGX_OK;
}


#endif /* NGX_STREAM_SSL */
