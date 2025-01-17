
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_misc.c.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_misc.h"
#include "ngx_stream_lua_util.h"




int
ngx_stream_lua_ffi_get_resp_status(ngx_stream_lua_request_t *r)
{
    return r->session->status;
}




int
ngx_stream_lua_ffi_get_conf_env(u_char *name, u_char **env_buf,
    size_t *name_len)
{
    ngx_uint_t            i;
    ngx_str_t            *var;
    ngx_core_conf_t      *ccf;

    ccf = (ngx_core_conf_t *) ngx_get_conf(ngx_cycle->conf_ctx,
                                           ngx_core_module);

    var = ccf->env.elts;

    for (i = 0; i < ccf->env.nelts; i++) {
        if (var[i].data[var[i].len] == '='
            && ngx_strncmp(name, var[i].data, var[i].len) == 0)
        {
            *env_buf = var[i].data;
            *name_len = var[i].len;

            return NGX_OK;
        }
    }

    return NGX_DECLINED;
}


/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
