
/*
 * 2010 (C) Marcus Clyne
 */

#include    <ndk.h>

#include    <ndk_config.c>


#if (NDK_HTTP_PRE_CONFIG)
static  ngx_int_t   ndk_http_preconfiguration    (ngx_conf_t *cf);
#endif
#if (NDK_HTTP_POST_CONFIG)
static  ngx_int_t   ndk_http_postconfiguration   (ngx_conf_t *cf);
#endif
#if (NDK_HTTP_CREATE_MAIN_CONF)
static void *       ndk_http_create_main_conf    (ngx_conf_t *cf);
#endif
#if (NDK_HTTP_INIT_MAIN_CONF)
static char *       ndk_http_init_main_conf      (ngx_conf_t *cf, void *conf);
#endif
#if (NDK_HTTP_CREATE_SRV_CONF)
static void *       ndk_http_create_srv_conf     (ngx_conf_t *cf);
#endif
#if (NDK_HTTP_MERGE_SRV_CONF)
static char *       ndk_http_merge_srv_conf      (ngx_conf_t *cf, void *parent, void *child);
#endif
#if (NDK_HTTP_CREATE_LOC_CONF)
static void *       ndk_http_create_loc_conf     (ngx_conf_t *cf);
#endif
#if (NDK_HTTP_MERGE_LOC_CONF)
static char *       ndk_http_merge_loc_conf      (ngx_conf_t *cf, void *parent, void *child);
#endif


#if (NDK_HTTP_INIT_MASTER)
static ngx_int_t    ndk_http_init_master         (ngx_log_t *log);
#endif
#if (NDK_HTTP_INIT_MODULE)
static ngx_int_t    ndk_http_init_module         (ngx_cycle_t *cycle);
#endif
#if (NDK_HTTP_INIT_PROCESS)
static ngx_int_t    ndk_http_init_process        (ngx_cycle_t *cycle);
#endif
#if (NDK_HTTP_EXIT_PROCESS)
static void         ndk_http_exit_process        (ngx_cycle_t *cycle);
#endif
#if (NDK_HTTP_EXIT_MASTER)
static void         ndk_http_exit_master         (ngx_cycle_t *cycle);
#endif


ngx_http_module_t   ndk_http_module_ctx = {

#if (NDK_HTTP_PRE_CONFIG)
    ndk_http_preconfiguration,
#else
    NULL,
#endif
#if (NDK_HTTP_POST_CONFIG)
    ndk_http_postconfiguration,
#else
    NULL,
#endif

#if (NDK_HTTP_CREATE_MAIN_CONF)
    ndk_http_create_main_conf,
#else
    NULL,
#endif
#if (NDK_HTTP_INIT_MAIN_CONF)
    ndk_http_merge_main_conf,
#else
    NULL,
#endif

#if (NDK_HTTP_CREATE_SVR_CONF)
    ndk_http_create_srv_conf,
#else
    NULL,
#endif
#if (NDK_HTTP_MERGE_SVR_CONF)
    ndk_http_merge_srv_conf,
#else
    NULL,
#endif

#if (NDK_HTTP_CREATE_LOC_CONF)
    ndk_http_create_loc_conf,
#else
    NULL,
#endif
#if (NDK_HTTP_MERGE_LOC_CONF)
    ndk_http_merge_loc_conf,
#else
    NULL,
#endif

};

ngx_module_t          ndk_http_module = {

    NGX_MODULE_V1,
    &ndk_http_module_ctx,          /* module context */
    ndk_http_commands,             /* module directives */
    NGX_HTTP_MODULE,               /* module type */

#if (NDK_HTTP_INIT_MASTER)
    ndk_http_init_master,
#else
    NULL,
#endif

#if (NDK_HTTP_INIT_MODULE)
    ndk_http_init_module,
#else
    NULL,
#endif
#if (NDK_HTTP_INIT_PROCESS)
    ndk_http_init_process,
#else
    NULL,
#endif

    NULL,                                   /* init thread */
    NULL,                                   /* exit thread */

#if (NDK_HTTP_EXIT_PROCESS)
    ndk_http_exit_process,
#else
    NULL,
#endif
#if (NDK_HTTP_EXIT_MASTER)
    ndk_http_exit_master,
#else
    NULL,
#endif
    NGX_MODULE_V1_PADDING
};



#if (NDK_HTTP_CREATE_MAIN_CONF)
static void *
ndk_http_create_main_conf (ngx_conf_t *cf)
{
    ndk_http_main_conf_t    *mcf;

    ndk_pcallocp_rce (mcf, cf->pool);

    return  mcf;
}
#endif

