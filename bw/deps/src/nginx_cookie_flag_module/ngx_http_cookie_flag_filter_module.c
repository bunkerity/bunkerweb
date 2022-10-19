#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>

#define NUM_FLAGS 3
#define MIN_ARGS  3

typedef struct {
    ngx_str_t cookie_name;
    ngx_flag_t httponly;
    ngx_flag_t secure;
    ngx_flag_t samesite;
    ngx_flag_t samesite_lax;
    ngx_flag_t samesite_strict;
} ngx_http_cookie_t;

typedef struct {
    ngx_array_t *cookies;
} ngx_http_cookie_flag_filter_loc_conf_t;

static char *ngx_http_cookie_flag_filter_cmd(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
static void *ngx_http_cookie_flag_filter_create_loc_conf(ngx_conf_t *cf);
static char *ngx_http_cookie_flag_filter_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child);
static ngx_int_t ngx_http_cookie_flag_filter_init(ngx_conf_t *cf);
static ngx_int_t ngx_http_cookie_flag_filter_append(ngx_http_request_t *r, ngx_http_cookie_t *flag, ngx_table_elt_t *header);
static ngx_int_t ngx_http_cookie_flag_filter_handler(ngx_http_request_t *r);
static size_t ngx_char_pos(ngx_str_t str, u_char ch);
static u_char *ngx_get_arg_name(ngx_pool_t *pool, ngx_str_t src);

static size_t ngx_char_pos(ngx_str_t str, u_char ch) {

    char *pos = NULL;
    size_t ind = 0;
    pos = strchr((char *) str.data, (int) ch);
    if (pos != NULL) {
        ind = (size_t) (pos - (char *) str.data);
    }
    return ind;

}

static u_char *ngx_get_arg_name(ngx_pool_t *pool, ngx_str_t src) {

    u_char  *dst;
    size_t pos;

    pos = ngx_char_pos(src, '=');

    if(pos) {
        dst = ngx_pnalloc(pool, pos + 1);
        if (dst == NULL) {
            return NULL;
        }
        ngx_memcpy(dst, src.data, pos);
        return dst;
    } else {
        return src.data;
    }

}

static ngx_command_t ngx_http_cookie_flag_filter_commands[] = {

    /* set cookie flag directive */
    { ngx_string("set_cookie_flag"),
      NGX_HTTP_SRV_CONF|NGX_HTTP_LOC_CONF|NGX_CONF_1MORE,
      ngx_http_cookie_flag_filter_cmd,
      NGX_HTTP_LOC_CONF_OFFSET,
      0,
      NULL
    },

    ngx_null_command

};

static ngx_http_module_t ngx_http_cookie_flag_filter_module_ctx = {
    NULL, /* preconfiguration */
    ngx_http_cookie_flag_filter_init, /* postconfiguration */

    NULL, /* create main configuration */
    NULL, /* init main configuration */

    NULL, /* create server configuration */
    NULL, /* merge server configuration */

    ngx_http_cookie_flag_filter_create_loc_conf, /* create location configuration */
    ngx_http_cookie_flag_filter_merge_loc_conf  /* merge location configuration */
};

ngx_module_t ngx_http_cookie_flag_filter_module = {
    NGX_MODULE_V1,
    &ngx_http_cookie_flag_filter_module_ctx, /* module context */
    ngx_http_cookie_flag_filter_commands,    /* module directives */
    NGX_HTTP_MODULE,                    /* module type */
    NULL,                               /* init master */
    NULL,                               /* init module */
    NULL,                               /* init process */
    NULL,                               /* init thread */
    NULL,                               /* exit thread */
    NULL,                               /* exit process */
    NULL,                               /* exit master */
    NGX_MODULE_V1_PADDING
};

static ngx_http_output_header_filter_pt ngx_http_next_header_filter;

static char *
ngx_http_cookie_flag_filter_cmd(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{

    ngx_http_cookie_flag_filter_loc_conf_t *flcf = conf;

    ngx_http_cookie_t *cookie, tmp;
    ngx_str_t *value;
    ngx_uint_t i, j;

    value = cf->args->elts;

    if (cf->args->nelts > (NUM_FLAGS + 2) || cf->args->nelts < MIN_ARGS) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "The number of arguments is incorrect");
        return NGX_CONF_ERROR;
    }

    // check on duplication
    if (cf->args->nelts > MIN_ARGS) {
        for (i = MIN_ARGS; i < cf->args->nelts; i++) {
            for (j = MIN_ARGS - 1; j < i; j++) {
                ngx_log_debug2(NGX_LOG_DEBUG_HTTP, cf->log, 0, "filter http_cookie_flag - comparasion \"%V\" and \"%V\"", &value[i], &value[j]);
                u_char *first = ngx_get_arg_name(cf->pool, value[j]);
                u_char *second = ngx_get_arg_name(cf->pool, value[i]);
                if (ngx_strcasecmp(first, second) == 0) {
                    ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "Duplicate flag \"%s\" (%V) detected", second, &value[i]);
                    return NGX_CONF_ERROR;
                }
            }
        }
    }

    if (flcf->cookies == NULL) {
        flcf->cookies = ngx_array_create(cf->pool, 1, sizeof(ngx_http_cookie_t));
        if (flcf->cookies == NULL) {
            return NGX_CONF_ERROR;
        }
    } else {
        // check whether cookie name has already set
        cookie = flcf->cookies->elts;
        for (i = 0; i < flcf->cookies->nelts; i++) {
            if (ngx_strncasecmp(cookie[i].cookie_name.data, value[1].data, value[1].len) == 0) {
                return "The cookie value has already set in previous directives";
            }
        }
    }

    cookie = ngx_array_push(flcf->cookies);
    if (cookie == NULL) {
        return NGX_CONF_ERROR;
    }

    // set cookie name
    cookie->cookie_name.data = value[1].data;
    cookie->cookie_name.len = value[1].len;
    cookie->httponly = 0;
    cookie->secure = 0;
    cookie->samesite = 0;
    cookie->samesite_lax = 0;
    cookie->samesite_strict = 0;

    // normalize and check 2nd and 3rd parameters
    for (i = 2; i < cf->args->nelts; i++) {
        if (ngx_strncasecmp(value[i].data, (u_char *) "httponly", 8) == 0 && value[i].len == 8) {
            cookie->httponly = 1;
        } else if (ngx_strncasecmp(value[i].data, (u_char *) "secure", 6) == 0 && value[i].len == 6) {
            cookie->secure = 1;
        } else if (ngx_strncasecmp(value[i].data, (u_char *) "samesite", 8) == 0 && value[i].len == 8) {
            cookie->samesite = 1;
        } else if (ngx_strncasecmp(value[i].data, (u_char *) "samesite=lax", 12) == 0 && value[i].len == 12) {
            cookie->samesite_lax = 1;
        } else if (ngx_strncasecmp(value[i].data, (u_char *) "samesite=strict", 15) == 0 && value[i].len == 15) {
            cookie->samesite_strict = 1;
        } else {
            ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "The parameter value \"%V\" is incorrect", &value[i]);
            return NGX_CONF_ERROR;
        }
    }

    // move default settings to the end of array
    cookie = flcf->cookies->elts;
    for (i = 0; i < flcf->cookies->nelts; i++) {
        if (ngx_strncasecmp(cookie[i].cookie_name.data, (u_char *) "*", 1) == 0 && i < flcf->cookies->nelts - 1) {
            tmp = cookie[flcf->cookies->nelts - 1];
            cookie[flcf->cookies->nelts - 1] = cookie[i];
            cookie[i] = tmp;
        }
    }

    return NGX_CONF_OK;
}

static void *
ngx_http_cookie_flag_filter_create_loc_conf(ngx_conf_t *cf)
{
    ngx_http_cookie_flag_filter_loc_conf_t *conf;
    conf = ngx_pcalloc(cf->pool, sizeof(ngx_http_cookie_flag_filter_loc_conf_t));
    if (conf == NULL) {
        return NULL;
    }

    return conf;
}

static char *
ngx_http_cookie_flag_filter_merge_loc_conf(ngx_conf_t *cf, void *parent, void *child)
{
    ngx_http_cookie_flag_filter_loc_conf_t *prev = parent;
    ngx_http_cookie_flag_filter_loc_conf_t *conf = child;

    if (conf->cookies == NULL) {
        conf->cookies = prev->cookies;
    }

    return NGX_CONF_OK;
}

static ngx_int_t
ngx_http_cookie_flag_filter_init(ngx_conf_t *cf)
{

    ngx_http_next_header_filter = ngx_http_top_header_filter;
    ngx_http_top_header_filter = ngx_http_cookie_flag_filter_handler;

    return NGX_OK;
}

static ngx_int_t
ngx_http_cookie_flag_filter_append(ngx_http_request_t *r, ngx_http_cookie_t *cookie, ngx_table_elt_t *header)
{
    ngx_str_t tmp;

    if (cookie->httponly == 1 && ngx_strcasestrn(header->value.data, "; HttpOnly", 10 - 1) == NULL) {
        tmp.data = ngx_pnalloc(r->pool, header->value.len + sizeof("; HttpOnly") - 1);
        if (tmp.data == NULL) {
            return NGX_ERROR;
        }
        tmp.len = ngx_sprintf(tmp.data, "%V; HttpOnly", &header->value) - tmp.data;
        header->value.data = tmp.data;
        header->value.len = tmp.len;
    }

    if (cookie->secure == 1 && ngx_strcasestrn(header->value.data, "; secure", 8 - 1) == NULL) {
        tmp.data = ngx_pnalloc(r->pool, header->value.len + sizeof("; secure") - 1);
        if (tmp.data == NULL) {
            return NGX_ERROR;
        }
        tmp.len = ngx_sprintf(tmp.data, "%V; secure", &header->value) - tmp.data;
        header->value.data = tmp.data;
        header->value.len = tmp.len;
    }

    if (cookie->samesite == 1 && ngx_strcasestrn(header->value.data, "; SameSite", 10 - 1) == NULL) {
        tmp.data = ngx_pnalloc(r->pool, header->value.len + sizeof("; SameSite") - 1);
        if (tmp.data == NULL) {
            return NGX_ERROR;
        }
        tmp.len = ngx_sprintf(tmp.data, "%V; SameSite", &header->value) - tmp.data;
        header->value.data = tmp.data;
        header->value.len = tmp.len;
    }

    if (cookie->samesite_lax == 1 && ngx_strcasestrn(header->value.data, "; SameSite=Lax", 14 - 1) == NULL) {
        tmp.data = ngx_pnalloc(r->pool, header->value.len + sizeof("; SameSite=Lax") - 1);
        if (tmp.data == NULL) {
            return NGX_ERROR;
        }
        tmp.len = ngx_sprintf(tmp.data, "%V; SameSite=Lax", &header->value) - tmp.data;
        header->value.data = tmp.data;
        header->value.len = tmp.len;
    }

    if (cookie->samesite_strict == 1 && ngx_strcasestrn(header->value.data, "; SameSite=Strict", 17 - 1) == NULL) {
        tmp.data = ngx_pnalloc(r->pool, header->value.len + sizeof("; SameSite=Strict") - 1);
        if (tmp.data == NULL) {
            return NGX_ERROR;
        }
        tmp.len = ngx_sprintf(tmp.data, "%V; SameSite=Strict", &header->value) - tmp.data;
        header->value.data = tmp.data;
        header->value.len = tmp.len;
    }

    return NGX_OK;
}

static ngx_int_t
ngx_http_cookie_flag_filter_handler(ngx_http_request_t *r)
{
    ngx_http_cookie_flag_filter_loc_conf_t *flcf;
    ngx_http_cookie_t *cookie;
    ngx_uint_t i, j;
    ngx_list_part_t *part;
    ngx_table_elt_t *header;

    flcf = ngx_http_get_module_loc_conf(r, ngx_http_cookie_flag_filter_module);

    if (flcf->cookies == NULL) {
        ngx_log_debug0(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag is disabled");
        return ngx_http_next_header_filter(r);
    }

    cookie = flcf->cookies->elts;

    if (flcf->cookies->nelts != 0) {
        ngx_log_debug0(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag is enabled");
    }

    // Checking whether Set-Cookie header is present
    part = &r->headers_out.headers.part;
    header = part->elts;
    for (i = 0; /* void */; i++) {
        if (i >= part->nelts) {
            if (part->next == NULL) {
                break;
            }

            part = part->next;
            header = part->elts;
            i = 0;
        }

        if (ngx_strncasecmp(header[i].key.data, (u_char *) "set-cookie", 10) == 0) {
            ngx_log_debug2(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag - before: \"%V: %V\"", &header[i].key, &header[i].value);

            // for each security cookie we check whether preset it within Set-Cookie value. If not then we append.
            for (j = 0; j < flcf->cookies->nelts; j++) {

                if (ngx_strncasecmp(cookie[j].cookie_name.data, (u_char *) "*", 1) != 0) {
                    // append "=" to the security cookie name. The result will be something like "cookie_name="
                    char *cookie_name = ngx_pnalloc(r->pool,  sizeof("=") - 1 + cookie[j].cookie_name.len);
                    if (cookie_name == NULL) {
                        return NGX_ERROR;
                    }
                    strcpy(cookie_name, (char *) cookie[j].cookie_name.data);
                    strcat(cookie_name, "=");

                    // if Set-Cookie contains a cookie from settings
                    if (ngx_strcasestrn(header[i].value.data, cookie_name, strlen(cookie_name) - 1) != NULL) {
                        ngx_log_debug1(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag - add flags for cookie \"%V\"", &cookie[j].cookie_name);
                        ngx_int_t res = ngx_http_cookie_flag_filter_append(r, &cookie[j], &header[i]);
                        if (res != NGX_OK) {
                            return NGX_ERROR;
                        }
                        break; // otherwise default value will be added
                    }
                } else if (ngx_strncasecmp(cookie[j].cookie_name.data, (u_char *) "*", 1) == 0) {
                    ngx_log_debug0(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag - add default cookie flags");
                    ngx_int_t res = ngx_http_cookie_flag_filter_append(r, &cookie[j], &header[i]);
                    if (res != NGX_OK) {
                        return NGX_ERROR;
                    }
                }
            }

            ngx_log_debug2(NGX_LOG_DEBUG_HTTP, r->connection->log, 0, "filter http_cookie_flag - after: \"%V: %V\"", &header[i].key, &header[i].value);
        }
    }

    return ngx_http_next_header_filter(r);
}
