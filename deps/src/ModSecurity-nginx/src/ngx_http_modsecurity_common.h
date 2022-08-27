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


#ifndef _NGX_HTTP_MODSECURITY_COMMON_H_INCLUDED_
#define _NGX_HTTP_MODSECURITY_COMMON_H_INCLUDED_

#include <nginx.h>
#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

#include <modsecurity/modsecurity.h>
#include <modsecurity/transaction.h>


/* #define MSC_USE_RULES_SET 1 */

#if defined(MODSECURITY_CHECK_VERSION)
#if MODSECURITY_VERSION_NUM >= 304010
#define MSC_USE_RULES_SET 1
#endif
#endif

#if defined(MSC_USE_RULES_SET)
#include <modsecurity/rules_set.h>
#else
#include <modsecurity/rules.h>
#endif


/**
 * TAG_NUM:
 *
 * Alpha  - 001
 * Beta   - 002
 * Dev    - 010
 * Rc1    - 051
 * Rc2    - 052
 * ...    - ...
 * Release- 100
 *
 */

#define MODSECURITY_NGINX_MAJOR "1"
#define MODSECURITY_NGINX_MINOR "0"
#define MODSECURITY_NGINX_PATCHLEVEL "3"
#define MODSECURITY_NGINX_TAG ""
#define MODSECURITY_NGINX_TAG_NUM "100"

#define MODSECURITY_NGINX_VERSION MODSECURITY_NGINX_MAJOR "." \
    MODSECURITY_NGINX_MINOR "." MODSECURITY_NGINX_PATCHLEVEL \
    MODSECURITY_NGINX_TAG

#define MODSECURITY_NGINX_VERSION_NUM MODSECURITY_NGINX_MAJOR \
    MODSECURITY_NGINX_MINOR MODSECURITY_NGINX_PATCHLEVEL \
    MODSECURITY_NGINX_TAG_NUM

#define MODSECURITY_NGINX_WHOAMI "ModSecurity-nginx v" \
    MODSECURITY_NGINX_VERSION

typedef struct {
    ngx_str_t name;
    ngx_str_t value;
} ngx_http_modsecurity_header_t;


typedef struct {
    ngx_http_request_t *r;
    Transaction *modsec_transaction;
    ModSecurityIntervention *delayed_intervention;

#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    /*
     * Should be filled with the headers that were sent to ModSecurity.
     *
     * The idea is to compare this set of headers with the headers that were
     * sent to the client. This check was placed because we don't have control
     * over other modules, thus, we may partially inspect the headers.
     *
     */
    ngx_array_t *sanity_headers_out;
#endif

    unsigned waiting_more_body:1;
    unsigned body_requested:1;
    unsigned processed:1;
    unsigned logged:1;
    unsigned intervention_triggered:1;
} ngx_http_modsecurity_ctx_t;


typedef struct {
    void                      *pool;
    ModSecurity               *modsec;
    ngx_uint_t                 rules_inline;
    ngx_uint_t                 rules_file;
    ngx_uint_t                 rules_remote;
} ngx_http_modsecurity_main_conf_t;


typedef struct {
    void                      *pool;
    /* RulesSet or Rules */
    void                      *rules_set;

    ngx_flag_t                 enable;
#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
    ngx_flag_t                 sanity_checks_enabled;
#endif

    ngx_http_complex_value_t  *transaction_id;
} ngx_http_modsecurity_conf_t;


typedef ngx_int_t (*ngx_http_modsecurity_resolv_header_pt)(ngx_http_request_t *r, ngx_str_t name, off_t offset);

typedef struct {
    ngx_str_t name;
    ngx_uint_t offset;
    ngx_http_modsecurity_resolv_header_pt resolver;
} ngx_http_modsecurity_header_out_t;


extern ngx_module_t ngx_http_modsecurity_module;

/* ngx_http_modsecurity_module.c */
int ngx_http_modsecurity_process_intervention (Transaction *transaction, ngx_http_request_t *r, ngx_int_t early_log);
ngx_http_modsecurity_ctx_t *ngx_http_modsecurity_create_ctx(ngx_http_request_t *r);
char *ngx_str_to_char(ngx_str_t a, ngx_pool_t *p);
#if (NGX_PCRE2)
#define ngx_http_modsecurity_pcre_malloc_init(x) NULL
#define ngx_http_modsecurity_pcre_malloc_done(x) (void)x
#else
ngx_pool_t *ngx_http_modsecurity_pcre_malloc_init(ngx_pool_t *pool);
void ngx_http_modsecurity_pcre_malloc_done(ngx_pool_t *old_pool);
#endif

/* ngx_http_modsecurity_body_filter.c */
ngx_int_t ngx_http_modsecurity_body_filter_init(void);
ngx_int_t ngx_http_modsecurity_body_filter(ngx_http_request_t *r, ngx_chain_t *in);

/* ngx_http_modsecurity_header_filter.c */
ngx_int_t ngx_http_modsecurity_header_filter_init(void);
ngx_int_t ngx_http_modsecurity_header_filter(ngx_http_request_t *r);
#if defined(MODSECURITY_SANITY_CHECKS) && (MODSECURITY_SANITY_CHECKS)
int ngx_http_modsecurity_store_ctx_header(ngx_http_request_t *r, ngx_str_t *name, ngx_str_t *value);
#endif

/* ngx_http_modsecurity_log.c */
void ngx_http_modsecurity_log(void *log, const void* data);
ngx_int_t ngx_http_modsecurity_log_handler(ngx_http_request_t *r);

/* ngx_http_modsecurity_pre_access.c */
ngx_int_t ngx_http_modsecurity_pre_access_handler(ngx_http_request_t *r);

/* ngx_http_modsecurity_rewrite.c */
ngx_int_t ngx_http_modsecurity_rewrite_handler(ngx_http_request_t *r);


#endif /* _NGX_HTTP_MODSECURITY_COMMON_H_INCLUDED_ */
