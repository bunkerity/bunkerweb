
/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_http_headers_more_filter_module.h"
#include "ngx_http_headers_more_headers_out.h"
#include "ngx_http_headers_more_headers_in.h"
#include "ngx_http_headers_more_util.h"
#include <ngx_config.h>


/* config handlers */

static void *ngx_http_headers_more_create_loc_conf(ngx_conf_t *cf);
static char *ngx_http_headers_more_merge_loc_conf(ngx_conf_t *cf,
    void *parent, void *child);
static void *ngx_http_headers_more_create_main_conf(ngx_conf_t *cf);
static ngx_int_t ngx_http_headers_more_post_config(ngx_conf_t *cf);

/* post-read-phase handler */

static ngx_int_t ngx_http_headers_more_handler(ngx_http_request_t *r);

/* filter handlers */

static ngx_int_t ngx_http_headers_more_filter_init(ngx_conf_t *cf);

ngx_uint_t  ngx_http_headers_more_location_hash = 0;


static ngx_command_t  ngx_http_headers_more_filter_commands[] = {

    { ngx_string("more_set_headers"),
      NGX_HTTP_MAIN_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_LOC_CONF|NGX_HTTP_LIF_CONF
                        |NGX_CONF_1MORE,
      ngx_http_headers_more_set_headers,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL},

    { ngx_string("more_clear_headers"),
      NGX_HTTP_MAIN_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_LOC_CONF|NGX_HTTP_LIF_CONF
                        |NGX_CONF_1MORE,
      ngx_http_headers_more_clear_headers,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL},

    { ngx_string("more_set_input_headers"),
      NGX_HTTP_MAIN_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_LOC_CONF|NGX_HTTP_LIF_CONF
                        |NGX_CONF_1MORE,
      ngx_http_headers_more_set_input_headers,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL},

    { ngx_string("more_clear_input_headers"),
      NGX_HTTP_MAIN_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_LOC_CONF|NGX_HTTP_LIF_CONF
                        |NGX_CONF_1MORE,
      ngx_http_headers_more_clear_input_headers,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL},

      ngx_null_command
};


static ngx_http_module_t  ngx_http_headers_more_filter_module_ctx = {
    NULL,                                   /* preconfiguration */
    ngx_http_headers_more_post_config,      /* postconfiguration */

    ngx_http_headers_more_create_main_conf, /* create main configuration */
    NULL,                                   /* init main configuration */

    NULL,                                   /* create server configuration */
    NULL,                                   /* merge server configuration */

    ngx_http_headers_more_create_loc_conf,  /* create location configuration */
    ngx_http_headers_more_merge_loc_conf    /* merge location configuration */
};


ngx_module_t  ngx_http_headers_more_filter_module = {
    NGX_MODULE_V1,
    &ngx_http_headers_more_filter_module_ctx,   /* module context */
    ngx_http_headers_more_filter_commands,      /* module directives */
    NGX_HTTP_MODULE,                       /* module type */
    NULL,                                  /* init master */
    NULL,                                  /* init module */
    NULL,                                  /* init process */
    NULL,                                  /* init thread */
    NULL,                                  /* exit thread */
    NULL,                                  /* exit process */
    NULL,                                  /* exit master */
    NGX_MODULE_V1_PADDING
};


static ngx_http_output_header_filter_pt  ngx_http_next_header_filter;


static volatile ngx_cycle_t  *ngx_http_headers_more_prev_cycle = NULL;


static ngx_int_t
ngx_http_headers_more_filter(ngx_http_request_t *r)
{
    ngx_int_t                            rc;
    ngx_uint_t                           i;
    ngx_http_headers_more_loc_conf_t    *conf;
    ngx_http_headers_more_cmd_t         *cmd;

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "headers more header filter, uri \"%V\"", &r->uri);

    conf = ngx_http_get_module_loc_conf(r, ngx_http_headers_more_filter_module);

    if (conf->cmds) {
        cmd = conf->cmds->elts;
        for (i = 0; i < conf->cmds->nelts; i++) {
            if (cmd[i].is_input) {
                continue;
            }

            rc = ngx_http_headers_more_exec_cmd(r, &cmd[i]);

            if (rc != NGX_OK) {
                return rc;
            }
        }
    }

    return ngx_http_next_header_filter(r);
}


static ngx_int_t
ngx_http_headers_more_filter_init(ngx_conf_t *cf)
{
    ngx_http_next_header_filter = ngx_http_top_header_filter;
    ngx_http_top_header_filter = ngx_http_headers_more_filter;

    return NGX_OK;
}


static void *
ngx_http_headers_more_create_loc_conf(ngx_conf_t *cf)
{
    ngx_http_headers_more_loc_conf_t    *conf;

    conf = ngx_pcalloc(cf->pool, sizeof(ngx_http_headers_more_loc_conf_t));
    if (conf == NULL) {
        return NULL;
    }

    /*
     * set by ngx_pcalloc():
     *
     *     conf->cmds = NULL;
     */

    return conf;
}


static char *
ngx_http_headers_more_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child)
{
    ngx_uint_t                           i;
    ngx_uint_t                           orig_len;
    ngx_http_headers_more_cmd_t         *prev_cmd, *cmd;
    ngx_http_headers_more_loc_conf_t    *prev = parent;
    ngx_http_headers_more_loc_conf_t    *conf = child;

    if (conf->cmds == NULL || conf->cmds->nelts == 0) {
        conf->cmds = prev->cmds;

    } else if (prev->cmds && prev->cmds->nelts) {
        orig_len = conf->cmds->nelts;

        (void) ngx_array_push_n(conf->cmds, prev->cmds->nelts);

        cmd = conf->cmds->elts;

        for (i = 0; i < orig_len; i++) {
            cmd[conf->cmds->nelts - 1 - i] = cmd[orig_len - 1 - i];
        }

        prev_cmd = prev->cmds->elts;

        for (i = 0; i < prev->cmds->nelts; i++) {
            cmd[i] = prev_cmd[i];
        }
    }

    return NGX_CONF_OK;
}


static ngx_int_t
ngx_http_headers_more_post_config(ngx_conf_t *cf)
{
    int                              multi_http_blocks;
    ngx_int_t                        rc;
    ngx_http_handler_pt             *h;
    ngx_http_core_main_conf_t       *cmcf;

    ngx_http_headers_more_main_conf_t       *hmcf;

    ngx_http_headers_more_location_hash =
                               ngx_http_headers_more_hash_literal("location");

    hmcf = ngx_http_conf_get_module_main_conf(cf,
                                         ngx_http_headers_more_filter_module);

    if (ngx_http_headers_more_prev_cycle != ngx_cycle) {
        ngx_http_headers_more_prev_cycle = ngx_cycle;
        multi_http_blocks = 0;

    } else {
        multi_http_blocks = 1;
    }

    if (multi_http_blocks || hmcf->requires_filter) {
        rc = ngx_http_headers_more_filter_init(cf);
        if (rc != NGX_OK) {
            return rc;
        }
    }

    if (!hmcf->requires_handler) {
        return NGX_OK;
    }

    cmcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_core_module);

    h = ngx_array_push(&cmcf->phases[NGX_HTTP_REWRITE_PHASE].handlers);
    if (h == NULL) {
        return NGX_ERROR;
    }

    *h = ngx_http_headers_more_handler;

    return NGX_OK;
}


static ngx_int_t
ngx_http_headers_more_handler(ngx_http_request_t *r)
{
    ngx_int_t                            rc;
    ngx_uint_t                           i;
    ngx_http_headers_more_loc_conf_t    *conf;
    ngx_http_headers_more_main_conf_t   *hmcf;
    ngx_http_headers_more_cmd_t         *cmd;

    ngx_log_debug1(NGX_LOG_DEBUG_HTTP, r->connection->log, 0,
                   "headers more rewrite handler, uri \"%V\"", &r->uri);

    hmcf = ngx_http_get_module_main_conf(r,
                                         ngx_http_headers_more_filter_module);

    if (!hmcf->postponed_to_phase_end) {
        ngx_http_core_main_conf_t       *cmcf;
        ngx_http_phase_handler_t         tmp;
        ngx_http_phase_handler_t        *ph;
        ngx_http_phase_handler_t        *cur_ph;
        ngx_http_phase_handler_t        *last_ph;

        hmcf->postponed_to_phase_end = 1;

        cmcf = ngx_http_get_module_main_conf(r, ngx_http_core_module);

        ph = cmcf->phase_engine.handlers;
        cur_ph = &ph[r->phase_handler];
        last_ph = &ph[cur_ph->next - 1];

        if (cur_ph < last_ph) {
            dd("swaping the contents of cur_ph and last_ph...");

            tmp = *cur_ph;

            memmove(cur_ph, cur_ph + 1,
                    (last_ph - cur_ph) * sizeof (ngx_http_phase_handler_t));

            *last_ph = tmp;

            r->phase_handler--; /* redo the current ph */

            return NGX_DECLINED;
        }
    }

    dd("running phase handler...");

    conf = ngx_http_get_module_loc_conf(r, ngx_http_headers_more_filter_module);

    if (conf->cmds) {
        if (r->http_version < NGX_HTTP_VERSION_10) {
            return NGX_DECLINED;
        }

        cmd = conf->cmds->elts;
        for (i = 0; i < conf->cmds->nelts; i++) {
            if (!cmd[i].is_input) {
                continue;
            }

            rc = ngx_http_headers_more_exec_input_cmd(r, &cmd[i]);

            if (rc != NGX_OK) {
                return rc;
            }
        }
    }

    return NGX_DECLINED;
}


static void *
ngx_http_headers_more_create_main_conf(ngx_conf_t *cf)
{
    ngx_http_headers_more_main_conf_t    *hmcf;

    hmcf = ngx_pcalloc(cf->pool, sizeof(ngx_http_headers_more_main_conf_t));
    if (hmcf == NULL) {
        return NULL;
    }

    /* set by ngx_pcalloc:
     *      hmcf->postponed_to_phase_end = 0;
     *      hmcf->requires_filter        = 0;
     *      hmcf->requires_handler       = 0;
     */

    return hmcf;
}
