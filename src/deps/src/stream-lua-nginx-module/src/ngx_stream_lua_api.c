
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_api.c.tt2
 */


/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"

#if (NGX_LINUX)
#include <linux/netfilter_ipv4.h>
#if (NGX_HAVE_INET6)
#include <linux/netfilter_ipv6.h>
#include <linux/netfilter_ipv6/ip6_tables.h>
#endif
#endif

#include "ngx_stream_lua_common.h"
#include "api/ngx_stream_lua_api.h"
#include "ngx_stream_lua_shdict.h"
#include "ngx_stream_lua_util.h"


lua_State *
ngx_stream_lua_get_global_state(ngx_conf_t *cf)
{
    ngx_stream_lua_main_conf_t       *lmcf;

    lmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_lua_module);

    return lmcf->lua;
}


static ngx_int_t ngx_stream_lua_shared_memory_init(ngx_shm_zone_t *shm_zone,
    void *data);


ngx_int_t
ngx_stream_lua_add_package_preload(ngx_conf_t *cf, const char *package,
    lua_CFunction func)
{
    lua_State       *L;

    ngx_stream_lua_main_conf_t            *lmcf;
    ngx_stream_lua_preload_hook_t         *hook;

    lmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_lua_module);

    L = lmcf->lua;

    if (L) {
        lua_getglobal(L, "package");
        lua_getfield(L, -1, "preload");
        lua_pushcfunction(L, func);
        lua_setfield(L, -2, package);
        lua_pop(L, 2);
    }

    /* we always register preload_hooks since we always create new Lua VMs
     * when lua code cache is off. */

    if (lmcf->preload_hooks == NULL) {
        lmcf->preload_hooks =
            ngx_array_create(cf->pool, 4,
                             sizeof(ngx_stream_lua_preload_hook_t));

        if (lmcf->preload_hooks == NULL) {
            return NGX_ERROR;
        }
    }

    hook = ngx_array_push(lmcf->preload_hooks);
    if (hook == NULL) {
        return NGX_ERROR;
    }

    hook->package = (u_char *) package;
    hook->loader = func;

    return NGX_OK;
}


ngx_shm_zone_t *
ngx_stream_lua_shared_memory_add(ngx_conf_t *cf, ngx_str_t *name,
    size_t size, void *tag)
{
    ngx_stream_lua_main_conf_t           *lmcf;
    ngx_stream_lua_shm_zone_ctx_t        *ctx;

    ngx_shm_zone_t              **zp;
    ngx_shm_zone_t               *zone;
    ngx_int_t                     n;

    lmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_lua_module);
    if (lmcf == NULL) {
        return NULL;
    }

    if (lmcf->shm_zones == NULL) {
        lmcf->shm_zones = ngx_palloc(cf->pool, sizeof(ngx_array_t));
        if (lmcf->shm_zones == NULL) {
            return NULL;
        }

        if (ngx_array_init(lmcf->shm_zones, cf->pool, 2,
                           sizeof(ngx_shm_zone_t *))
            != NGX_OK)
        {
            return NULL;
        }
    }

    zone = ngx_shared_memory_add(cf, name, (size_t) size, tag);
    if (zone == NULL) {
        return NULL;
    }

    if (zone->data) {
        ctx = (ngx_stream_lua_shm_zone_ctx_t *) zone->data;
        return &ctx->zone;
    }

    n = sizeof(ngx_stream_lua_shm_zone_ctx_t);

    ctx = ngx_pcalloc(cf->pool, n);
    if (ctx == NULL) {
        return NULL;
    }

    ctx->lmcf = lmcf;
    ctx->log = &cf->cycle->new_log;
    ctx->cycle = cf->cycle;

    ngx_memcpy(&ctx->zone, zone, sizeof(ngx_shm_zone_t));

    zp = ngx_array_push(lmcf->shm_zones);
    if (zp == NULL) {
        return NULL;
    }

    *zp = zone;

    /* set zone init */
    zone->init = ngx_stream_lua_shared_memory_init;
    zone->data = ctx;

    lmcf->requires_shm = 1;

    return &ctx->zone;
}


static ngx_int_t
ngx_stream_lua_shared_memory_init(ngx_shm_zone_t *shm_zone, void *data)
{
    ngx_stream_lua_shm_zone_ctx_t       *octx = data;
    ngx_stream_lua_main_conf_t          *lmcf;
    ngx_stream_lua_shm_zone_ctx_t       *ctx;

    ngx_shm_zone_t              *ozone;
    void                        *odata;
    ngx_int_t                    rc;
    volatile ngx_cycle_t        *saved_cycle;
    ngx_shm_zone_t              *zone;

    ctx = (ngx_stream_lua_shm_zone_ctx_t *) shm_zone->data;
    zone = &ctx->zone;

    odata = NULL;
    if (octx) {
        ozone = &octx->zone;
        odata = ozone->data;
    }

    zone->shm = shm_zone->shm;
#if defined(nginx_version) && nginx_version >= 1009000
    zone->noreuse = shm_zone->noreuse;
#endif

    if (zone->init(zone, odata) != NGX_OK) {
        return NGX_ERROR;
    }

    dd("get lmcf");

    lmcf = ctx->lmcf;
    if (lmcf == NULL) {
        return NGX_ERROR;
    }

    dd("lmcf->lua: %p", lmcf->lua);

    lmcf->shm_zones_inited++;

    if (lmcf->shm_zones_inited == lmcf->shm_zones->nelts
        && lmcf->init_handler && !ngx_test_config)
    {
        saved_cycle = ngx_cycle;
        ngx_cycle = ctx->cycle;

        rc = lmcf->init_handler(ctx->log, lmcf, lmcf->lua);

        ngx_cycle = saved_cycle;

        if (rc != NGX_OK) {
            /* an error happened */
            return NGX_ERROR;
        }
    }

    return NGX_OK;
}


#if (NGX_LINUX)
int
ngx_stream_lua_ffi_req_dst_addr(ngx_stream_lua_request_t *r, char *buf,
    int *buf_size, u_char *errbuf, size_t *errbuf_size)
{
    int                fd;
    int                opt_name;
    int                family;
    socklen_t          addr_sz;
    socklen_t          len = sizeof(family);

    struct sockaddr_storage addr;

    addr_sz = sizeof(addr);
    /* Check if connection exists */
    if (r->session->connection == NULL) {
        *errbuf_size = ngx_snprintf(errbuf, *errbuf_size, "no connection")
                       - errbuf;
        return NGX_ERROR;
    }

    fd = r->session->connection->fd;

    /* Validate file descriptor */
    if (fd < 0) {
        *errbuf_size = ngx_snprintf(errbuf, *errbuf_size, "invalid fd")
                       - errbuf;
        return NGX_ERROR;
    }

    /* Get socket family using getsockopt */
    if (getsockopt(fd, SOL_SOCKET, SO_DOMAIN, &family, &len) != 0) {
        *errbuf_size = ngx_snprintf(errbuf, *errbuf_size,
                                    "failed to get socket family") - errbuf;
        return NGX_ERROR;
    }

    memset(&addr, 0, addr_sz);

    /* Get original destination address based on socket family */
    if (family == AF_INET) {
        /* IPv4 */
        opt_name = SO_ORIGINAL_DST;
        if (getsockopt(fd, SOL_IP, opt_name, &addr, &addr_sz) != 0) {
            *errbuf_size
                = ngx_snprintf(errbuf, *errbuf_size,
                               "failed to get IPv4 origin addr") - errbuf;
            return NGX_ERROR;
        }

#if (NGX_HAVE_INET6)

    } else if (family == AF_INET6) {
        /* IPv6 */
        opt_name = IP6T_SO_ORIGINAL_DST;
        if (getsockopt(fd, SOL_IPV6, opt_name, &addr, &addr_sz) != 0) {
            *errbuf_size
                = ngx_snprintf(errbuf, *errbuf_size,
                               "failed to get IPv6 origin addr") - errbuf;
            return NGX_ERROR;
        }
#endif

    } else {
        /* Unsupported address family */
        *errbuf_size
            = ngx_snprintf(errbuf, *errbuf_size,
                           "unsupported address family: %d", family) - errbuf;
        return NGX_ERROR;
    }

    /* Convert socket address to string representation */
    *buf_size = ngx_sock_ntop((struct sockaddr *)&addr, addr_sz,
                              (u_char *) buf, *buf_size, 1);

    return NGX_OK;
}
#endif

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
