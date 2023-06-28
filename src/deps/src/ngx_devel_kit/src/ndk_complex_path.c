

ndk_http_complex_path_value_t     ndk_empty_http_complex_path_value = {{0,NULL},0};


ngx_int_t
ndk_http_complex_path_value_compile (ngx_conf_t *cf, ngx_http_complex_value_t *cv, ngx_str_t *value, ngx_uint_t prefix)
{
    ngx_http_compile_complex_value_t   ccv;

    ngx_memzero (&ccv, sizeof(ngx_http_compile_complex_value_t));

    ccv.cf = cf;
    ccv.value = value;
    ccv.complex_value = cv;

    switch (prefix) {

    case    1 :
        ccv.root_prefix = 1;
        break;

    case    2 :
        ccv.conf_prefix = 1;
        break;
    }

    ndk_path_to_dir_safe (value, 1, 0);

    if (!value->len)
        return  NGX_OK;

    return  ngx_http_compile_complex_value (&ccv);
}



ngx_array_t *
ndk_http_complex_path_create_compile (ngx_conf_t *cf, ngx_str_t *path, ngx_uint_t prefix)
{
    ndk_http_complex_path_elt_t     *cpe;
    ngx_array_t                     *a;
    ngx_int_t                        n;
    u_char                          *m, *s, *e;
    ngx_str_t                        value;

    n = ndk_strcntc (path, ':') + 1;

    a = ngx_array_create (cf->pool, n, sizeof (ndk_http_complex_path_elt_t));
    if (a == NULL) {
        return  NULL;
    }

    s = path->data;
    e = s + path->len;


    while (s < e) {

        m = s;

        while (m < e && *m != ':') m++;

        if (m == s) {
            s = m+1;
            continue;
        }

        cpe = ngx_array_push (a);
        if (cpe == NULL) {
            return  NULL;
        }

        if (*s == '#') {
            s++;
            cpe->dynamic = 1;
        } else {
            cpe->dynamic = 0;
        }

        value.data = s;
        value.len = m - s;

        if (ndk_http_complex_path_value_compile (cf, &cpe->val, &value, prefix) == NGX_ERROR)
            return  NULL;

        s = m+1;
    }

    return  a;
}




char *
ndk_conf_set_http_complex_path_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t                   *path;
    ngx_array_t                 *a;
    ngx_conf_post_t             *post;
    ndk_http_complex_path_t     *cp;

    cp = (ndk_http_complex_path_t *) (p + cmd->offset);

    if (cp->a != NGX_CONF_UNSET_PTR) {
        return  "is duplicate";
    }

    path = cf->args->elts;
    path++;

    cp->a = ndk_http_complex_path_create_compile (cf, path, cp->prefix);
    if (cp->a == NULL)
        /* TODO : log */
        return  NGX_CONF_ERROR;

    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}



