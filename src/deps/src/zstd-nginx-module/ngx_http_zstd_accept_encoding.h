
/*
 * Copyright (C) GetPageSpeed LLC
 */


#ifndef NGX_HTTP_ZSTD_ACCEPT_ENCODING_H_INCLUDED_
#define NGX_HTTP_ZSTD_ACCEPT_ENCODING_H_INCLUDED_


#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>


/*
 * Accept-Encoding parsing, per RFC 9110 section 12.5.3:
 *
 *     Accept-Encoding = #( codings [ weight ] )
 *     codings         = content-coding / "identity" / "*"
 *     weight          = OWS ";" OWS "q=" qvalue
 *     qvalue          = ( "0" [ "." 0*3DIGIT ] ) / ( "1" [ "." 0*3"0" ] )
 *
 * Both modules ask the same question of the same header, so the parser lives
 * here rather than being duplicated in each.
 *
 * Three properties matter and are easy to get wrong with a substring search:
 *
 *   - "zstd;q=0" means the client explicitly refuses zstd. It is not the same
 *     as the coding being absent.
 *   - "*" is a real wildcard, and an explicit entry for zstd overrides it in
 *     either direction ("*;q=0, zstd" accepts, "*, zstd;q=0" refuses).
 *   - Coding names are whole tokens. "zstd-foo" and "notzstd" are different
 *     codings that happen to contain "zstd" as a substring.
 */


#define NGX_HTTP_ZSTD_QVALUE_ABSENT  (-1)


static ngx_inline ngx_uint_t
ngx_http_zstd_is_tchar(u_char c)
{
    if ((c >= 'a' && c <= 'z')
        || (c >= 'A' && c <= 'Z')
        || (c >= '0' && c <= '9'))
    {
        return 1;
    }

    switch (c) {
    case '!': case '#': case '$': case '%': case '&': case '\'':
    case '*': case '+': case '-': case '.': case '^': case '_':
    case '`': case '|': case '~':
        return 1;
    default:
        return 0;
    }
}


static ngx_inline u_char *
ngx_http_zstd_skip_ows(u_char *p, u_char *last)
{
    while (p < last && (*p == ' ' || *p == '\t')) {
        p++;
    }

    return p;
}


/*
 * Parse a qvalue into thousandths, so 1 becomes 1000 and 0.001 becomes 1.
 *
 * The accumulator is ngx_int_t and the fraction is capped at three digits, so
 * a long run of digits is rejected outright rather than being folded into a
 * narrower type where it could wrap and turn a refusal into an acceptance.
 */
static ngx_inline ngx_int_t
ngx_http_zstd_parse_qvalue(u_char **pos, u_char *last, ngx_int_t *qvalue)
{
    u_char     *p;
    ngx_int_t   q, scale;
    ngx_uint_t  digits;

    p = *pos;

    if (p == last) {
        return NGX_ERROR;
    }

    if (*p == '1') {
        q = 1000;
        p++;

        if (p < last && *p == '.') {
            p++;

            /* only zeroes may follow 1., anything else exceeds 1 */

            for (digits = 0; p < last && *p >= '0' && *p <= '9'; p++) {
                if (++digits > 3 || *p != '0') {
                    return NGX_ERROR;
                }
            }
        }

    } else if (*p == '0') {
        q = 0;
        p++;

        if (p < last && *p == '.') {
            p++;

            for (digits = 0, scale = 100;
                 p < last && *p >= '0' && *p <= '9';
                 p++, scale /= 10)
            {
                if (++digits > 3) {
                    return NGX_ERROR;
                }

                q += (*p - '0') * scale;
            }
        }

    } else {
        return NGX_ERROR;
    }

    *pos = p;
    *qvalue = q;

    return NGX_OK;
}


/*
 * Advance past the remainder of the current list element. Quote-aware: a comma
 * inside a quoted-string does not end the element, and a backslash inside one
 * escapes the next octet.
 */
static ngx_inline u_char *
ngx_http_zstd_skip_element(u_char *p, u_char *last)
{
    ngx_uint_t  quoted;

    for (quoted = 0; p < last; p++) {

        if (quoted) {
            if (*p == '\\' && p + 1 < last) {
                p++;

            } else if (*p == '"') {
                quoted = 0;
            }

            continue;
        }

        if (*p == '"') {
            quoted = 1;

        } else if (*p == ',') {
            return p;
        }
    }

    return last;
}


static ngx_inline ngx_int_t
ngx_http_zstd_accept_encoding(ngx_str_t *ae)
{
    u_char     *p, *last, *name, *param;
    size_t      len, param_len;
    ngx_int_t   q, zstd_q, wildcard_q;
    ngx_uint_t  seen_q, bad;

    if (ae == NULL || ae->data == NULL) {
        return NGX_DECLINED;
    }

    p = ae->data;
    last = ae->data + ae->len;

    zstd_q = NGX_HTTP_ZSTD_QVALUE_ABSENT;
    wildcard_q = NGX_HTTP_ZSTD_QVALUE_ABSENT;

    while (p < last) {

        /* OWS and empty list elements, which the grammar permits */

        while (p < last && (*p == ' ' || *p == '\t' || *p == ',')) {
            p++;
        }

        if (p == last) {
            break;
        }

        name = p;

        while (p < last && ngx_http_zstd_is_tchar(*p)) {
            p++;
        }

        len = p - name;

        if (len == 0) {
            /* not a token where a coding name is required */
            p = ngx_http_zstd_skip_element(p, last);
            continue;
        }

        q = 1000;               /* no weight present means q=1 */
        seen_q = 0;
        bad = 0;

        for ( ;; ) {
            p = ngx_http_zstd_skip_ows(p, last);

            if (p == last || *p != ';') {
                break;
            }

            p++;                                            /* ';' */
            p = ngx_http_zstd_skip_ows(p, last);

            param = p;

            while (p < last && ngx_http_zstd_is_tchar(*p)) {
                p++;
            }

            param_len = p - param;
            p = ngx_http_zstd_skip_ows(p, last);

            if (p == last || *p != '=') {
                /* a parameter with no value; nothing to interpret */
                if (param_len == 0) {
                    bad = 1;
                    break;
                }

                continue;
            }

            p++;                                            /* '=' */
            p = ngx_http_zstd_skip_ows(p, last);

            if (param_len == 1 && (*param == 'q' || *param == 'Q')) {

                /* a second q for one element is ambiguous, so reject it */

                if (seen_q
                    || ngx_http_zstd_parse_qvalue(&p, last, &q) != NGX_OK)
                {
                    bad = 1;
                    break;
                }

                seen_q = 1;
                continue;
            }

            /* some other parameter: step over its value */

            if (p < last && *p == '"') {
                p++;

                while (p < last && *p != '"') {
                    if (*p == '\\' && p + 1 < last) {
                        p++;
                    }

                    p++;
                }

                if (p < last) {
                    p++;                                    /* closing '"' */
                }

            } else {
                while (p < last && ngx_http_zstd_is_tchar(*p)) {
                    p++;
                }
            }
        }

        if (!bad) {
            if (len == 4 && ngx_strncasecmp(name, (u_char *) "zstd", 4) == 0) {
                zstd_q = q;

            } else if (len == 1 && *name == '*') {
                wildcard_q = q;
            }
        }

        p = ngx_http_zstd_skip_element(p, last);
    }

    /* an explicit entry for the coding always beats the wildcard */

    if (zstd_q != NGX_HTTP_ZSTD_QVALUE_ABSENT) {
        return zstd_q > 0 ? NGX_OK : NGX_DECLINED;
    }

    if (wildcard_q != NGX_HTTP_ZSTD_QVALUE_ABSENT) {
        return wildcard_q > 0 ? NGX_OK : NGX_DECLINED;
    }

    return NGX_DECLINED;
}


static ngx_inline ngx_uint_t
ngx_http_zstd_vary_has_accept_encoding(ngx_http_request_t *r)
{
    u_char           *end, *p, *start;
    ngx_uint_t        i;
    ngx_list_part_t  *part;
    ngx_table_elt_t  *h;

    for (part = &r->headers_out.headers.part, h = part->elts, i = 0;
         /* void */;
         i++)
    {
        if (i >= part->nelts) {
            if (part->next == NULL) {
                break;
            }

            part = part->next;
            h = part->elts;
            i = 0;
        }

        if (h[i].hash == 0
            || h[i].key.len != sizeof("Vary") - 1
            || ngx_strncasecmp(h[i].key.data, (u_char *) "Vary",
                               sizeof("Vary") - 1) != 0)
        {
            continue;
        }

        p = h[i].value.data;
        end = p + h[i].value.len;

        while (p < end) {
            while (p < end && (*p == ' ' || *p == '\t' || *p == ',')) {
                p++;
            }

            start = p;
            while (p < end && *p != ',') {
                p++;
            }

            while (p > start && (p[-1] == ' ' || p[-1] == '\t')) {
                p--;
            }

            if ((p - start == 1 && *start == '*')
                || ((size_t) (p - start) == sizeof("Accept-Encoding") - 1
                    && ngx_strncasecmp(start, (u_char *) "Accept-Encoding",
                                       sizeof("Accept-Encoding") - 1) == 0))
            {
                return 1;
            }

            while (p < end && *p != ',') {
                p++;
            }
        }
    }

    return 0;
}


static ngx_inline ngx_int_t
ngx_http_zstd_vary_accept_encoding(ngx_http_request_t *r)
{
    ngx_table_elt_t           *h;
    ngx_http_core_loc_conf_t  *clcf;

    r->gzip_vary = 1;

    clcf = ngx_http_get_module_loc_conf(r, ngx_http_core_module);
    if (clcf != NULL && clcf->gzip_vary) {
        return NGX_OK;
    }

    if (ngx_http_zstd_vary_has_accept_encoding(r)) {
        return NGX_OK;
    }

    h = ngx_list_push(&r->headers_out.headers);
    if (h == NULL) {
        return NGX_ERROR;
    }

    h->hash = 1;
#if (nginx_version >= 1023000)
    h->next = NULL;
#endif
    ngx_str_set(&h->key, "Vary");
    ngx_str_set(&h->value, "Accept-Encoding");

    return NGX_OK;
}


#endif /* NGX_HTTP_ZSTD_ACCEPT_ENCODING_H_INCLUDED_ */
