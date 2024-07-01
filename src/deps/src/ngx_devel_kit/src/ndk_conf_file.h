

/* conf set functions */

char *  ndk_conf_set_true_slot              (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_false_slot             (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_full_path_slot         (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_ptr_slot               (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_null_slot              (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_str_array_multi_slot   (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_keyval1_slot           (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_num_flag               (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_num64_slot             (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *  ndk_conf_set_sec_flag_slot          (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

ngx_http_conf_ctx_t *   ndk_conf_create_http_location           (ngx_conf_t *cf);
ngx_http_conf_ctx_t *   ngx_conf_create_http_named_location     (ngx_conf_t *cf, ngx_str_t *name);

ngx_int_t               ndk_replace_command     (ngx_command_t *new_cmd, ngx_uint_t module_type);


/* values for conf_set_xxx_flag */

#define     NDK_CONF_SET_TRUE       -2
#define     NDK_CONF_SET_FALSE      -3


/* wrappers for utility macros */

#define     ndk_conf_set_bitmask_slot       ngx_conf_set_bitmask_slot
#define     ndk_conf_set_bufs_slot          ngx_conf_set_bufs_slot
#define     ndk_conf_set_enum_slot          ngx_conf_set_enum_slot
#define     ndk_conf_set_flag_slot          ngx_conf_set_flag_slot
#define     ndk_conf_set_keyval_slot        ngx_conf_set_keyval_slot
#define     ndk_conf_set_msec_slot          ngx_conf_set_msec_slot
#define     ndk_conf_set_num_slot           ngx_conf_set_num_slot
#define     ndk_conf_set_off_slot           ngx_conf_set_off_slot
#define     ndk_conf_set_sec_slot           ngx_conf_set_sec_slot
#define     ndk_conf_set_size_slot          ngx_conf_set_size_slot
#define     ndk_conf_set_str_slot           ngx_conf_set_str_slot




