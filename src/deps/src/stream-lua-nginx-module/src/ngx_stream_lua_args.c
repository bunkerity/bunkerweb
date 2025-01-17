
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_args.c.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_args.h"
#include "ngx_stream_lua_util.h"




int
ngx_stream_lua_parse_args(lua_State *L, u_char *buf, u_char *last, int max)
{
    u_char                      *p, *q;
    u_char                      *src, *dst;
    unsigned                     parsing_value;
    size_t                       len;
    int                          count = 0;
    int                          top;

    top = lua_gettop(L);

    p = buf;

    parsing_value = 0;
    q = p;

    while (p != last) {
        if (*p == '=' && ! parsing_value) {
            /* key data is between p and q */

            src = q; dst = q;

            ngx_stream_lua_unescape_uri(&dst, &src, p - q,
                                        NGX_UNESCAPE_URI_COMPONENT);

            dd("pushing key %.*s", (int) (dst - q), q);

            /* push the key */
            lua_pushlstring(L, (char *) q, dst - q);

            /* skip the current '=' char */
            p++;

            q = p;
            parsing_value = 1;

        } else if (*p == '&') {
            /* reached the end of a key or a value, just save it */
            src = q; dst = q;

            ngx_stream_lua_unescape_uri(&dst, &src, p - q,
                                        NGX_UNESCAPE_URI_COMPONENT);

            dd("pushing key or value %.*s", (int) (dst - q), q);

            /* push the value or key */
            lua_pushlstring(L, (char *) q, dst - q);

            /* skip the current '&' char */
            p++;

            q = p;

            if (parsing_value) {
                /* end of the current pair's value */
                parsing_value = 0;

            } else {
                /* the current parsing pair takes no value,
                 * just push the value "true" */
                dd("pushing boolean true");

                lua_pushboolean(L, 1);
            }

            (void) lua_tolstring(L, -2, &len);

            if (len == 0) {
                /* ignore empty string key pairs */
                dd("popping key and value...");
                lua_pop(L, 2);

            } else {
                dd("setting table...");
                ngx_stream_lua_set_multi_value_table(L, top);
            }

            if (max > 0 && ++count == max) {
                lua_pushliteral(L, "truncated");

                ngx_log_debug1(NGX_LOG_DEBUG_STREAM, ngx_cycle->log, 0,
                               "stream lua hit query args limit %d",
                               max);
                return 2;
            }

        } else {
            p++;
        }
    }

    if (p != q || parsing_value) {
        src = q; dst = q;

        ngx_stream_lua_unescape_uri(&dst, &src, p - q,
                                    NGX_UNESCAPE_URI_COMPONENT);

        dd("pushing key or value %.*s", (int) (dst - q), q);

        lua_pushlstring(L, (char *) q, dst - q);

        if (!parsing_value) {
            dd("pushing boolean true...");
            lua_pushboolean(L, 1);
        }

        (void) lua_tolstring(L, -2, &len);

        if (len == 0) {
            /* ignore empty string key pairs */
            dd("popping key and value...");
            lua_pop(L, 2);

        } else {
            dd("setting table...");
            ngx_stream_lua_set_multi_value_table(L, top);
        }
    }

    dd("gettop: %d", lua_gettop(L));
    dd("type: %s", lua_typename(L, lua_type(L, 1)));

    if (lua_gettop(L) != top) {
        return luaL_error(L, "internal error: stack in bad state");
    }

    return 1;
}




/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
