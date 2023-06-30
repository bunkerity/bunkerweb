
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_module.c.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_directive.h"
#include "ngx_stream_lua_contentby.h"
#include "ngx_stream_lua_util.h"
#include "ngx_stream_lua_initby.h"
#include "ngx_stream_lua_initworkerby.h"
#include "ngx_stream_lua_probe.h"
#include "ngx_stream_lua_balancer.h"
#include "ngx_stream_lua_logby.h"
#include "ngx_stream_lua_semaphore.h"
#include "ngx_stream_lua_ssl_client_helloby.h"
#include "ngx_stream_lua_ssl_certby.h"


#include "ngx_stream_lua_prereadby.h"


static void *ngx_stream_lua_create_main_conf(ngx_conf_t *cf);
static char *ngx_stream_lua_init_main_conf(ngx_conf_t *cf, void *conf);
static void *ngx_stream_lua_create_srv_conf(ngx_conf_t *cf);
static char *ngx_stream_lua_merge_srv_conf(ngx_conf_t *cf, void *parent,
    void *child);




static ngx_int_t ngx_stream_lua_init(ngx_conf_t *cf);
static char *ngx_stream_lua_lowat_check(ngx_conf_t *cf, void *post, void *data);
#if (NGX_STREAM_SSL)
static ngx_int_t ngx_stream_lua_set_ssl(ngx_conf_t *cf,
    ngx_stream_lua_loc_conf_t *llcf);
#if (nginx_version >= 1019004)
static char *ngx_stream_lua_ssl_conf_command_check(ngx_conf_t *cf, void *post,
    void *data);
#endif
#endif
static char *ngx_stream_lua_malloc_trim(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);


static ngx_conf_post_t  ngx_stream_lua_lowat_post =
    { ngx_stream_lua_lowat_check };
#if (NGX_STREAM_SSL)
#if (nginx_version >= 1019004)
static ngx_conf_post_t  ngx_stream_lua_ssl_conf_command_post =
    { ngx_stream_lua_ssl_conf_command_check };
#endif
#endif



#if (NGX_STREAM_SSL)

static ngx_conf_bitmask_t  ngx_stream_lua_ssl_protocols[] = {
    { ngx_string("SSLv2"), NGX_SSL_SSLv2 },
    { ngx_string("SSLv3"), NGX_SSL_SSLv3 },
    { ngx_string("TLSv1"), NGX_SSL_TLSv1 },
    { ngx_string("TLSv1.1"), NGX_SSL_TLSv1_1 },
    { ngx_string("TLSv1.2"), NGX_SSL_TLSv1_2 },
#ifdef NGX_SSL_TLSv1_3
    { ngx_string("TLSv1.3"), NGX_SSL_TLSv1_3 },
#endif
    { ngx_null_string, 0 }
};

#endif




static ngx_command_t ngx_stream_lua_cmds[] = {

    { ngx_string("lua_load_resty_core"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_FLAG,
      ngx_stream_lua_load_resty_core,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      NULL },

    { ngx_string("lua_max_running_timers"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, max_running_timers),
      NULL },

    { ngx_string("lua_max_pending_timers"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, max_pending_timers),
      NULL },

    { ngx_string("lua_shared_dict"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE2,
      ngx_stream_lua_shared_dict,
      0,
      0,
      NULL },

    { ngx_string("lua_sa_restart"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_FLAG,
      ngx_conf_set_flag_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, set_sa_restart),
      NULL },

    { ngx_string("lua_capture_error_log"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_capture_error_log,
      0,
      0,
      NULL },

#if (NGX_PCRE)
    { ngx_string("lua_regex_cache_max_entries"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, regex_cache_max_entries),
      NULL },

    { ngx_string("lua_regex_match_limit"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, regex_match_limit),
      NULL },
#endif

    { ngx_string("lua_package_cpath"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_package_cpath,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      NULL },

    { ngx_string("lua_package_path"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_package_path,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      NULL },

    { ngx_string("lua_code_cache"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_FLAG,
      ngx_stream_lua_code_cache,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_loc_conf_t, enable_code_cache),
      NULL },


     { ngx_string("lua_socket_log_errors"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_FLAG,
      ngx_conf_set_flag_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_loc_conf_t, log_socket_errors),
      NULL },

    { ngx_string("init_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_init_by_lua_block,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_by_inline },

    { ngx_string("init_by_lua"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_init_by_lua,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_by_inline },

    { ngx_string("init_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_init_by_lua,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_by_file },

    { ngx_string("init_worker_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_init_worker_by_lua_block,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_worker_by_inline },

    { ngx_string("init_worker_by_lua"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_init_worker_by_lua,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_worker_by_inline },

    { ngx_string("init_worker_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_init_worker_by_lua,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_init_worker_by_file },

    /* preread_by_lua_file rel/or/abs/path/to/script */
    { ngx_string("preread_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_preread_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_preread_handler_file },

    /* preread_by_lua_block { <inline script> } */
    { ngx_string("preread_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_preread_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_preread_handler_inline },


    /* content_by_lua "<inline script>" */
    { ngx_string("content_by_lua"),
      NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_content_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_content_handler_inline },

    /* content_by_lua_block { <inline script> } */
    { ngx_string("content_by_lua_block"),
      NGX_STREAM_SRV_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_content_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_content_handler_inline },

    /* content_by_lua_file rel/or/abs/path/to/script */
    { ngx_string("content_by_lua_file"),
      NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_content_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_content_handler_file },



    /* log_by_lua_block { <inline script> } */
    { ngx_string("log_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
                        |NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_log_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_log_handler_inline },

    { ngx_string("log_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
                        |NGX_CONF_TAKE1,
      ngx_stream_lua_log_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_log_handler_file },

    { ngx_string("preread_by_lua_no_postpone"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_FLAG,
      ngx_conf_set_flag_slot,
      NGX_STREAM_MAIN_CONF_OFFSET,
      offsetof(ngx_stream_lua_main_conf_t, postponed_to_preread_phase_end),
      NULL },

    { ngx_string("balancer_by_lua_block"),
      NGX_STREAM_UPS_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_balancer_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_balancer_handler_inline },

    { ngx_string("balancer_by_lua_file"),
      NGX_STREAM_UPS_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_balancer_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_balancer_handler_file },


    { ngx_string("lua_socket_keepalive_timeout"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_msec_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, keepalive_timeout),
      NULL },

    { ngx_string("lua_socket_connect_timeout"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_msec_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, connect_timeout),
      NULL },

    { ngx_string("lua_socket_send_timeout"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_msec_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, send_timeout),
      NULL },

    { ngx_string("lua_socket_send_lowat"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_size_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, send_lowat),
      &ngx_stream_lua_lowat_post },

    { ngx_string("lua_socket_buffer_size"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_size_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, buffer_size),
      NULL },

    { ngx_string("lua_socket_pool_size"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, pool_size),
      NULL },

    { ngx_string("lua_socket_read_timeout"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_TAKE1,
      ngx_conf_set_msec_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, read_timeout),
      NULL },


    { ngx_string("lua_check_client_abort"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF
          |NGX_CONF_FLAG,
      ngx_conf_set_flag_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, check_client_abort),
      NULL },



#if (NGX_STREAM_SSL)

    { ngx_string("lua_ssl_protocols"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_1MORE,
      ngx_conf_set_bitmask_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_protocols),
      &ngx_stream_lua_ssl_protocols },

    { ngx_string("lua_ssl_ciphers"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_str_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_ciphers),
      NULL },

    { ngx_string("ssl_client_hello_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_ssl_client_hello_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_ssl_client_hello_handler_inline },

    { ngx_string("ssl_client_hello_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_ssl_client_hello_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_ssl_client_hello_handler_file },

    { ngx_string("ssl_certificate_by_lua_block"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_BLOCK|NGX_CONF_NOARGS,
      ngx_stream_lua_ssl_cert_by_lua_block,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_ssl_cert_handler_inline },

    { ngx_string("ssl_certificate_by_lua_file"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_ssl_cert_by_lua,
      NGX_STREAM_SRV_CONF_OFFSET,
      0,
      (void *) ngx_stream_lua_ssl_cert_handler_file },


    { ngx_string("lua_ssl_verify_depth"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_num_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_verify_depth),
      NULL },

    { ngx_string("lua_ssl_trusted_certificate"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_str_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_trusted_certificate),
      NULL },

    { ngx_string("lua_ssl_crl"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE1,
      ngx_conf_set_str_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_crl),
      NULL },

#if (nginx_version >= 1019004)
    { ngx_string("lua_ssl_conf_command"),
      NGX_STREAM_MAIN_CONF|NGX_STREAM_SRV_CONF|NGX_CONF_TAKE2,
      ngx_conf_set_keyval_slot,
      NGX_STREAM_SRV_CONF_OFFSET,
      offsetof(ngx_stream_lua_srv_conf_t, ssl_conf_commands),
      &ngx_stream_lua_ssl_conf_command_post },
#endif
#endif  /* NGX_STREAM_SSL */

     { ngx_string("lua_malloc_trim"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_malloc_trim,
      NGX_STREAM_MAIN_CONF_OFFSET,
      0,
      NULL },

     { ngx_string("lua_add_variable"),
      NGX_STREAM_MAIN_CONF|NGX_CONF_TAKE1,
      ngx_stream_lua_add_variable,
      0,
      0,
      NULL },

    ngx_null_command
};


ngx_stream_module_t ngx_stream_lua_module_ctx = {
    NULL,                                     /*  preconfiguration */
    ngx_stream_lua_init,                /*  postconfiguration */

    ngx_stream_lua_create_main_conf,    /*  create main configuration */
    ngx_stream_lua_init_main_conf,      /*  init main configuration */

    ngx_stream_lua_create_srv_conf,     /*  create server configuration */
    ngx_stream_lua_merge_srv_conf,      /*  merge server configuration */

};


ngx_module_t ngx_stream_lua_module = {
    NGX_MODULE_V1,
    &ngx_stream_lua_module_ctx,       /*  module context */
    ngx_stream_lua_cmds,              /*  module directives */
    NGX_STREAM_MODULE,                /*  module type */
    NULL,                                   /*  init master */
    NULL,                                   /*  init module */
    ngx_stream_lua_init_worker,       /*  init process */
    NULL,                                   /*  init thread */
    NULL,                                   /*  exit thread */
    NULL,                                   /*  exit process */
    NULL,                                   /*  exit master */
    NGX_MODULE_V1_PADDING
};


static ngx_int_t
ngx_stream_lua_init(ngx_conf_t *cf)
{
    ngx_int_t                           rc;
    volatile ngx_cycle_t               *saved_cycle;
    ngx_array_t                        *arr;
    ngx_pool_cleanup_t                 *cln;

    ngx_stream_handler_pt              *h;
    ngx_stream_lua_main_conf_t         *lmcf;
    ngx_stream_core_main_conf_t        *cmcf;


    if (ngx_process == NGX_PROCESS_SIGNALLER || ngx_test_config) {
        return NGX_OK;
    }

    lmcf = ngx_stream_conf_get_module_main_conf(cf,
                                                ngx_stream_lua_module);


    cmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_core_module);

    if (lmcf->requires_preread) {
        h = ngx_array_push(&cmcf->phases[NGX_STREAM_PREREAD_PHASE].handlers);
        if (h == NULL) {
            return NGX_ERROR;
        }

        *h = ngx_stream_lua_preread_handler;
    }

    if (lmcf->postponed_to_preread_phase_end == NGX_CONF_UNSET) {
        lmcf->postponed_to_preread_phase_end = 0;
    }

    dd("requires log: %d", (int) lmcf->requires_log);

    if (lmcf->requires_log) {
        arr = &cmcf->phases[NGX_STREAM_LOG_PHASE].handlers;
        h = ngx_array_push(arr);
        if (h == NULL) {
            return NGX_ERROR;
        }

        if (arr->nelts > 1) {

            /*
             * if there are other log handlers, move them back and put ourself
             * to the front of the list
             */

            h = arr->elts;
            ngx_memmove(&h[1], h,
                        (arr->nelts - 1) * sizeof(ngx_stream_handler_pt));
        }

        *h = ngx_stream_lua_log_handler;
    }


    /* add the cleanup of semaphores after the lua_close */
    cln = ngx_pool_cleanup_add(cf->pool, 0);
    if (cln == NULL) {
        return NGX_ERROR;
    }

    cln->data = lmcf;
    cln->handler = ngx_stream_lua_sema_mm_cleanup;



    if (lmcf->lua == NULL) {
        dd("initializing lua vm");

#ifndef OPENRESTY_LUAJIT
        if (ngx_process != NGX_PROCESS_SIGNALLER && !ngx_test_config) {
            ngx_log_error(NGX_LOG_ALERT, cf->log, 0,
                          "detected a LuaJIT version which is not OpenResty's"
                          "; many optimizations will be disabled and "
                          "performance will be compromised (see "
                          "https://github.com/openresty/luajit2 for "
                          "OpenResty's LuaJIT or, even better, consider using "
                          "the OpenResty releases from https://openresty.org/"
                          "en/download.html)");
        }
#endif


        rc = ngx_stream_lua_init_vm(&lmcf->lua, NULL, cf->cycle, cf->pool,
                                    lmcf, cf->log, NULL);
        if (rc != NGX_OK) {
            if (rc == NGX_DECLINED) {
                ngx_stream_lua_assert(lmcf->lua != NULL);

                ngx_conf_log_error(NGX_LOG_ALERT, cf, 0,
                                   "failed to load the 'resty.core' module "
                                   "(https://github.com/openresty/lua-resty"
                                   "-core); ensure you are using an OpenResty "
                                   "release from https://openresty.org/en/"
                                   "download.html (reason: %s)",
                                   lua_tostring(lmcf->lua, -1));

            } else {
                /* rc == NGX_ERROR */
                ngx_conf_log_error(NGX_LOG_ALERT, cf, 0,
                                   "failed to initialize Lua VM");
            }

             return NGX_ERROR;
        }

        /* rc == NGX_OK */

        ngx_stream_lua_assert(lmcf->lua != NULL);

        if (!lmcf->requires_shm && lmcf->init_handler) {
            saved_cycle = ngx_cycle;
            ngx_cycle = cf->cycle;

            rc = lmcf->init_handler(cf->log, lmcf, lmcf->lua);

            ngx_cycle = saved_cycle;

            if (rc != NGX_OK) {
                /* an error happened */
                return NGX_ERROR;
            }
        }

        dd("Lua VM initialized!");
    }

    return NGX_OK;
}


static char *
ngx_stream_lua_lowat_check(ngx_conf_t *cf, void *post, void *data)
{
#if (NGX_FREEBSD)
    ssize_t *np = data;

    if ((u_long) *np >= ngx_freebsd_net_inet_tcp_sendspace) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "\"lua_send_lowat\" must be less than %d "
                           "(sysctl net.inet.tcp.sendspace)",
                           ngx_freebsd_net_inet_tcp_sendspace);

        return NGX_CONF_ERROR;
    }

#elif !(NGX_HAVE_SO_SNDLOWAT)
    ssize_t *np = data;

    ngx_conf_log_error(NGX_LOG_WARN, cf, 0,
                       "\"lua_send_lowat\" is not supported, ignored");

    *np = 0;

#endif

    return NGX_CONF_OK;
}


static void *
ngx_stream_lua_create_main_conf(ngx_conf_t *cf)
{
    ngx_int_t       rc;

    ngx_stream_lua_main_conf_t          *lmcf;

    lmcf = ngx_pcalloc(cf->pool, sizeof(ngx_stream_lua_main_conf_t));
    if (lmcf == NULL) {
        return NULL;
    }

    /* set by ngx_pcalloc:
     *      lmcf->lua = NULL;
     *      lmcf->lua_path = { 0, NULL };
     *      lmcf->lua_cpath = { 0, NULL };
     *      lmcf->pending_timers = 0;
     *      lmcf->running_timers = 0;
     *      lmcf->watcher = NULL;
     *      lmcf->regex_cache_entries = 0;
     *      lmcf->jit_stack = NULL;
     *      lmcf->shm_zones = NULL;
     *      lmcf->init_handler = NULL;
     *      lmcf->init_src = { 0, NULL };
     *      lmcf->shm_zones_inited = 0;
     *      lmcf->shdict_zones = NULL;
     *      lmcf->preload_hooks = NULL;
     *      lmcf->requires_header_filter = 0;
     *      lmcf->requires_body_filter = 0;
     *      lmcf->requires_capture_filter = 0;
     *      lmcf->requires_rewrite = 0;
     *      lmcf->requires_access = 0;
     *      lmcf->requires_log = 0;
     *      lmcf->requires_shm = 0;
     */

    lmcf->pool = cf->pool;
    lmcf->max_pending_timers = NGX_CONF_UNSET;
    lmcf->max_running_timers = NGX_CONF_UNSET;
#if (NGX_PCRE)
    lmcf->regex_cache_max_entries = NGX_CONF_UNSET;
    lmcf->regex_match_limit = NGX_CONF_UNSET;
#endif

    lmcf->postponed_to_preread_phase_end = NGX_CONF_UNSET;

    lmcf->set_sa_restart = NGX_CONF_UNSET;

#if (NGX_STREAM_LUA_HAVE_MALLOC_TRIM)
    lmcf->malloc_trim_cycle = NGX_CONF_UNSET_UINT;
#endif

    rc = ngx_stream_lua_sema_mm_init(cf, lmcf);
    if (rc != NGX_OK) {
        return NULL;
    }

    dd("nginx Lua module main config structure initialized!");

    return lmcf;
}


static char *
ngx_stream_lua_init_main_conf(ngx_conf_t *cf, void *conf)
{
    ngx_stream_lua_main_conf_t       *lmcf = conf;

#if (NGX_PCRE)
    if (lmcf->regex_cache_max_entries == NGX_CONF_UNSET) {
        lmcf->regex_cache_max_entries = 1024;
    }

    if (lmcf->regex_match_limit == NGX_CONF_UNSET) {
        lmcf->regex_match_limit = 0;
    }
#endif

    if (lmcf->max_pending_timers == NGX_CONF_UNSET) {
        lmcf->max_pending_timers = 1024;
    }

    if (lmcf->max_running_timers == NGX_CONF_UNSET) {
        lmcf->max_running_timers = 256;
    }

#if (NGX_STREAM_LUA_HAVE_SA_RESTART)
    if (lmcf->set_sa_restart == NGX_CONF_UNSET) {
        lmcf->set_sa_restart = 1;
    }
#endif

#if (NGX_STREAM_LUA_HAVE_MALLOC_TRIM)
    if (lmcf->malloc_trim_cycle == NGX_CONF_UNSET_UINT) {
        lmcf->malloc_trim_cycle = 1000;  /* number of reqs */
    }
#endif

    lmcf->cycle = cf->cycle;

    return NGX_CONF_OK;
}






static void *
ngx_stream_lua_create_srv_conf(ngx_conf_t *cf)
{
    ngx_stream_lua_srv_conf_t           *conf;

    conf = ngx_pcalloc(cf->pool, sizeof(ngx_stream_lua_srv_conf_t));
    if (conf == NULL) {
        return NULL;
    }

    /* set by ngx_pcalloc:
     *      lscf->srv.ssl_client_hello_handler = NULL;
     *      lscf->srv.ssl_client_hello_src = { 0, NULL };
     *      lscf->srv.ssl_client_hello_src_key = NULL;
     *
     *      lscf->srv.ssl_cert_handler = NULL;
     *      lscf->srv.ssl_cert_src = { 0, NULL };
     *      lscf->srv.ssl_cert_src_key = NULL;
     *
     *      lscf->srv.ssl_session_store_handler = NULL;
     *      lscf->srv.ssl_session_store_src = { 0, NULL };
     *      lscf->srv.ssl_session_store_src_key = NULL;
     *
     *      lscf->srv.ssl_session_fetch_handler = NULL;
     *      lscf->srv.ssl_session_fetch_src = { 0, NULL };
     *      lscf->srv.ssl_session_fetch_src_key = NULL;
     *
     *      lscf->balancer.handler = NULL;
     *      lscf->balancer.src = { 0, NULL };
     *      lscf->balancer.src_key = NULL;
     */

    conf->enable_code_cache  = NGX_CONF_UNSET;
    conf->check_client_abort = NGX_CONF_UNSET;

    conf->keepalive_timeout = NGX_CONF_UNSET_MSEC;
    conf->connect_timeout = NGX_CONF_UNSET_MSEC;
    conf->send_timeout = NGX_CONF_UNSET_MSEC;
    conf->read_timeout = NGX_CONF_UNSET_MSEC;
    conf->send_lowat = NGX_CONF_UNSET_SIZE;
    conf->buffer_size = NGX_CONF_UNSET_SIZE;
    conf->pool_size = NGX_CONF_UNSET_UINT;

    conf->log_socket_errors = NGX_CONF_UNSET;

#if (NGX_STREAM_SSL)
    conf->ssl_verify_depth = NGX_CONF_UNSET_UINT;
#endif

    return conf;
}


static char *
ngx_stream_lua_merge_srv_conf(ngx_conf_t *cf, void *parent, void *child)
{
    ngx_stream_lua_srv_conf_t       *prev = parent;
    ngx_stream_lua_srv_conf_t       *conf = child;

#if (NGX_STREAM_SSL)
    ngx_stream_ssl_conf_t           *sscf;

    dd("merge srv conf");

    sscf = ngx_stream_conf_get_module_srv_conf(cf, ngx_stream_ssl_module);
    if (sscf && sscf->listen) {
        if (conf->srv.ssl_client_hello_src.len == 0) {
            conf->srv.ssl_client_hello_src = prev->srv.ssl_client_hello_src;
            conf->srv.ssl_client_hello_src_key =
                prev->srv.ssl_client_hello_src_key;
            conf->srv.ssl_client_hello_handler =
                prev->srv.ssl_client_hello_handler;
        }

        if (conf->srv.ssl_client_hello_src.len) {
            if (sscf->ssl.ctx == NULL) {
                ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                              "no ssl configured for the server");

                return NGX_CONF_ERROR;
            }
#ifdef LIBRESSL_VERSION_NUMBER
            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "LibreSSL does not support by "
                          "ssl_client_hello_by_lua*");
            return NGX_CONF_ERROR;

#else

#   ifdef SSL_ERROR_WANT_CLIENT_HELLO_CB

            SSL_CTX_set_client_hello_cb(sscf->ssl.ctx,
                                        ngx_stream_lua_ssl_client_hello_handler,
                                        NULL);

#   else

            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "OpenSSL too old to support "
                          "ssl_client_hello_by_lua*");
            return NGX_CONF_ERROR;

#   endif
#endif
        }

        if (conf->srv.ssl_cert_src.len == 0) {
            conf->srv.ssl_cert_src = prev->srv.ssl_cert_src;
            conf->srv.ssl_cert_src_key = prev->srv.ssl_cert_src_key;
            conf->srv.ssl_cert_handler = prev->srv.ssl_cert_handler;
        }

        if (conf->srv.ssl_cert_src.len) {
            if (sscf->ssl.ctx == NULL) {
                ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                              "no ssl configured for the server");

                return NGX_CONF_ERROR;
            }

#ifdef LIBRESSL_VERSION_NUMBER

            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "LibreSSL is not supported by ssl_certificate_by_lua*");
            return NGX_CONF_ERROR;

#else

#   if OPENSSL_VERSION_NUMBER >= 0x1000205fL

            SSL_CTX_set_cert_cb(sscf->ssl.ctx, ngx_stream_lua_ssl_cert_handler, NULL);

#   else

            ngx_log_error(NGX_LOG_EMERG, cf->log, 0,
                          "OpenSSL too old to support ssl_certificate_by_lua*");
            return NGX_CONF_ERROR;

#   endif

#endif
        }
    }


#endif  /* NGX_STREAM_SSL */

#if (NGX_STREAM_SSL)

    ngx_conf_merge_bitmask_value(conf->ssl_protocols, prev->ssl_protocols,
                                 NGX_CONF_BITMASK_SET|NGX_SSL_SSLv3
                                 |NGX_SSL_TLSv1|NGX_SSL_TLSv1_1
                                 |NGX_SSL_TLSv1_2);

    ngx_conf_merge_str_value(conf->ssl_ciphers, prev->ssl_ciphers,
                             "DEFAULT");

    ngx_conf_merge_uint_value(conf->ssl_verify_depth,
                              prev->ssl_verify_depth, 1);
    ngx_conf_merge_str_value(conf->ssl_trusted_certificate,
                             prev->ssl_trusted_certificate, "");
    ngx_conf_merge_str_value(conf->ssl_crl, prev->ssl_crl, "");
#if (nginx_version >= 1019004)
    ngx_conf_merge_ptr_value(conf->ssl_conf_commands, prev->ssl_conf_commands,
                             NULL);
#endif

    if (ngx_stream_lua_set_ssl(cf, conf) != NGX_OK) {
        return NGX_CONF_ERROR;
    }

#endif

    ngx_conf_merge_value(conf->enable_code_cache, prev->enable_code_cache, 1);
    ngx_conf_merge_value(conf->check_client_abort, prev->check_client_abort, 0);

    ngx_conf_merge_msec_value(conf->keepalive_timeout,
                              prev->keepalive_timeout, 60000);

    ngx_conf_merge_msec_value(conf->connect_timeout,
                              prev->connect_timeout, 60000);

    ngx_conf_merge_msec_value(conf->send_timeout,
                              prev->send_timeout, 60000);

    ngx_conf_merge_msec_value(conf->read_timeout,
                              prev->read_timeout, 60000);

    ngx_conf_merge_size_value(conf->send_lowat,
                              prev->send_lowat, 0);

    ngx_conf_merge_size_value(conf->buffer_size,
                              prev->buffer_size,
                              (size_t) ngx_pagesize);

    ngx_conf_merge_uint_value(conf->pool_size, prev->pool_size, 30);

    ngx_conf_merge_value(conf->log_socket_errors, prev->log_socket_errors, 1);

    if (conf->preread_src.value.len == 0) {
        conf->preread_src = prev->preread_src;
        conf->preread_handler = prev->preread_handler;
        conf->preread_src_key = prev->preread_src_key;
        conf->preread_chunkname = prev->preread_chunkname;
    }

    return NGX_CONF_OK;
}




#if (NGX_STREAM_SSL)

static ngx_int_t
ngx_stream_lua_set_ssl(ngx_conf_t *cf, ngx_stream_lua_srv_conf_t *lscf)
{
    ngx_pool_cleanup_t  *cln;

    lscf->ssl = ngx_pcalloc(cf->pool, sizeof(ngx_ssl_t));
    if (lscf->ssl == NULL) {
        return NGX_ERROR;
    }

    lscf->ssl->log = cf->log;

    if (ngx_ssl_create(lscf->ssl, lscf->ssl_protocols, NULL) != NGX_OK) {
        return NGX_ERROR;
    }

    cln = ngx_pool_cleanup_add(cf->pool, 0);
    if (cln == NULL) {
        return NGX_ERROR;
    }

    cln->handler = ngx_ssl_cleanup_ctx;
    cln->data = lscf->ssl;

    if (SSL_CTX_set_cipher_list(lscf->ssl->ctx,
                                (const char *) lscf->ssl_ciphers.data)
        == 0)
    {
        ngx_ssl_error(NGX_LOG_EMERG, cf->log, 0,
                      "SSL_CTX_set_cipher_list(\"%V\") failed",
                      &lscf->ssl_ciphers);
        return NGX_ERROR;
    }

    if (lscf->ssl_trusted_certificate.len
        && ngx_ssl_trusted_certificate(cf, lscf->ssl,
                                       &lscf->ssl_trusted_certificate,
                                       lscf->ssl_verify_depth)
        != NGX_OK)
    {
        return NGX_ERROR;
    }

    dd("ssl crl: %.*s", (int) lscf->ssl_crl.len, lscf->ssl_crl.data);

    if (ngx_ssl_crl(cf, lscf->ssl, &lscf->ssl_crl) != NGX_OK) {
        return NGX_ERROR;
    }

#if (nginx_version >= 1019004)
    if (ngx_ssl_conf_commands(cf, lscf->ssl, lscf->ssl_conf_commands)
        != NGX_OK) {
        return NGX_ERROR;
    }
#endif
    return NGX_OK;
}

#if (nginx_version >= 1019004)
static char *
ngx_stream_lua_ssl_conf_command_check(ngx_conf_t *cf, void *post, void *data)
{
#ifndef SSL_CONF_FLAG_FILE
    return "is not supported on this platform";
#endif

    return NGX_CONF_OK;
}
#endif
#endif  /* NGX_STREAM_SSL */


static char *
ngx_stream_lua_malloc_trim(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
#if (NGX_STREAM_LUA_HAVE_MALLOC_TRIM)

    ngx_int_t       nreqs;
    ngx_str_t      *value;

    ngx_stream_lua_main_conf_t          *lmcf = conf;

    value = cf->args->elts;

    nreqs = ngx_atoi(value[1].data, value[1].len);
    if (nreqs == NGX_ERROR) {
        return "invalid number in the 1st argument";
    }

    lmcf->malloc_trim_cycle = (ngx_uint_t) nreqs;

    if (nreqs == 0) {
        return NGX_CONF_OK;
    }

    lmcf->requires_log = 1;

#else

    ngx_conf_log_error(NGX_LOG_WARN, cf, 0, "lua_malloc_trim is not supported "
                       "on this platform, ignored");

#endif
    return NGX_CONF_OK;
}

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
