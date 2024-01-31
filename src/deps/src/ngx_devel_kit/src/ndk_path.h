

/* path conversion functions */

void            ndk_clean_path                  (ngx_str_t *path, ngx_uint_t complex, size_t off);
void            ndk_path_to_dir_safe            (ngx_str_t *path, ngx_uint_t complex, size_t off);

/* path create functions */

ngx_array_t *   ndk_split_path_create           (ngx_conf_t *cf, ngx_str_t *path);
ngx_array_t *   ndk_split_path_create_raw       (ngx_conf_t *cf, char *path);

/* conf set functions */

char *          ndk_conf_set_full_path_slot     (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);
char *          ndk_conf_set_split_path_slot    (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

/* conf set post functions */

char *          ndk_conf_set_full_path          (ngx_conf_t *cf, void *data, ngx_str_t *path);
char *          ndk_conf_set_full_conf_path     (ngx_conf_t *cf, void *data, ngx_str_t *path);

