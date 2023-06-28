
ngx_int_t
ndk_copy_chain_to_str (ngx_pool_t *pool, ngx_chain_t *in, ngx_str_t *str)
{
    ngx_chain_t     *cl;
    size_t           len;
    u_char          *p;
    ngx_buf_t       *b;
    
    len = 0;
    for (cl = in; cl; cl = cl->next)
        len += ngx_buf_size (cl->buf);
    
    ndk_palloc_re (p, pool, len + 1);
    
    str->data = p;
    str->len = len;
    
    for (cl = in; cl; cl = cl->next) {
        
        b = cl->buf;
        
        if (ngx_buf_in_memory (b)) {
            p = ngx_cpymem (p, b->pos, b->last - b->pos);
        }
    }
    
    *p = '\0';
    
    return  NGX_OK;
}


char *
ndk_copy_chain_to_charp (ngx_pool_t *pool, ngx_chain_t *in)
{
    ngx_str_t   str;
    
    if (ndk_copy_chain_to_str (pool, in, &str) != NGX_OK)
        return  NULL;
    
    return  (char *) str.data;
}