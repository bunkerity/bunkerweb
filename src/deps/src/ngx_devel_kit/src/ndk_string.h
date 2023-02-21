

#if 1
/* TODO : set ndk_hex_dump for older versions of Nginx */
#define     ndk_hex_dump                    ngx_hex_dump
#endif

typedef struct {
    size_t          len;
    u_char         *data;
    ngx_flag_t      escaped;
} ndk_estr_t;

int64_t         ndk_atoi64                  (u_char *line, size_t n);

ngx_int_t       ndk_strcntc                 (ngx_str_t *s, char c);
ngx_int_t       ndk_strccnt                 (char *s, char c);
ngx_array_t *   ndk_str_array_create        (ngx_pool_t *pool, char **s, ngx_int_t n);
u_char *        ndk_catstrf                 (ngx_pool_t *pool, ngx_str_t *dest, const char *fmt, ...);
ngx_int_t       ndk_cmpstr                  (ngx_str_t *s1, ngx_str_t *s2);
u_char *        ndk_dupstr                  (ngx_pool_t *pool, ngx_str_t *dest, ngx_str_t *src);

static ngx_inline void
ndk_strtoupper (u_char *p, size_t len)
{
    u_char *e = p + len;
    for ( ; p<e; p++) {
        *p = ngx_toupper(*p);
    }
}


static ngx_inline u_char *
ndk_strncpy (u_char *d, u_char *s, size_t n)
{
    return  (u_char *) strncpy ((char *) d, (char *) s, n);
}
