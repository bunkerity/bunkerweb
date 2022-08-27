/*
 * ModSecurity connector for nginx, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifndef MODSECURITY_DDEBUG
#define MODSECURITY_DDEBUG 0
#endif
#include "ddebug.h"

#include "ngx_http_modsecurity_common.h"
#include "stdio.h"
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

static ngx_int_t ngx_http_modsecurity_init(ngx_conf_t *cf);
static void *ngx_http_modsecurity_create_main_conf(ngx_conf_t *cf);
static char *ngx_http_modsecurity_init_main_conf(ngx_conf_t *cf, void *conf);
static void *ngx_http_modsecurity_create_conf(ngx_conf_t *cf);
static char *ngx_http_modsecurity_merge_conf(ngx_conf_t *cf, void *parent, void *child);
static void ngx_http_modsecurity_cleanup_instance(void *data);
static void ngx_http_modsecurity_cleanup_rules(void *data);


/*
 * PCRE malloc/free workaround, based on
 * https://github.com/openresty/lua-nginx-module/blob/master/src/ngx_http_lua_pcrefix.c
 */

#if !(NGX_PCRE2)
static void *(*old_pcre_malloc)(size_t);
static void (*old_pcre_free)(void *ptr);
static ngx_pool_t *ngx_http_modsec_pcre_pool = NULL;

static void *
ngx_http_modsec_pcre_malloc(size_t size)
{
    if (ngx_http_modsec_pcre_pool) {
        return ngx_palloc(ngx_http_modsec_pcre_pool, size);
    }

    fprintf(stderr, "error: modsec pcre malloc failed due to empty pcre pool");

    return NULL;
}

static void
ngx_http_modsec_pcre_free(void *ptr)
{
    if (ngx_http_modsec_pcre_pool) {
        ngx_pfree(ngx_http_modsec_pcre_pool, ptr);
        return;
    }

#if 0
    /* this may happen when called from cleanup handlers */
    fprintf(stderr, "error: modsec pcre free failed due to empty pcre pool");
#endif

    return;
}

ngx_pool_t *
ngx_http_modsecurity_pcre_malloc_init(ngx_pool_t *pool)
{
    ngx_pool_t  *old_pool;

    if (pcre_malloc != ngx_http_modsec_pcre_malloc) {
        ngx_http_modsec_pcre_pool = pool;

        old_pcre_malloc = pcre_malloc;
        old_pcre_free = pcre_free;

        pcre_malloc = ngx_http_modsec_pcre_malloc;
        pcre_free = ngx_http_modsec_pcre_free;

        return NULL;
    }

    old_pool = ngx_http_modsec_pcre_pool;
    ngx_http_modsec_pcre_pool = pool;

    return old_pool;
}

void
ngx_http_modsecurity_pcre_malloc_done(ngx_pool_t *old_pool)
{
    ngx_http_modsec_pcre_pool = old_pool;

    if (old_pool == NULL) {
        pcre_malloc = old_pcre_malloc;
        pcre_free = old_pcre_free;
    }
}
#endif

/*
 * ngx_string's are not null-terminated in common case, so we need to convert
 * them into null-terminated ones before passing to ModSecurity
 */
ngx_inline char *ngx_str_to_char(ngx_str_t a, ngx_pool_t *p)
{
    char *str = NULL;

    if (a.len == 0) {
        return NULL;
    }

    str = ngx_pnalloc(p, a.len+1);
    if (str == NULL) {
        dd("failed to allocate memory to convert space ngx_string to C string");
        /* We already returned NULL for an empty string, so return -1 here to indicate allocation error */
        return (char *)-1;
    }
    ngx_memcpy(str, a.data, a.len);
    str[a.len] = '\0';

    return str;
}


ngx_inline int
ngx_http_modsecurity_process_intervention (Transaction *transaction, ngx_http_request_t *r, ngx_int_t early_log)
{
    char *log = NULL;
    ModSecurityIntervention intervention;
    intervention.status = 200;
    intervention.url = NULL;
    intervention.log = NULL;
    intervention.disruptive = 0;
    ngx_http_modsecurity_ctx_t *ctx = NULL;

    dd("processing intervention");

    ctx = ngx_http_get_module_ctx(r, ngx_http_modsecurity_module);
    if (ctx == NULL)
    {
        return NGX_HTTP_INTERNAL_SERVER_ERROR;
    }

    if (msc_intervention(transaction, &intervention) == 0) {
        dd("nothing to do");
        return 0;
    }

    log = intervention.log;
    if (intervention.log == NULL) {
        log = "(no log message was specified)";
    }

    ngx_log_error(NGX_LOG_ERR, (ngx_log_t *)r->connection->log, 0, "%s", log);

    if (intervention.log != NULL) {
        free(intervention.log);
    }

    if (intervention.url != NULL)
    {
        dd("intervention -- redirecting to: %s with status code: %d", intervention.url, intervention.status);

        if (r->header_sent)
        {
            dd("Headers are already sent. Cannot perform the redirection at this point.");
            return -1;
        }

        /**
         * Not sure if it sane to do this indepent of the phase
         * but, here we go...
         *
         * This code cames from: http/ngx_http_special_response.c
         * function: ngx_http_send_error_page
         * src/http/ngx_http_core_module.c
         * From src/http/ngx_http_core_module.c (line 1910) i learnt
         * that location->hash should be set to 1.
         *
         */
        ngx_http_clear_location(r);
        ngx_str_t a = ngx_string("");

        a.data = (unsigned char *)intervention.url;
        a.len = strlen(intervention.url);

        ngx_table_elt_t *location = NULL;
        location = ngx_list_push(&r->headers_out.headers);
        ngx_str_set(&location->key, "Location");
        location->value = a;
        r->headers_out.location = location;
        r->headers_out.location->hash = 1;

#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
        ngx_http_modsecurity_store_ctx_header(r, &location->key, &location->value);
#endif

        return intervention.status;
    }

    if (intervention.status != 200)
    {
        /**
         * FIXME: this will bring proper response code to audit log in case
         * when e.g. error_page redirect was triggered, but there still won't be another
         * required pieces like response headers etc.
         *
         */
        msc_update_status_code(ctx->modsec_transaction, intervention.status);

        if (early_log) {
            dd("intervention -- calling log handler manually with code: %d", intervention.status);
            ngx_http_modsecurity_log_handler(r);
            ctx->logged = 1;
	}

        if (r->header_sent)
        {
            dd("Headers are already sent. Cannot perform the redirection at this point.");
            return -1;
        }
        dd("intervention -- returning code: %d", intervention.status);
        return intervention.status;
    }
    return 0;
}


void
ngx_http_modsecurity_cleanup(void *data)
{
    ngx_http_modsecurity_ctx_t *ctx;

    ctx = (ngx_http_modsecurity_ctx_t *) data;

    msc_transaction_cleanup(ctx->modsec_transaction);

#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    /*
     * Purge stored context headers.  Memory allocated for individual stored header
     * name/value pair will be freed automatically when r->pool is destroyed.
     */
    ngx_array_destroy(ctx->sanity_headers_out);
#endif
}


ngx_inline ngx_http_modsecurity_ctx_t *
ngx_http_modsecurity_create_ctx(ngx_http_request_t *r)
{
    ngx_str_t                          s;
    ngx_pool_cleanup_t                *cln;
    ngx_http_modsecurity_ctx_t        *ctx;
    ngx_http_modsecurity_conf_t       *mcf;
    ngx_http_modsecurity_main_conf_t  *mmcf;

    ctx = ngx_pcalloc(r->pool, sizeof(ngx_http_modsecurity_ctx_t));
    if (ctx == NULL)
    {
        dd("failed to allocate memory for the context.");
        return NULL;
    }

    mmcf = ngx_http_get_module_main_conf(r, ngx_http_modsecurity_module);
    mcf = ngx_http_get_module_loc_conf(r, ngx_http_modsecurity_module);

    dd("creating transaction with the following rules: '%p' -- ms: '%p'", mcf->rules_set, mmcf->modsec);

    if (mcf->transaction_id) {
        if (ngx_http_complex_value(r, mcf->transaction_id, &s) != NGX_OK) {
            return NGX_CONF_ERROR;
        }
        ctx->modsec_transaction = msc_new_transaction_with_id(mmcf->modsec, mcf->rules_set, (char *) s.data, r->connection->log);

    } else {
        ctx->modsec_transaction = msc_new_transaction(mmcf->modsec, mcf->rules_set, r->connection->log);
    }

    dd("transaction created");

    ngx_http_set_ctx(r, ctx, ngx_http_modsecurity_module);

    cln = ngx_pool_cleanup_add(r->pool, sizeof(ngx_http_modsecurity_ctx_t));
    if (cln == NULL)
    {
        dd("failed to create the ModSecurity context cleanup");
        return NGX_CONF_ERROR;
    }
    cln->handler = ngx_http_modsecurity_cleanup;
    cln->data = ctx;

#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    ctx->sanity_headers_out = ngx_array_create(r->pool, 12, sizeof(ngx_http_modsecurity_header_t));
    if (ctx->sanity_headers_out == NULL) {
        return NGX_CONF_ERROR;
    }
#endif

    return ctx;
}


char *
ngx_conf_set_rules(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    int                                res;
    char                              *rules;
    ngx_str_t                         *value;
    const char                        *error;
    ngx_pool_t                        *old_pool;
    ngx_http_modsecurity_conf_t       *mcf = conf;
    ngx_http_modsecurity_main_conf_t  *mmcf;

    value = cf->args->elts;
    rules = ngx_str_to_char(value[1], cf->pool);

    if (rules == (char *)-1) {
        return NGX_CONF_ERROR;
    }

    old_pool = ngx_http_modsecurity_pcre_malloc_init(cf->pool);
    res = msc_rules_add(mcf->rules_set, rules, &error);
    ngx_http_modsecurity_pcre_malloc_done(old_pool);

    if (res < 0) {
        dd("Failed to load the rules: '%s' - reason: '%s'", rules, error);
        return strdup(error);
    }

    mmcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_modsecurity_module);
    mmcf->rules_inline += res;

    return NGX_CONF_OK;
}


char *
ngx_conf_set_rules_file(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    int                                res;
    char                              *rules_set;
    ngx_str_t                         *value;
    const char                        *error;
    ngx_pool_t                        *old_pool;
    ngx_http_modsecurity_conf_t       *mcf = conf;
    ngx_http_modsecurity_main_conf_t  *mmcf;

    value = cf->args->elts;
    rules_set = ngx_str_to_char(value[1], cf->pool);

    if (rules_set == (char *)-1) {
        return NGX_CONF_ERROR;
    }

    old_pool = ngx_http_modsecurity_pcre_malloc_init(cf->pool);
    res = msc_rules_add_file(mcf->rules_set, rules_set, &error);
    ngx_http_modsecurity_pcre_malloc_done(old_pool);

    if (res < 0) {
        dd("Failed to load the rules from: '%s' - reason: '%s'", rules_set, error);
        return strdup(error);
    }

    mmcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_modsecurity_module);
    mmcf->rules_file += res;

    return NGX_CONF_OK;
}


char *
ngx_conf_set_rules_remote(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    int                                res;
    ngx_str_t                         *value;
    const char                        *error;
    const char                        *rules_remote_key, *rules_remote_server;
    ngx_pool_t                        *old_pool;
    ngx_http_modsecurity_conf_t       *mcf = conf;
    ngx_http_modsecurity_main_conf_t  *mmcf;

    value = cf->args->elts;
    rules_remote_key = ngx_str_to_char(value[1], cf->pool);
    rules_remote_server = ngx_str_to_char(value[2], cf->pool);

    if (rules_remote_server == (char *)-1) {
        return NGX_CONF_ERROR;
    }

    if (rules_remote_key == (char *)-1) {
        return NGX_CONF_ERROR;
    }

    old_pool = ngx_http_modsecurity_pcre_malloc_init(cf->pool);
    res = msc_rules_add_remote(mcf->rules_set, rules_remote_key, rules_remote_server, &error);
    ngx_http_modsecurity_pcre_malloc_done(old_pool);

    if (res < 0) {
        dd("Failed to load the rules from: '%s'  - reason: '%s'", rules_remote_server, error);
        return strdup(error);
    }

    mmcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_modsecurity_module);
    mmcf->rules_remote += res;

    return NGX_CONF_OK;
}


char *ngx_conf_set_transaction_id(ngx_conf_t *cf, ngx_command_t *cmd, void *conf) {
    ngx_str_t                         *value;
    ngx_http_complex_value_t           cv;
    ngx_http_compile_complex_value_t   ccv;
    ngx_http_modsecurity_conf_t *mcf = conf;

    value = cf->args->elts;

    ngx_memzero(&ccv, sizeof(ngx_http_compile_complex_value_t));

    ccv.cf = cf;
    ccv.value = &value[1];
    ccv.complex_value = &cv;
    ccv.zero = 1;

    if (ngx_http_compile_complex_value(&ccv) != NGX_OK) {
        return NGX_CONF_ERROR;
    }

    mcf->transaction_id = ngx_palloc(cf->pool, sizeof(ngx_http_complex_value_t));
    if (mcf->transaction_id == NULL) {
        return NGX_CONF_ERROR;
    }

    *mcf->transaction_id = cv;

    return NGX_CONF_OK;
}


static ngx_command_t ngx_http_modsecurity_commands[] =  {
  {
    ngx_string("modsecurity"),
    NGX_HTTP_LOC_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_MAIN_CONF|NGX_CONF_FLAG,
    ngx_conf_set_flag_slot,
    NGX_HTTP_LOC_CONF_OFFSET,
    offsetof(ngx_http_modsecurity_conf_t, enable),
    NULL
  },
  {
    ngx_string("modsecurity_rules"),
    NGX_HTTP_LOC_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_MAIN_CONF|NGX_CONF_TAKE1,
    ngx_conf_set_rules,
    NGX_HTTP_LOC_CONF_OFFSET,
    offsetof(ngx_http_modsecurity_conf_t, enable),
    NULL
  },
  {
    ngx_string("modsecurity_rules_file"),
    NGX_HTTP_LOC_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_MAIN_CONF|NGX_CONF_TAKE1,
    ngx_conf_set_rules_file,
    NGX_HTTP_LOC_CONF_OFFSET,
    offsetof(ngx_http_modsecurity_conf_t, enable),
    NULL
  },
  {
    ngx_string("modsecurity_rules_remote"),
    NGX_HTTP_LOC_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_MAIN_CONF|NGX_CONF_TAKE2,
    ngx_conf_set_rules_remote,
    NGX_HTTP_LOC_CONF_OFFSET,
    offsetof(ngx_http_modsecurity_conf_t, enable),
    NULL
  },
  {
    ngx_string("modsecurity_transaction_id"),
    NGX_HTTP_LOC_CONF|NGX_HTTP_SRV_CONF|NGX_HTTP_MAIN_CONF|NGX_CONF_1MORE,
    ngx_conf_set_transaction_id,
    NGX_HTTP_LOC_CONF_OFFSET,
    0,
    NULL
  },
  ngx_null_command
};


static ngx_http_module_t ngx_http_modsecurity_ctx = {
    NULL,                                  /* preconfiguration */
    ngx_http_modsecurity_init,             /* postconfiguration */

    ngx_http_modsecurity_create_main_conf, /* create main configuration */
    ngx_http_modsecurity_init_main_conf,   /* init main configuration */

    NULL,                                  /* create server configuration */
    NULL,                                  /* merge server configuration */

    ngx_http_modsecurity_create_conf,      /* create location configuration */
    ngx_http_modsecurity_merge_conf        /* merge location configuration */
};


ngx_module_t ngx_http_modsecurity_module = {
    NGX_MODULE_V1,
    &ngx_http_modsecurity_ctx,             /* module context */
    ngx_http_modsecurity_commands,         /* module directives */
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


static ngx_int_t
ngx_http_modsecurity_init(ngx_conf_t *cf)
{
    ngx_http_handler_pt *h_rewrite;
    ngx_http_handler_pt *h_preaccess;
    ngx_http_handler_pt *h_log;
    ngx_http_core_main_conf_t *cmcf;
    int rc = 0;

    cmcf = ngx_http_conf_get_module_main_conf(cf, ngx_http_core_module);
    if (cmcf == NULL)
    {
        dd("We are not sure how this returns, NGINX doesn't seem to think it will ever be null");
        return NGX_ERROR;
    }
    /**
     *
     * Seems like we cannot do this very same thing with
     * NGX_HTTP_FIND_CONFIG_PHASE. it does not seems to
     * be an array. Our next option is the REWRITE.
     *
     * TODO: check if we can hook prior to NGX_HTTP_REWRITE_PHASE phase.
     *
     */
    h_rewrite = ngx_array_push(&cmcf->phases[NGX_HTTP_REWRITE_PHASE].handlers);
    if (h_rewrite == NULL)
    {
        dd("Not able to create a new NGX_HTTP_REWRITE_PHASE handle");
        return NGX_ERROR;
    }
    *h_rewrite = ngx_http_modsecurity_rewrite_handler;

    /**
     *
     * Processing the request body on the preaccess phase.
     *
     * TODO: check if hook into separated phases is the best thing to do.
     *
     */
    h_preaccess = ngx_array_push(&cmcf->phases[NGX_HTTP_PREACCESS_PHASE].handlers);
    if (h_preaccess == NULL)
    {
        dd("Not able to create a new NGX_HTTP_PREACCESS_PHASE handle");
        return NGX_ERROR;
    }
    *h_preaccess = ngx_http_modsecurity_pre_access_handler;

    /**
     * Process the log phase.
     *
     * TODO: check if the log phase happens like it happens on Apache.
     *       check if last phase will not hold the request.
     *
     */
    h_log = ngx_array_push(&cmcf->phases[NGX_HTTP_LOG_PHASE].handlers);
    if (h_log == NULL)
    {
        dd("Not able to create a new NGX_HTTP_LOG_PHASE handle");
        return NGX_ERROR;
    }
    *h_log = ngx_http_modsecurity_log_handler;


    rc = ngx_http_modsecurity_header_filter_init();
    if (rc != NGX_OK) {
        return rc;
    }

    rc = ngx_http_modsecurity_body_filter_init();
    if (rc != NGX_OK) {
        return rc;
    }

    return NGX_OK;
}


static void *
ngx_http_modsecurity_create_main_conf(ngx_conf_t *cf)
{
    ngx_pool_cleanup_t                *cln;
    ngx_http_modsecurity_main_conf_t  *conf;

    conf = (ngx_http_modsecurity_main_conf_t *) ngx_pcalloc(cf->pool,
                                    sizeof(ngx_http_modsecurity_main_conf_t));

    if (conf == NULL)
    {
        return NGX_CONF_ERROR;
    }

    /*
     * set by ngx_pcalloc():
     *
     *     conf->modsec = NULL;
     *     conf->pool = NULL;
     *     conf->rules_inline = 0;
     *     conf->rules_file = 0;
     *     conf->rules_remote = 0;
     */

    cln = ngx_pool_cleanup_add(cf->pool, 0);
    if (cln == NULL) {
        return NGX_CONF_ERROR;
    }

    cln->handler = ngx_http_modsecurity_cleanup_instance;
    cln->data = conf;

    conf->pool = cf->pool;

    /* Create our ModSecurity instance */
    conf->modsec = msc_init();
    if (conf->modsec == NULL)
    {
        dd("failed to create the ModSecurity instance");
        return NGX_CONF_ERROR;
    }

    /* Provide our connector information to LibModSecurity */
    msc_set_connector_info(conf->modsec, MODSECURITY_NGINX_WHOAMI);
    msc_set_log_cb(conf->modsec, ngx_http_modsecurity_log);

    dd ("main conf created at: '%p', instance is: '%p'", conf, conf->modsec);

    return conf;
}


static char *
ngx_http_modsecurity_init_main_conf(ngx_conf_t *cf, void *conf)
{
    ngx_http_modsecurity_main_conf_t  *mmcf;
    mmcf = (ngx_http_modsecurity_main_conf_t *) conf;

    ngx_log_error(NGX_LOG_NOTICE, cf->log, 0,
                  "%s (rules loaded inline/local/remote: %ui/%ui/%ui)",
                  MODSECURITY_NGINX_WHOAMI, mmcf->rules_inline,
                  mmcf->rules_file, mmcf->rules_remote);

    return NGX_CONF_OK;
}


static void *
ngx_http_modsecurity_create_conf(ngx_conf_t *cf)
{
    ngx_pool_cleanup_t           *cln;
    ngx_http_modsecurity_conf_t  *conf;

    conf = (ngx_http_modsecurity_conf_t *) ngx_pcalloc(cf->pool,
                                         sizeof(ngx_http_modsecurity_conf_t));

    if (conf == NULL)
    {
        dd("Failed to allocate space for ModSecurity configuration");
        return NGX_CONF_ERROR;
    }

    /*
     * set by ngx_pcalloc():
     *
     *     conf->enable = 0;
     *     conf->sanity_checks_enabled = 0;
     *     conf->rules_set = NULL;
     *     conf->pool = NULL;
     *     conf->transaction_id = NULL;
     */

    conf->enable = NGX_CONF_UNSET;
    conf->rules_set = msc_create_rules_set();
    conf->pool = cf->pool;
    conf->transaction_id = NGX_CONF_UNSET_PTR;
#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    conf->sanity_checks_enabled = NGX_CONF_UNSET;
#endif

    cln = ngx_pool_cleanup_add(cf->pool, 0);
    if (cln == NULL) {
        dd("failed to create the ModSecurity configuration cleanup");
        return NGX_CONF_ERROR;
    }

    cln->handler = ngx_http_modsecurity_cleanup_rules;
    cln->data = conf;

    dd ("conf created at: '%p'", conf);

    return conf;
}


static char *
ngx_http_modsecurity_merge_conf(ngx_conf_t *cf, void *parent, void *child)
{
    ngx_http_modsecurity_conf_t *p = parent;
    ngx_http_modsecurity_conf_t *c = child;
#if defined(MODSECURITY_DDEBUG) && (MODSECURITY_DDEBUG)
    ngx_http_core_loc_conf_t *clcf = ngx_http_conf_get_module_loc_conf(cf, ngx_http_core_module);
#endif
    int rules;
    const char *error = NULL;

    dd("merging loc config [%s] - parent: '%p' child: '%p'",
        ngx_str_to_char(clcf->name, cf->pool), parent,
        child);

    dd("                  state - parent: '%d' child: '%d'",
        (int) c->enable, (int) p->enable);

    ngx_conf_merge_value(c->enable, p->enable, 0);
    ngx_conf_merge_ptr_value(c->transaction_id, p->transaction_id, NULL);
#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    ngx_conf_merge_value(c->sanity_checks_enabled, p->sanity_checks_enabled, 0);
#endif

#if defined(MODSECURITY_DDEBUG) && (MODSECURITY_DDEBUG)
    dd("PARENT RULES");
    msc_rules_dump(p->rules_set);
    dd("CHILD RULES");
    msc_rules_dump(c->rules_set);
#endif
    rules = msc_rules_merge(c->rules_set, p->rules_set, &error);

    if (rules < 0) {
        return strdup(error);
    }

#if defined(MODSECURITY_DDEBUG) && (MODSECURITY_DDEBUG)
    dd("NEW CHILD RULES");
    msc_rules_dump(c->rules_set);
#endif
    return NGX_CONF_OK;
}


static void
ngx_http_modsecurity_cleanup_instance(void *data)
{
    ngx_pool_t                        *old_pool;
    ngx_http_modsecurity_main_conf_t  *mmcf;

    mmcf = (ngx_http_modsecurity_main_conf_t *) data;

    dd("deleting a main conf -- instance is: \"%p\"", mmcf->modsec);

    old_pool = ngx_http_modsecurity_pcre_malloc_init(mmcf->pool);
    msc_cleanup(mmcf->modsec);
    ngx_http_modsecurity_pcre_malloc_done(old_pool);
}


static void
ngx_http_modsecurity_cleanup_rules(void *data)
{
    ngx_pool_t                   *old_pool;
    ngx_http_modsecurity_conf_t  *mcf;

    mcf = (ngx_http_modsecurity_conf_t *) data;

    dd("deleting a loc conf -- RuleSet is: \"%p\"", mcf->rules_set);

    old_pool = ngx_http_modsecurity_pcre_malloc_init(mcf->pool);
    msc_rules_cleanup(mcf->rules_set);
    ngx_http_modsecurity_pcre_malloc_done(old_pool);
}


/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
