

#include    <iconv.h>

typedef struct {
    char        *from;
    char        *to;
} ndk_encoding_t;


char *  ndk_conf_set_encoding_slot  (ngx_conf_t *cf, ngx_command_t *cmd, void *conf);

