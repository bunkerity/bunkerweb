

typedef struct {
    ngx_str_t                   key;
    ngx_http_complex_value_t    value;
} ndk_http_complex_keyval_t;



/* create/compile functions */

ngx_int_t      ndk_http_complex_value_compile        (ngx_conf_t *cf, ngx_http_complex_value_t *cv, ngx_str_t *value);
ngx_array_t *  ndk_http_complex_value_array_create   (ngx_conf_t *cf, char **s, ngx_int_t n);
ngx_int_t      ndk_http_complex_value_array_compile  (ngx_conf_t *cf, ngx_array_t *a);


/* conf set slot functions */

char *  ndk_conf_set_http_complex_keyval_slot        (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_http_complex_value_slot         (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_http_complex_value_array_slot   (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
