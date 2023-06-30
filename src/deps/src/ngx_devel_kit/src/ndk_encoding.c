


char *
ndk_conf_set_encoding_slot (ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char    *p = conf;

    ndk_encoding_t  *ep;
    ngx_str_t       *value;
    size_t           len;
    iconv_t          ic;

    ep = (ndk_encoding_t *) (p + cmd->offset);
    if (ep->from && ep->to)
        return  "is duplicate";

    value = cf->args->elts;


    if (ep->from) {

        ep->to = (char *) value[1].data;
        len = strlen (ep->from);

    } else if (ep->to) {

        ep->from = (char *) value[1].data;
        len = strlen (ep->to);

    } else {
        return  "has no base encoding";
    }


    if (len == value[1].len && !strncasecmp (ep->to, ep->from, len)) {

        ngx_log_error (NGX_LOG_WARN, cf->log, 0, 
            "\"%V\" '%V' encoding is ignored (no conversion)", &value[0], &value[1]);

        return  NGX_CONF_OK;
    }


    ic = iconv_open (ep->to, ep->from);
    if (ic == (iconv_t)-1)
        return  "has an invalid encoding";


    if (iconv_close (ic)) {
        ngx_log_error (NGX_LOG_EMERG, cf->log, errno, "iconv_close()");
        return  NGX_CONF_ERROR;
    }

    return  NGX_CONF_OK;
}

