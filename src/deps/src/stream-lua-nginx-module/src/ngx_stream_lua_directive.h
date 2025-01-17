
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_directive.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_DIRECTIVE_H_INCLUDED_
#define _NGX_STREAM_LUA_DIRECTIVE_H_INCLUDED_


#include "ngx_stream_lua_common.h"


char *ngx_stream_lua_shared_dict(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_package_cpath(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_package_path(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_content_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_content_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_log_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_log_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);


char *ngx_stream_lua_init_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_init_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_init_worker_by_lua_block(ngx_conf_t *cf,
    ngx_command_t *cmd, void *conf);
char *ngx_stream_lua_init_worker_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *ngx_stream_lua_code_cache(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *ngx_stream_lua_load_resty_core(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);


char *
ngx_stream_lua_preread_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);
char *
ngx_stream_lua_preread_by_lua(ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *
ngx_stream_lua_add_variable(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);

char *ngx_stream_lua_conf_lua_block_parse(ngx_conf_t *cf,
    ngx_command_t *cmd);


char *ngx_stream_lua_capture_error_log(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf);

#endif /* _NGX_STREAM_LUA_DIRECTIVE_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
