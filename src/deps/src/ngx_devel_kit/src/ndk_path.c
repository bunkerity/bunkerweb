


/* This function cleans a path to its most basic form, performing the following transformations :
 *
 *  - ./ -> [empty]
 *  - // -> /
 *  - /base/parent/../ -> /base/
 *
 * If possible, it leaves the original string in place and does not copy characters, otherwise
 * characters are copied.
*/

void
ndk_clean_path (ngx_str_t *path, ngx_uint_t complex, size_t off)
{
    u_char         *s, *p, *m, *e, c, *l;
    ngx_uint_t      root;

    if (path->len == 1) {

        if (path->data[0] == '.') {
            path->len = 0;
        }

        return;
    }

    /* strip initial './' */

    s = path->data;
    e = s + path->len;

    if (off) {
        p = s + off;
        goto check_basic;
    }

    if (*s == '/')
        root = 1;
    else
        root = 0;

    while (s < e) {

        switch (*s) {

        case    '/' :

            /* '//' => '/' */

            s++;
            continue;

        case    '.' :

            if (s == e-1) {

                if (root) {
                    path->data[0] = '/';
                    path->len = 1;
                } else {
                    path->len = 0;
                }

                return;
            }

            /* './' => '' */

            if (s[1] == '/') {

                s += 2;

                if (s == e) {

                    path->len = 0;
                    return;
                }

                continue;
            }
        }

        break;
    }

    if (root && *s != '/') {
        s--;
    }

    p = s;

check_basic :

    for ( ; p<e; p++) {

        if (*p == '/') {

        new_dir_first :

            if (e - p == 1)
                break;

            switch (p[1]) {

            case    '/' :

                /* '//' => '/' */

                m = p + 2;
                goto copy;

            case    '.' :

                if (e - p == 2)
                    break;

                switch (p[2]) {

                case    '/' :

                    /* './' => '' */

                    m = p + 2;
                    goto copy;

                case    '.' :

                    if (e - p == 3 || p[3] == '/') {

                        if (p == s) {

                            s += 3;
                            continue;
                        }

                        if (p - s >= 2) {

                            if (p[-1] == '.' && p[-2] == '.') {

                                if (p - s == 2 || p[-3] == '/') {    /* = '../../' */

                                    p += 2;     /* 3? */
                                    continue;
                                }
                            }
                        }

                        m = p + 4;

                        if (complex) {

                            for (p--; p >= s; p--) {

                                switch (*p) {

                                case    '/' :
                                    goto copy;

                                case    '$' :

                                    p = m - 1;

                                    if (m == e)
                                        goto end_basic;

                                    goto new_dir_first;
                                }
                            }

                        } else {

                           for (p--; p > s; p--) {

                                /* '/path/folder/../' => '/path/' */

                                if (*p == '/')
                                    break;
                            }
                        }

                        goto copy;
                    }
                }
            }
        }
    }

end_basic :

    path->data = s;
    path->len = p - s;

    return;

copy :

    p++;

    if (m < e)
        goto new_dir;

    while (m < e) {       

        c = *m;
        *p = c;
        p++;

        if (c == '/') {

            m++;

        new_dir :

            for ( ; m<e; m++) {

                c = *m;
                if (c != '/')
                    break;
            }

            if (m == e)
                break;

            if (c == '.') {

                if (e - m == 1)
                    break;

                switch (m[1]) {

                case    '/' :

                    /* './' => '' */

                    m += 2;
                    if (m == e)
                        break;

                    goto new_dir;

                case    '.' :

                    if (e - m == 2 || m[2] == '/') {

                        if (m - s >= 3) {   /* NOTE : this is one higher than above because m has moved on 1 */

                            if (p[-2] == '.' && p[-3] == '.') {

                                if (m - s == 3 || p[-4] == '/') {    /* = '../../' */

                                    p[0] = '.';
                                    p[1] = '.';
                                    p[2] = '/';
                                    p += 3;
                                    m += 3;
                                    goto new_dir;
                                }
                            }
                        }

                        if (complex) {

                            l = p;

                            for (p -= 2; p >= s; p--) {

                                switch (*p) {

                                case    '/' :
                                    break;

                                case    '$' :

                                    l[0] = '.';
                                    l[1] = '.';
                                    l[2] = '/';
                                    p = l + 4;
                                    break;

                                default :
                                    continue;
                                }

                                break;
                            }

                            m += 3;
                            if (m == e)
                                goto end;

                            goto new_dir;

                        } else {

                            for (p -= 2; p > s; p--) {

                                /* '/path/folder/../' => '/path/' */

                                if (*p == '/')
                                    break;
                            }

                            m += 3;
                            if (m == e)
                                goto end;

                            goto new_dir;
                        }
                    }
                }
            }

        } else {
            m++;
        }
    }

end :

    path->data = s;
    path->len = p - s;
}


/* This function converts a path to its directory version, and assumes that there is always space
 * to allocatate an extra character on the end (which is only true if the provided strings always
 * have NULL's at the end (hence the 'safe').
*/

void
ndk_path_to_dir_safe (ngx_str_t *path, ngx_uint_t complex, size_t off)
{
    size_t   len;
    u_char  *p, *m;

    ndk_clean_path (path, complex, off);

    len = path->len;
    if (!len)
        return;

    p = path->data;
    m = p + len - 1;

    if (*m != '/') {

        p [len] = '/';
        path->len++;
    }
}


/* Divides a path given by path/to/path1:path/to/path2 into separate strings and returns an
 * array of these strings.
*/

ngx_array_t *
ndk_split_path_create (ngx_conf_t *cf, ngx_str_t *path)
{
    ngx_str_t         *str;
    int                n;
    u_char            *m, *s, *e;
    ngx_array_t       *a; 

    if (path == NULL)
        return  NULL;

    n = ndk_strcntc (path, ':');

    a = ngx_array_create (cf->pool, n + 1, sizeof (ngx_str_t));
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

        str = ngx_array_push (a);
        if (str == NULL) {
            return  NULL;
        }

        str->data = s;
        str->len = m - s;

        if (ngx_conf_full_name (cf->cycle, str, 0) == NGX_ERROR)
            return  NULL;

        s = m+1;
    }

    return  a;
}



ngx_array_t *
ndk_split_path_create_raw (ngx_conf_t *cf, char *path)
{
    ngx_str_t         *str;
    int                n;
    char              *m, *s;
    ngx_array_t       *a; 

    if (path == NULL)
        return  NULL;

    n = ndk_strccnt (path, ':');

    a = ngx_array_create (cf->pool, n + 1, sizeof (ngx_str_t));
    if (a == NULL) {
        return  NULL;
    }

    s = path;


    while (*s != '\0') {

        m = s;

        while (*m != '\0' && *m != ':') m++;

        if (m == s) {
            s = m+1;
            continue;
        }

        str = ngx_array_push (a);
        if (str == NULL) {
            return  NULL;
        }

        str->data = (u_char *) s;
        str->len = m - s;

        if (ngx_conf_full_name (cf->cycle, str, 0) == NGX_ERROR)
            return  NULL;

        if (*m == '\0')
            break;

        s = m+1;
    }

    return  a;
}



char *
ndk_conf_set_full_path_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char  *p = conf;

    ngx_str_t        *path, *value;
    ngx_conf_post_t  *post;

    path = (ngx_str_t *) (p + cmd->offset);

    if (path->data) {
        return "is duplicate";
    }

    value = cf->args->elts;

    *path = value[1];

    if (ngx_conf_full_name (cf->cycle, path, 0) == NGX_ERROR)
        return  NGX_CONF_ERROR;

    if (cmd->post) {
        post = cmd->post;
        return post->post_handler(cf, post, path);
    }

    return NGX_CONF_OK;
}



char *
ndk_conf_set_split_path_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)     
{
    /* TODO : change to use the path func above */

    char  *p = conf;

    ngx_str_t         *value, *str;
    ngx_array_t      **a;
    ngx_conf_post_t   *post;
    int                n;
    u_char            *m, *s, *e;

    a = (ngx_array_t **) (p + cmd->offset);

    if (*a != NGX_CONF_UNSET_PTR) {
        return  "is duplicate";
    }

    value = cf->args->elts;
    value++;

    n = ndk_strcntc (value, ':') + 1;

    *a = ngx_array_create (cf->pool, n, sizeof (ngx_str_t));
    if (*a == NULL) {
        return  NGX_CONF_ERROR;
    }

    s = value->data;
    e = s + value->len;

    while (s < e) {

        m = s;

        while (m < e && *m != ':') m++;

        if (m == s) {
            s = m+1;
            continue;
        }

        str = ngx_array_push (*a);
        if (str == NULL) {
            return  NGX_CONF_ERROR;
        }

        str->data = s;
        str->len = m - s;

        if (ngx_conf_full_name (cf->cycle, str, 0) == NGX_ERROR)
            return  NGX_CONF_ERROR;

        s = m+1;
    }


    if (cmd->post) {
        post = cmd->post;
        return  post->post_handler (cf, post, a);
    }

    return  NGX_CONF_OK;
}



char *
ndk_conf_set_full_path (ngx_conf_t *cf, void *data, ngx_str_t *path)
{
    if (ngx_conf_full_name (cf->cycle, path, 0) == NGX_ERROR)
        return  NGX_CONF_ERROR;

    return  NGX_CONF_OK;
}



char *
ndk_conf_set_full_conf_path (ngx_conf_t *cf, void *data, ngx_str_t *path)
{
    if (ngx_conf_full_name (cf->cycle, path, 1) == NGX_ERROR)
        return  NGX_CONF_ERROR;

    return  NGX_CONF_OK;
}


