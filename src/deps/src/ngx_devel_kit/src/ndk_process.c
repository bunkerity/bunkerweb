
ngx_int_t
ndk_init_signals (ngx_signal_t *sig, ngx_log_t *log)
{
    struct sigaction   sa;

    for ( ; sig->signo != 0; sig++) {
        ndk_zerov (sa);
        sa.sa_handler = sig->handler;
        sigemptyset (&sa.sa_mask);
        
        if (sigaction (sig->signo, &sa, NULL) == -1) {
            ngx_log_error (NGX_LOG_EMERG, log, ngx_errno,
                          "sigaction(%s) failed", sig->signame);
            return NGX_ERROR;
        }
    }

    return NGX_OK;
}
