

typedef struct {
    ngx_array_t                    *a;
    ngx_uint_t                      prefix;
} ndk_http_complex_path_t;

typedef struct {
    ngx_http_complex_value_t        val;
    ngx_flag_t                      dynamic;
} ndk_http_complex_path_elt_t;

typedef struct {
    ngx_str_t                       val;
    ngx_flag_t                      dynamic;
} ndk_http_complex_path_value_t;

typedef struct {
    ndk_http_complex_path_value_t  *elts;
    ngx_uint_t                      nelts;
} ndk_http_complex_path_values_t;


extern  ndk_http_complex_path_value_t     ndk_empty_http_complex_path_value;


ngx_array_t *   ndk_http_complex_path_create_compile     (ngx_conf_t *cf, ngx_str_t *path, ngx_uint_t prefix);
ngx_int_t       ndk_http_complex_path_value_compile      (ngx_conf_t *cf, ngx_http_complex_value_t *cv, 
                                                                    ngx_str_t *value, ngx_uint_t prefix);
char *          ndk_conf_set_http_complex_path_slot      (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
