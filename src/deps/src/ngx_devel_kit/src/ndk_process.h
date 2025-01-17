

typedef struct {
    int     signo;
    char   *signame;
    char   *name;
    void  (*handler)(int signo);
} ngx_signal_t;


ngx_int_t   ndk_init_signals    (ngx_signal_t *sig, ngx_log_t *log);

