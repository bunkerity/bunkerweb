
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_log_ringbuf.h.tt2
 */


#ifndef _NGX_STREAM_LUA_RINGBUF_H_INCLUDED_
#define _NGX_STREAM_LUA_RINGBUF_H_INCLUDED_


#include "ngx_stream_lua_common.h"


typedef struct {
    ngx_uint_t   filter_level;
    char        *tail;              /* writed point */
    char        *head;              /* readed point */
    char        *data;              /* buffer */
    char        *sentinel;
    size_t       size;              /* buffer total size */
    size_t       count;             /* count of logs */
} ngx_stream_lua_log_ringbuf_t;


void ngx_stream_lua_log_ringbuf_init(ngx_stream_lua_log_ringbuf_t *rb,
    void *buf, size_t len);
void ngx_stream_lua_log_ringbuf_reset(ngx_stream_lua_log_ringbuf_t *rb);
ngx_int_t ngx_stream_lua_log_ringbuf_read(ngx_stream_lua_log_ringbuf_t *rb,
    int *log_level, void **buf, size_t *n, double *log_time);
ngx_int_t ngx_stream_lua_log_ringbuf_write(ngx_stream_lua_log_ringbuf_t *rb,
    int log_level, void *buf, size_t n);


#endif /* _NGX_STREAM_LUA_RINGBUF_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
