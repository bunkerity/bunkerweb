


ngx_int_t
ndk_http_complex_value_compile (ngx_conf_t *cf, ngx_http_complex_value_t *cv, ngx_str_t *value)
{
    ngx_http_compile_complex_value_t   ccv;

    ngx_memzero (&ccv, sizeof(ngx_http_compile_complex_value_t));

    ccv.cf = cf;
    ccv.value = value;
    ccv.complex_value = cv;

    return  ngx_http_compile_complex_value (&ccv);
}




ngx_array_t *
ndk_http_complex_value_array_create (ngx_conf_t *cf, char **s, ngx_int_t n)
{
    ngx_int_t                    i;
    ngx_http_complex_value_t    *cv;
    ngx_array_t                 *a;
    ngx_str_t                    value;

    a = ngx_array_create (cf->pool, n, sizeof (ngx_http_complex_value_t));
    if (a == NULL)
        return  NULL;


    for (i=0; i<n; i++, s++) {

        cv = ngx_array_push (a);

        value.data = (u_char *) *s;
        value.len = strlen (*s);

        if (ndk_http_complex_value_compile (cf, cv, &value))
            return  NULL;
    }

    return  a;
}



ngx_int_t
ndk_http_complex_value_array_compile (ngx_conf_t *cf, ngx_array_t *a)
{
    ngx_uint_t                  i;
    ngx_http_complex_value_t   *cv;

    if (a == NULL || a == NGX_CONF_UNSET_PTR) {
        return  NGX_ERROR;
    }

    cv = a->elts;

    for (i=0; i<a->nelts; i++, cv++) {

        if (ndk_http_complex_value_compile (cf, cv, &cv->value))
            return  NGX_ERROR;
    }

    return  NGX_OK;
}



char *
ndk_conf_set_http_complex_value_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_http_complex_value_t    *cv;
    ngx_str_t                   *value;
    ngx_conf_post_t             *post;

    cv = (ngx_http_complex_value_t *) (p + cmd->offset);

    if (cv->value.data) {
        return "is duplicate";
    }

    value = cf->args->elts;

    if (ndk_http_complex_value_compile (cf, cv, value + 1))
        return  NGX_CONF_ERROR;

    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, cv);
    }

    return  NGX_CONF_OK;
}



char *
ndk_conf_set_http_complex_value_array_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char *p = conf;

    ngx_str_t                   *value;
    ngx_http_complex_value_t    *cv;
    ngx_array_t                **a;
    ngx_conf_post_t             *post;
    ngx_uint_t                   i, alloc;

    a = (ngx_array_t **) (p + cmd->offset);

    if (*a == NULL || *a == NGX_CONF_UNSET_PTR) {

        alloc = cf->args->nelts > 4 ? cf->args->nelts : 4;

        *a = ngx_array_create (cf->pool, alloc, sizeof (ngx_http_complex_value_t));
        if (*a == NULL) {
            return  NGX_CONF_ERROR;
        }
    }

    value = cf->args->elts;

    for (i=1; i<cf->args->nelts; i++) {

        cv = ngx_array_push (*a);
        if (cv == NULL) {
            return  NGX_CONF_ERROR;
        }

        if (ndk_http_complex_value_compile (cf, cv, &value[i]) == NGX_ERROR)
            return  NGX_CONF_ERROR;
    }


    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}


char *
ndk_conf_set_http_complex_keyval_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char *p = conf;

    ngx_str_t                   *value;
    ndk_http_complex_keyval_t   *ckv;
    ngx_array_t                **a;
    ngx_conf_post_t             *post;
    ngx_int_t                    alloc;

    a = (ngx_array_t **) (p + cmd->offset);

    if (*a == NULL || *a == NGX_CONF_UNSET_PTR) {

        alloc = cf->args->nelts > 4 ? cf->args->nelts : 4;

        *a = ngx_array_create (cf->pool, alloc, sizeof (ndk_http_complex_keyval_t));
        if (*a == NULL) {
            return  NGX_CONF_ERROR;
        }
    }

    ckv = ngx_array_push (*a);
    if (ckv == NULL) {
        return  NGX_CONF_ERROR;
    }

    value = cf->args->elts;

    ckv->key = value[1];

    if (ndk_http_complex_value_compile (cf, &ckv->value, &value[2]) == NGX_ERROR)
        return  NGX_CONF_ERROR;

    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}

/* TODO : complex keyval1 */
