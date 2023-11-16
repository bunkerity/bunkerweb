/*
 * 2010 (C) Marcus Clyne
 */

#ifndef _NDK_SET_VAR_H_INCLUDED_
#define _NDK_SET_VAR_H_INCLUDED_


typedef ngx_int_t   (*ndk_set_var_pt)              (ngx_http_request_t *r, ngx_str_t *val);
typedef ngx_int_t   (*ndk_set_var_data_pt)         (ngx_http_request_t *r, ngx_str_t *val, void *data);
typedef ngx_int_t   (*ndk_set_var_value_pt)        (ngx_http_request_t *r, ngx_str_t *val, ngx_http_variable_value_t *v);
typedef ngx_int_t   (*ndk_set_var_value_data_pt)   (ngx_http_request_t *r, ngx_str_t *val, ngx_http_variable_value_t *v, void *data);
typedef void        (*ndk_set_var_hash_pt)         (u_char *p, char *data, size_t len);


typedef struct {
    ngx_uint_t      type;
    void           *func;
    size_t          size;
    void           *data;
} ndk_set_var_t;


enum {
    NDK_SET_VAR_BASIC = 0,
    NDK_SET_VAR_DATA,
    NDK_SET_VAR_VALUE,
    NDK_SET_VAR_VALUE_DATA,
    NDK_SET_VAR_MULTI_VALUE,
    NDK_SET_VAR_MULTI_VALUE_DATA,
    NDK_SET_VAR_HASH
};


char *  ndk_set_var                    (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_set_var_value              (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_set_var_multi_value        (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);


char *  ndk_set_var_core               (ngx_conf_t *cf, ngx_str_t *name, ndk_set_var_t *filter);
char *  ndk_set_var_value_core         (ngx_conf_t *cf, ngx_str_t *name, ngx_str_t *value, ndk_set_var_t *filter);
char *  ndk_set_var_multi_value_core   (ngx_conf_t *cf, ngx_str_t *name, ngx_str_t *value, ndk_set_var_t *filter);

#endif /* _NDK_SET_VAR_H_INCLUDED_ */
