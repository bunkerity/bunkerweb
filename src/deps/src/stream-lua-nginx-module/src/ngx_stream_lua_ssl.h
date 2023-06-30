
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_ssl.h.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_SSL_H_INCLUDED_
#define _NGX_STREAM_LUA_SSL_H_INCLUDED_


#include "ngx_stream_lua_common.h"


#if (NGX_STREAM_SSL)


typedef struct {
    ngx_connection_t            *connection; /* original true connection */
    ngx_stream_lua_request_t    *request;    /* fake request */
    ngx_pool_cleanup_pt         *cleanup;

    ngx_ssl_session_t       *session;    /* retrurn value for openssl's
                                          * session_get_cb */

    ngx_str_t                session_id;

    int                      exit_code;  /* exit code for openssl's
                                            set_client_hello_cb or
                                            set_cert_cb callback */

    int                      ctx_ref;    /* reference to anchor
                                            request ctx data in lua
                                            registry */

    unsigned                 done:1;
    unsigned                 aborted:1;

    unsigned                 entered_client_hello_handler:1;
    unsigned                 entered_cert_handler:1;
    unsigned                 entered_sess_fetch_handler:1;
} ngx_stream_lua_ssl_ctx_t;


ngx_int_t ngx_stream_lua_ssl_init(ngx_log_t *log);


extern int ngx_stream_lua_ssl_ctx_index;


#endif


#endif  /* _NGX_STREAM_LUA_SSL_H_INCLUDED_ */
