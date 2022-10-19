
/*
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_http_headers_more_util.h"
#include <ctype.h>


ngx_int_t
ngx_http_headers_more_parse_header(ngx_conf_t *cf, ngx_str_t *cmd_name,
    ngx_str_t *raw_header, ngx_array_t *headers,
    ngx_http_headers_more_opcode_t opcode,
    ngx_http_headers_more_set_header_t *handlers)
{
    ngx_http_headers_more_header_val_t             *hv;

    ngx_uint_t                           i;
    ngx_str_t                            key = ngx_null_string;
    ngx_str_t                            value = ngx_null_string;
    ngx_flag_t                           seen_end_of_key;
    ngx_http_compile_complex_value_t     ccv;
    u_char                              *p;

    hv = ngx_array_push(headers);
    if (hv == NULL) {
        return NGX_ERROR;
    }

    seen_end_of_key = 0;
    for (i = 0; i < raw_header->len; i++) {
        if (key.len == 0) {
            if (isspace(raw_header->data[i])) {
                continue;
            }

            key.data = raw_header->data;
            key.len  = 1;

            continue;
        }

        if (!seen_end_of_key) {
            if (raw_header->data[i] == ':'
                || isspace(raw_header->data[i]))
            {
                seen_end_of_key = 1;
                continue;
            }

            key.len++;

            continue;
        }

        if (value.len == 0) {
            if (raw_header->data[i] == ':'
                || isspace(raw_header->data[i]))
            {
                continue;
            }

            value.data = &raw_header->data[i];
            value.len  = 1;

            continue;
        }

        value.len++;
    }

    if (key.len == 0) {
        ngx_log_error(NGX_LOG_ERR, cf->log, 0,
                      "%V: no key found in the header argument: %V",
                      cmd_name, raw_header);

        return NGX_ERROR;
    }

    hv->wildcard = (key.data[key.len - 1] == '*');
    if (hv->wildcard && key.len<2){
        ngx_log_error(NGX_LOG_ERR, cf->log, 0,
                      "%V: wildcard key too short: %V",
                      cmd_name, raw_header);
        return NGX_ERROR;
    }

    hv->hash = ngx_hash_key_lc(key.data, key.len);
    hv->key = key;

    hv->offset = 0;

    for (i = 0; handlers[i].name.len; i++) {
        if (hv->key.len != handlers[i].name.len
            || ngx_strncasecmp(hv->key.data, handlers[i].name.data,
                               handlers[i].name.len) != 0)
        {
            dd("hv key comparison: %s <> %s", handlers[i].name.data,
               hv->key.data);

            continue;
        }

        hv->offset = handlers[i].offset;
        hv->handler = handlers[i].handler;

        break;
    }

    if (handlers[i].name.len == 0 && handlers[i].handler) {
        hv->offset = handlers[i].offset;
        hv->handler = handlers[i].handler;
    }

    if (opcode == ngx_http_headers_more_opcode_clear) {
        value.len = 0;
    }

    if (value.len == 0) {
        ngx_memzero(&hv->value, sizeof(ngx_http_complex_value_t));
        return NGX_OK;

    }

    /* Nginx request header value requires to be a null-terminated
     * C string */

    p = ngx_palloc(cf->pool, value.len + 1);
    if (p == NULL) {
        return NGX_ERROR;
    }

    ngx_memcpy(p, value.data, value.len);
    p[value.len] = '\0';
    value.data = p;
    value.len++; /* we should also compile the trailing '\0' */

    /* compile the header value as a complex value */

    ngx_memzero(&ccv, sizeof(ngx_http_compile_complex_value_t));

    ccv.cf = cf;
    ccv.value = &value;
    ccv.complex_value = &hv->value;

    if (ngx_http_compile_complex_value(&ccv) != NGX_OK) {
        return NGX_ERROR;
    }

    return NGX_OK;
}


ngx_int_t
ngx_http_headers_more_parse_statuses(ngx_log_t *log, ngx_str_t *cmd_name,
    ngx_str_t *value, ngx_array_t *statuses)
{
    u_char          *p, *last;
    ngx_uint_t      *s = NULL;

    p = value->data;
    last = p + value->len;

    for (; p != last; p++) {
        if (s == NULL) {
            if (isspace(*p)) {
                continue;
            }

            s = ngx_array_push(statuses);
            if (s == NULL) {
                return NGX_ERROR;
            }

            if (*p >= '0' && *p <= '9') {
                *s = *p - '0';

            } else {
                ngx_log_error(NGX_LOG_ERR, log, 0,
                              "%V: invalid digit \"%c\" found in "
                              "the status code list \"%V\"",
                              cmd_name, *p, value);

                return NGX_ERROR;
            }

            continue;
        }

        if (isspace(*p)) {
            dd("Parsed status %d", (int) *s);

            s = NULL;
            continue;
        }

        if (*p >= '0' && *p <= '9') {
            *s *= 10;
            *s += *p - '0';

        } else {
            ngx_log_error(NGX_LOG_ERR, log, 0,
                          "%V: invalid digit \"%c\" found in "
                          "the status code list \"%V\"",
                          cmd_name, *p, value);

            return NGX_ERROR;
        }
    }

    if (s) {
        dd("Parsed status %d", (int) *s);
    }

    return NGX_OK;
}


ngx_int_t
ngx_http_headers_more_parse_types(ngx_log_t *log, ngx_str_t *cmd_name,
    ngx_str_t *value, ngx_array_t *types)
{
    u_char          *p, *last;
    ngx_str_t       *t = NULL;

    p = value->data;
    last = p + value->len;

    for (; p != last; p++) {
        if (t == NULL) {
            if (isspace(*p) || *p == ';') {
                continue;
            }

            t = ngx_array_push(types);
            if (t == NULL) {
                return NGX_ERROR;
            }

            t->len = 1;
            t->data = p;

            continue;
        }

        if (isspace(*p) || *p == ';') {
            t = NULL;
            continue;
        }

        t->len++;
    }

    return NGX_OK;
}


ngx_int_t
ngx_http_headers_more_rm_header_helper(ngx_list_t *l, ngx_list_part_t *cur,
    ngx_uint_t i)
{
    ngx_table_elt_t             *data;
    ngx_list_part_t             *new, *part;

    dd("list rm item: part %p, i %d, nalloc %d", cur, (int) i,
       (int) l->nalloc);

    data = cur->elts;

    dd("cur: nelts %d, nalloc %d", (int) cur->nelts,
       (int) l->nalloc);

    if (i == 0) {
        cur->elts = (char *) cur->elts + l->size;
        cur->nelts--;

        if (cur == l->last) {
            if (cur->nelts == 0) {
#if 1
                part = &l->part;

                if (part == cur) {
                    cur->elts = (char *) cur->elts - l->size;
                    /* do nothing */

                } else {
                    while (part->next != cur) {
                        if (part->next == NULL) {
                            return NGX_ERROR;
                        }
                        part = part->next;
                    }

                    l->last = part;
                    part->next = NULL;
                    dd("part nelts: %d", (int) part->nelts);
                    l->nalloc = part->nelts;
                }
#endif

            } else {
                l->nalloc--;
            }

            return NGX_OK;
        }

        if (cur->nelts == 0) {
            part = &l->part;

            if (part == cur) {
                ngx_http_headers_more_assert(cur->next != NULL);

                dd("remove 'cur' from the list by rewriting 'cur': "
                   "l->last: %p, cur: %p, cur->next: %p, part: %p",
                   l->last, cur, cur->next, part);

                if (l->last == cur->next) {
                    dd("last is cur->next");
                    l->part = *(cur->next);
                    l->last = part;
                    l->nalloc = part->nelts;

                } else {
                    l->part = *(cur->next);
                }

            } else {
                dd("remove 'cur' from the list");
                while (part->next != cur) {
                    if (part->next == NULL) {
                        return NGX_ERROR;
                    }
                    part = part->next;
                }

                part->next = cur->next;
            }

            return NGX_OK;
        }

        return NGX_OK;
    }

    if (i == cur->nelts - 1) {
        cur->nelts--;

        if (cur == l->last) {
            l->nalloc = cur->nelts;
        }

        return NGX_OK;
    }

    new = ngx_palloc(l->pool, sizeof(ngx_list_part_t));
    if (new == NULL) {
        return NGX_ERROR;
    }

    new->elts = &data[i + 1];
    new->nelts = cur->nelts - i - 1;
    new->next = cur->next;

    cur->nelts = i;
    cur->next = new;
    if (cur == l->last) {
        l->last = new;
        l->nalloc = new->nelts;
    }

    return NGX_OK;
}
