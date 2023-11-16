
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_time.c.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_common.h"


double
ngx_stream_lua_ffi_now(void)
{
    ngx_time_t              *tp;

    tp = ngx_timeofday();

    return tp->sec + tp->msec / 1000.0;
}


double
ngx_stream_lua_ffi_req_start_time(ngx_stream_lua_request_t *r)
{
    return r->session->start_sec + r->session->start_msec / 1000.0;
}


long
ngx_stream_lua_ffi_time(void)
{
    return (long) ngx_time();
}


long
ngx_stream_lua_ffi_monotonic_msec(void)
{
    return (long) ngx_current_msec;
}


void
ngx_stream_lua_ffi_update_time(void)
{
    ngx_time_update();
}


void
ngx_stream_lua_ffi_today(u_char *buf)
{
    ngx_tm_t                 tm;

    ngx_gmtime(ngx_time() + ngx_cached_time->gmtoff * 60, &tm);

    ngx_sprintf(buf, "%04d-%02d-%02d", tm.ngx_tm_year, tm.ngx_tm_mon,
                tm.ngx_tm_mday);
}


void
ngx_stream_lua_ffi_localtime(u_char *buf)
{
    ngx_tm_t                 tm;

    ngx_gmtime(ngx_time() + ngx_cached_time->gmtoff * 60, &tm);

    ngx_sprintf(buf, "%04d-%02d-%02d %02d:%02d:%02d", tm.ngx_tm_year,
                tm.ngx_tm_mon, tm.ngx_tm_mday, tm.ngx_tm_hour, tm.ngx_tm_min,
                tm.ngx_tm_sec);
}


void
ngx_stream_lua_ffi_utctime(u_char *buf)
{
    ngx_tm_t       tm;

    ngx_gmtime(ngx_time(), &tm);

    ngx_sprintf(buf, "%04d-%02d-%02d %02d:%02d:%02d", tm.ngx_tm_year,
                tm.ngx_tm_mon, tm.ngx_tm_mday, tm.ngx_tm_hour, tm.ngx_tm_min,
                tm.ngx_tm_sec);
}




/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
