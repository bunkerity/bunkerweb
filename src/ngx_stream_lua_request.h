
/*
 * Copyright (C) OpenResty Inc.
 */


#ifndef _NGX_STREAM_LUA_REQUEST_H_INCLUDED_
#define _NGX_STREAM_LUA_REQUEST_H_INCLUDED_


typedef void (*ngx_stream_lua_cleanup_pt)(void *data);

typedef struct ngx_stream_lua_cleanup_s  ngx_stream_lua_cleanup_t;

struct ngx_stream_lua_cleanup_s {
    ngx_stream_lua_cleanup_pt               handler;
    void                                   *data;
    ngx_stream_lua_cleanup_t               *next;
};


typedef struct ngx_stream_lua_request_s  ngx_stream_lua_request_t;

typedef void (*ngx_stream_lua_event_handler_pt)(ngx_stream_lua_request_t *r);


struct ngx_stream_lua_request_s {
    ngx_connection_t                     *connection;
    ngx_stream_session_t                 *session;
    ngx_pool_t                           *pool;
    ngx_stream_lua_cleanup_t             *cleanup;

    ngx_stream_lua_event_handler_pt       read_event_handler;
    ngx_stream_lua_event_handler_pt       write_event_handler;
};


void ngx_stream_lua_empty_handler(ngx_event_t *wev);
void ngx_stream_lua_request_handler(ngx_event_t *ev);
void ngx_stream_lua_block_reading(ngx_stream_lua_request_t *r);

ngx_stream_lua_cleanup_t *
ngx_stream_lua_cleanup_add(ngx_stream_lua_request_t *r, size_t size);

ngx_stream_lua_request_t *
ngx_stream_lua_create_request(ngx_stream_session_t *s);
void ngx_stream_lua_finalize_real_request(ngx_stream_lua_request_t *r,
    ngx_int_t rc);
void ngx_stream_lua_core_run_phases(ngx_stream_lua_request_t *r);


typedef ngx_int_t (*ngx_stream_lua_handler_pt)(ngx_stream_lua_request_t *r);


#define ngx_stream_lua_get_module_ctx(r, module)                             \
    ngx_stream_get_module_ctx((r)->session, module)
#define ngx_stream_lua_set_ctx(r, c, module)                                 \
    ngx_stream_set_ctx((r)->session, c, module)
#define ngx_stream_lua_get_module_main_conf(r, module)                       \
    ngx_stream_get_module_main_conf((r)->session, module)
#define ngx_stream_lua_get_module_srv_conf(r, module)                        \
    ngx_stream_get_module_srv_conf((r)->session, module)
#define ngx_stream_lua_get_module_loc_conf                                   \
    ngx_stream_lua_get_module_srv_conf


#endif /* _NGX_STREAM_LUA_REQUEST_H_INCLUDED_ */
