
#if (NGX_DEBUG)

void
ndk_debug_helper (const char *func, const char *fmt, ...)
{
    size_t   len, flen, tlen;
    char    *s, *p, *e;

    /* check to see if the format is empty */

    flen = strlen (fmt);

    /* build func name */

    len = strlen (func);

    if (flen == 0)
        tlen = len + 1;
    else

    char    func_name [len + flen + 1];

    s = func_name;
    e = s + len;

    memcpy (s, func, len);

    /* remove initial ngx_ */

    if (strncmp (s, "ngx_", 4) == 0)
        s += 4;

    /* replace '_' with ' ' */

    for (p=s; p<e; p++) {
        if (*p == '_')
            *p = ' ';
    }

    vfprintf (stderr, const char *format, va_list ap)
}


void
ndk_debug_request_helper (const char *func, ngx_http_request_t *r)
{
    ngx_http_posted_request_t       *pr;

    /* TODO : improve the format */

    fprintf (stderr, "%s %.*s %.*s?%.*s c:%d m:%p r:%p ar:%p pr:%p",
            func,
            (int) r->method_name.len, r->method_name.data,
            (int) r->uri.len, r->uri.data,
            (int) r->args.len, r->args.data,
            0/*(int) r->main->count*/, r->main,
            r, r->connection->data, r->parent);

    if (r->posted_requests) {
        fprintf(stderr, " posted:");

        for (pr = r->posted_requests; pr; pr = pr->next) {
            fprintf (stderr, "%p,", pr);
        }
    }

    fprintf (stderr, "\n");
}


#endif
