

char *
ndk_conf_set_regex_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t               *value;
    ngx_conf_post_t         *post;
    ngx_regex_elt_t         *re;   
    ngx_regex_compile_t      rc;
    u_char                   errstr[NGX_MAX_CONF_ERRSTR];

    re = (ngx_regex_elt_t *) (p + cmd->offset);

    if (re->name) {
        return  "is duplicate";
    }

    value = cf->args->elts;
    value++;

    ndk_zerov (rc);

    rc.pool = cf->pool;
    rc.err.len = NGX_MAX_CONF_ERRSTR;
    rc.err.data = errstr;
    rc.pattern = *value;

    if (ngx_regex_compile(&rc) != NGX_OK) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "%V", &rc.err);
        return NGX_CONF_ERROR;
    }

    re->regex = rc.regex;
    re->name = value->data;

    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, re);
    }

    return  NGX_CONF_OK;
}
 

char *
ndk_conf_set_regex_caseless_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t               *value;
    ngx_conf_post_t         *post;
    ngx_regex_elt_t         *re;   
    ngx_regex_compile_t      rc;
    u_char                   errstr[NGX_MAX_CONF_ERRSTR];

    re = (ngx_regex_elt_t *) (p + cmd->offset);

    if (re->name) {
        return  "is duplicate";
    }

    value = cf->args->elts;
    value++;

    ndk_zerov (rc);

    rc.pool = cf->pool;
    rc.err.len = NGX_MAX_CONF_ERRSTR;
    rc.err.data = errstr;
    rc.pattern = *value;
    rc.options = NGX_REGEX_CASELESS;

    if (ngx_regex_compile(&rc) != NGX_OK) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "%V", &rc.err);
        return NGX_CONF_ERROR;
    }

    re->regex = rc.regex;
    re->name = value->data;

    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, re);
    }

    return  NGX_CONF_OK;
}



char *
ndk_conf_set_regex_array_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t               *value;
    ngx_conf_post_t         *post;
    ngx_array_t            **a;
    ngx_regex_elt_t         *re;   
    ngx_regex_compile_t      rc;
    ngx_uint_t               i, n = 0;
    u_char                   errstr[NGX_MAX_CONF_ERRSTR];

    a = (ngx_array_t **) (p + cmd->offset);

    if (*a != NGX_CONF_UNSET_PTR) {

        n = cf->args->nelts > 4 ? cf->args->nelts : 4;

        *a = ngx_array_create (cf->pool, n, sizeof (ngx_regex_elt_t));
        if (*a == NULL) {
            return  NGX_CONF_ERROR;
        }
    }

    ndk_zerov (rc);

    rc.pool = cf->pool;
    rc.err.len = NGX_MAX_CONF_ERRSTR;
    rc.err.data = errstr;

    value = cf->args->elts;
    value++;

    for (i=0; i<n; i++, value++) {

        re = ngx_array_push (*a);
        if (re == NULL)
            return  NGX_CONF_ERROR;

        rc.pattern = *value;

        if (ngx_regex_compile(&rc) != NGX_OK) {
            ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "%V", &rc.err);
            return NGX_CONF_ERROR;
        }

        re->regex = rc.regex;
        re->name = value->data;
    }


    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}



char *
ndk_conf_set_regex_array_caseless_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t               *value;
    ngx_conf_post_t         *post;
    ngx_array_t            **a;
    ngx_regex_elt_t         *re;   
    ngx_regex_compile_t      rc;
    ngx_uint_t               i, n = 0;
    u_char                   errstr[NGX_MAX_CONF_ERRSTR];

    a = (ngx_array_t **) (p + cmd->offset);

    if (*a != NGX_CONF_UNSET_PTR) {

        n = cf->args->nelts > 4 ? cf->args->nelts : 4;

        *a = ngx_array_create (cf->pool, n, sizeof (ngx_regex_elt_t));
        if (*a == NULL) {
            return  NGX_CONF_ERROR;
        }
    }

    ndk_zerov (rc);

    rc.pool = cf->pool;
    rc.err.len = NGX_MAX_CONF_ERRSTR;
    rc.err.data = errstr;

    value = cf->args->elts;
    value++;

    for (i=0; i<n; i++, value++) {

        re = ngx_array_push (*a);
        if (re == NULL)
            return  NGX_CONF_ERROR;

        rc.pattern = *value;
        rc.options = NGX_REGEX_CASELESS;

        if (ngx_regex_compile(&rc) != NGX_OK) {
            ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, "%V", &rc.err);
            return NGX_CONF_ERROR;
        }

        re->regex = rc.regex;
        re->name = value->data;
    }


    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}

