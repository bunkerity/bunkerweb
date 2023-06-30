

/* TODO : generalize this into a generic list module, with weight */


typedef struct {
    ngx_uint_t      weight;
    ngx_str_t       s;
    ngx_conf_t     *cf;
} ndk_upstream_list_parse_t;



static ngx_int_t
ndk_upstream_list_parse_weight (ndk_upstream_list_parse_t *ulp)
{
    size_t      i;
    ngx_str_t   *s;

    s = &ulp->s;

    for (i=0; i<s->len; i++) {

        if (s->data[i] < '0' || s->data[i] > '9')
            break;
    }

    if (!i) {
        ulp->weight = 1;
        return  NGX_OK;
    }

    if (i == s->len) {
        ngx_conf_log_error (NGX_LOG_EMERG, ulp->cf, 0,
            "upstream list just consists of number \"%V\"", s);

        return  NGX_ERROR;
    }

    if (s->data[i] != ':') {
        ngx_conf_log_error (NGX_LOG_EMERG, ulp->cf, 0,
            "upstream list not correct format \"%V\"", s);

        return  NGX_ERROR;
    }


    ulp->weight = ngx_atoi (s->data, i);

    s->data += (i + 1);
    s->len -= (i + 1);

    return  NGX_OK;
}



static char *
ndk_upstream_list (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    /* TODO : change this for getting upstream pointer if available */

    ngx_uint_t                   buckets, count, i, j;
    ngx_str_t                   *value, **bucket, *us;
    ngx_array_t                 *ula;
    ndk_upstream_list_t         *ul, *ule;
    ndk_upstream_list_parse_t    ulp;

    ndk_http_main_conf_t        *mcf;

    mcf = ngx_http_conf_get_module_main_conf (cf, ndk_http_module);

    ula = mcf->upstreams;

    /* create array of upstream lists it doesn't already exist */

    if (ula == NULL) {

        ula = ngx_array_create (cf->pool, 4, sizeof (ndk_upstream_list_t));
        if (ula == NULL)
            return  NGX_CONF_ERROR;

        mcf->upstreams = ula;
    }


    /* check to see if the list already exists */

    value = cf->args->elts;
    value++;

    ul = ula->elts;
    ule = ul + ula->nelts;

    for ( ; ul<ule; ul++) {

        if (ul->name.len == value->len &&
            ngx_strncasecmp (ul->name.data, value->data, value->len) == 0) {

            ngx_conf_log_error (NGX_LOG_EMERG, cf, 0,
                           "duplicate upstream list name \"%V\"", value);

            return  NGX_CONF_ERROR;
        }
    }


    /* create a new list */

    ul = ngx_array_push (ula);
    if (ul == NULL)
        return  NGX_CONF_ERROR;

    ul->name = *value;



    /* copy all the upstream names */

    count = cf->args->nelts - 2;

    us = ngx_palloc (cf->pool, count * sizeof (ngx_str_t));
    if (us == NULL)
        return  NGX_CONF_ERROR;

    ngx_memcpy (us, value + 1, count * sizeof (ngx_str_t));


    /* calculate the total number of buckets */

    buckets = 0;

    ulp.cf = cf;

    for (i=0; i<count; i++, us++) {

        ulp.s = *us;

        if (ndk_upstream_list_parse_weight (&ulp) != NGX_OK)
            return  NGX_CONF_ERROR;

        buckets += ulp.weight;
    }


    /* allocate space for all buckets */

    bucket = ngx_palloc (cf->pool, buckets * sizeof (ngx_str_t *));
    if (bucket == NULL)
        return  NGX_CONF_ERROR;

    ul->elts = bucket;
    ul->nelts = buckets;


    /* set values for each bucket */

    us -= count;

    for (i=0; i<count; i++, us++) {

        ulp.s = *us;

        if (ndk_upstream_list_parse_weight (&ulp) != NGX_OK)
            return  NGX_CONF_ERROR;

        us->data = ulp.s.data;
        us->len = ulp.s.len;

        /* TODO : check format of upstream */
        /* TODO : add automatic adding of http:// in upstreams? */

        for (j=0; j<ulp.weight; j++, bucket++) {

            *bucket = us;
        }
    }

    return  NGX_CONF_OK;
}


ndk_upstream_list_t *
ndk_get_upstream_list (ndk_http_main_conf_t *mcf, u_char *data, size_t len)
{
    ndk_upstream_list_t         *ul, *ule;
    ngx_array_t                 *ua = mcf->upstreams;

    if (ua == NULL) {
        return NULL;
    }

    ul = ua->elts;
    ule = ul + ua->nelts;

    for (; ul < ule; ul++) {
        if (ul->name.len == len && ngx_strncasecmp(ul->name.data, data, len) == 0)
        {
            return ul;
        }
    }

    return NULL;
}

