
/* TODO : check that all the main types have a corresponding merge function */

#define     ndk_conf_merge_value            ngx_conf_merge_value
#define     ndk_conf_merge_off_value        ngx_conf_merge_off_value 
#define     ndk_conf_merge_ptr_value        ngx_conf_merge_ptr_value
#define     ndk_conf_merge_str_value        ngx_conf_merge_str_value
#define     ndk_conf_merge_size_value       ngx_conf_merge_size_value 


#define     ndk_conf_merge_keyval_value(conf,prev,default)                                  \
                                                                                            \
                conf = prev ? prev : default;

#define     ndk_conf_merge_str_array_value(conf,prev,val1,...)                              \
                                                                                            \
                if (conf == NGX_CONF_UNSET_PTR) {                                           \
                    if (prev == NGX_CONF_UNSET_PTR) {                                       \
                        if (val1 == NULL) {                                                 \
                            conf = NULL;                                                    \
                        } else {                                                            \
                            char * elts[] = {val1,##__VA_ARGS__};                           \
                            int    n = sizeof(elts)/sizeof(char*);                          \
                                                                                            \
                            conf = ndk_str_array_create (cf->pool, elts, n);                \
                                                                                            \
                            if (conf == NULL)                                               \
                                return  NGX_CONF_ERROR;                                     \
                        }                                                                   \
                    } else {                                                                \
                        conf = prev;                                                        \
                    }                                                                       \
                }

#define     ndk_conf_merge_http_complex_value_value(conf,prev,default)                      \
                                                                                            \
                if (!conf.str.len) {                                                        \
                    if (prev.str.len) {                                                     \
                        conf = prev;                                                        \
                    } else {                                                                \
                        conf.str.data = (u_char *) default;                                 \
                        conf.str.len = sizeof (default) - 1;                                \
                                                                                            \
                        if (ndk_http_complex_value_compile (cf, &conf))                     \
                            return  NGX_CONF_ERROR;                                         \
                    }                                                                       \
                }

#define     ndk_conf_merge_http_complex_value_array_value(conf,prev,val1,...)               \
                                                                                            \
                if (conf == NGX_CONF_UNSET_PTR) {                                           \
                    if (prev == NGX_CONF_UNSET_PTR) {                                       \
                        if (val1 == NULL)                                                   \
                            conf = NULL;                                                    \
                        else {                                                              \
                            char * elts[] = {val1,##__VA_ARGS__};                           \
                            int    n = sizeof(elts)/sizeof(char*);                          \
                                                                                            \
                            conf = ndk_http_complex_value_array_create (cf, elts, n);       \
                                                                                            \
                            if (conf == NULL)                                               \
                                return  NGX_CONF_ERROR;                                     \
                        }                                                                   \
                    } else {                                                                \
                        conf = prev;                                                        \
                    }                                                                       \
                }

#define     ndk_conf_merge_http_complex_path_value(conf,prev,...)                           \
                ndk_conf_merge_http_complex_value_array_value (conf.a, prev.a, __VA_ARGS__)

#define     ndk_conf_merge_split_path_value(conf,prev,path)                                 \
                                                                                            \
                if (conf == NGX_CONF_UNSET_PTR)  {                                          \
                    conf = (prev == NGX_CONF_UNSET_PTR ?                                    \
                        ndk_split_path_create_raw (cf, path) : prev);                       \
                }

