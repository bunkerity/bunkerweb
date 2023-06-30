 
/*
 * 2010 (C) Marcus Clyne
*/


#ifndef NDK_H
#define NDK_H


#include    <ngx_config.h>
#include    <ngx_core.h>
#include    <ngx_http.h>


#define     ndk_version     2015
#define     NDK_VERSION     "0.2.15"


#if (NGX_DEBUG)
#ifndef     NDK_DEBUG
#define     NDK_DEBUG 1
#endif
#else
#ifndef     NDK_DEBUG
#define     NDK_DEBUG 0
#endif
#endif


#if !(NDK)
#error At least one module requires the Nginx Development Kit to be compiled with \
the source (add --with-module=/path/to/devel/kit/src to configure command)
#endif

#include    <ndk_config.h>


#if (NDK_HTTP_CREATE_MAIN_CONF)

#define     ndk_http_conf_get_main_conf(cf)   ngx_http_conf_get_module_main_conf (cf, ndk_http_module)
#define     ndk_http_get_main_conf(r)         ngx_http_get_module_main_conf (r, ndk_http_module)

typedef struct {
#if (NDK_UPSTREAM_LIST)
    ngx_array_t         *upstreams;
#endif
} ndk_http_main_conf_t;

#endif /* NDK_HTTP_CREATE_MAIN_CONF */

#include    <ndk_includes.h>


extern  ngx_module_t    ndk_http_module;


#endif
