

/* TODO : check that this is correct */

u_char *
ndk_map_uri_to_path_add_suffix (ngx_http_request_t *r, ngx_str_t *path, ngx_str_t *suffix, ngx_int_t dot)
{
    size_t      root_size;
    u_char     *p;

    if (suffix->len) {

        if (dot) {

            p = ngx_http_map_uri_to_path (r, path, &root_size, suffix->len + 1);

            if (p == NULL)
                return  NULL;

            *p = '.';
            p++;

        } else {

            p = ngx_http_map_uri_to_path (r, path, &root_size, suffix->len);

            if (p == NULL)
                return  NULL;
        }       

        path->len--;

        p = ngx_cpymem (p, suffix->data, suffix->len);
        *p = '\0';

        return  p;  
    }

    p = ngx_http_map_uri_to_path (r, path, &root_size, 0);

    path->len--;

    return  p;
}

