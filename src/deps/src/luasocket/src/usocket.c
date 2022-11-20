/*=========================================================================*\
* Socket compatibilization module for Unix
* LuaSocket toolkit
*
* The code is now interrupt-safe.
* The penalty of calling select to avoid busy-wait is only paid when
* the I/O call fail in the first place.
\*=========================================================================*/
#include "luasocket.h"

#include "socket.h"
#include "pierror.h"

#include <string.h>
#include <signal.h>

/*-------------------------------------------------------------------------*\
* Wait for readable/writable/connected socket with timeout
\*-------------------------------------------------------------------------*/
#ifndef SOCKET_SELECT
#include <sys/poll.h>

#define WAITFD_R        POLLIN
#define WAITFD_W        POLLOUT
#define WAITFD_C        (POLLIN|POLLOUT)
int socket_waitfd(p_socket ps, int sw, p_timeout tm) {
    int ret;
    struct pollfd pfd;
    pfd.fd = *ps;
    pfd.events = sw;
    pfd.revents = 0;
    if (timeout_iszero(tm)) return IO_TIMEOUT;  /* optimize timeout == 0 case */
    do {
        int t = (int)(timeout_getretry(tm)*1e3);
        ret = poll(&pfd, 1, t >= 0? t: -1);
    } while (ret == -1 && errno == EINTR);
    if (ret == -1) return errno;
    if (ret == 0) return IO_TIMEOUT;
    if (sw == WAITFD_C && (pfd.revents & (POLLIN|POLLERR))) return IO_CLOSED;
    return IO_DONE;
}
#else

#define WAITFD_R        1
#define WAITFD_W        2
#define WAITFD_C        (WAITFD_R|WAITFD_W)

int socket_waitfd(p_socket ps, int sw, p_timeout tm) {
    int ret;
    fd_set rfds, wfds, *rp, *wp;
    struct timeval tv, *tp;
    double t;
    if (*ps >= FD_SETSIZE) return EINVAL;
    if (timeout_iszero(tm)) return IO_TIMEOUT;  /* optimize timeout == 0 case */
    do {
        /* must set bits within loop, because select may have modifed them */
        rp = wp = NULL;
        if (sw & WAITFD_R) { FD_ZERO(&rfds); FD_SET(*ps, &rfds); rp = &rfds; }
        if (sw & WAITFD_W) { FD_ZERO(&wfds); FD_SET(*ps, &wfds); wp = &wfds; }
        t = timeout_getretry(tm);
        tp = NULL;
        if (t >= 0.0) {
            tv.tv_sec = (int)t;
            tv.tv_usec = (int)((t-tv.tv_sec)*1.0e6);
            tp = &tv;
        }
        ret = select(*ps+1, rp, wp, NULL, tp);
    } while (ret == -1 && errno == EINTR);
    if (ret == -1) return errno;
    if (ret == 0) return IO_TIMEOUT;
    if (sw == WAITFD_C && FD_ISSET(*ps, &rfds)) return IO_CLOSED;
    return IO_DONE;
}
#endif


/*-------------------------------------------------------------------------*\
* Initializes module
\*-------------------------------------------------------------------------*/
int socket_open(void) {
    /* installs a handler to ignore sigpipe or it will crash us */
    signal(SIGPIPE, SIG_IGN);
    return 1;
}

/*-------------------------------------------------------------------------*\
* Close module
\*-------------------------------------------------------------------------*/
int socket_close(void) {
    return 1;
}

/*-------------------------------------------------------------------------*\
* Close and inutilize socket
\*-------------------------------------------------------------------------*/
void socket_destroy(p_socket ps) {
    if (*ps != SOCKET_INVALID) {
        close(*ps);
        *ps = SOCKET_INVALID;
    }
}

/*-------------------------------------------------------------------------*\
* Select with timeout control
\*-------------------------------------------------------------------------*/
int socket_select(t_socket n, fd_set *rfds, fd_set *wfds, fd_set *efds,
        p_timeout tm) {
    int ret;
    do {
        struct timeval tv;
        double t = timeout_getretry(tm);
        tv.tv_sec = (int) t;
        tv.tv_usec = (int) ((t - tv.tv_sec) * 1.0e6);
        /* timeout = 0 means no wait */
        ret = select(n, rfds, wfds, efds, t >= 0.0 ? &tv: NULL);
    } while (ret < 0 && errno == EINTR);
    return ret;
}

/*-------------------------------------------------------------------------*\
* Creates and sets up a socket
\*-------------------------------------------------------------------------*/
int socket_create(p_socket ps, int domain, int type, int protocol) {
    *ps = socket(domain, type, protocol);
    if (*ps != SOCKET_INVALID) return IO_DONE;
    else return errno;
}

/*-------------------------------------------------------------------------*\
* Binds or returns error message
\*-------------------------------------------------------------------------*/
int socket_bind(p_socket ps, SA *addr, socklen_t len) {
    int err = IO_DONE;
    socket_setblocking(ps);
    if (bind(*ps, addr, len) < 0) err = errno;
    socket_setnonblocking(ps);
    return err;
}

/*-------------------------------------------------------------------------*\
*
\*-------------------------------------------------------------------------*/
int socket_listen(p_socket ps, int backlog) {
    int err = IO_DONE;
    if (listen(*ps, backlog)) err = errno;
    return err;
}

/*-------------------------------------------------------------------------*\
*
\*-------------------------------------------------------------------------*/
void socket_shutdown(p_socket ps, int how) {
    shutdown(*ps, how);
}

/*-------------------------------------------------------------------------*\
* Connects or returns error message
\*-------------------------------------------------------------------------*/
int socket_connect(p_socket ps, SA *addr, socklen_t len, p_timeout tm) {
    int err;
    /* avoid calling on closed sockets */
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    /* call connect until done or failed without being interrupted */
    do if (connect(*ps, addr, len) == 0) return IO_DONE;
    while ((err = errno) == EINTR);
    /* if connection failed immediately, return error code */
    if (err != EINPROGRESS && err != EAGAIN) return err;
    /* zero timeout case optimization */
    if (timeout_iszero(tm)) return IO_TIMEOUT;
    /* wait until we have the result of the connection attempt or timeout */
    err = socket_waitfd(ps, WAITFD_C, tm);
    if (err == IO_CLOSED) {
        if (recv(*ps, (char *) &err, 0, 0) == 0) return IO_DONE;
        else return errno;
    } else return err;
}

/*-------------------------------------------------------------------------*\
* Accept with timeout
\*-------------------------------------------------------------------------*/
int socket_accept(p_socket ps, p_socket pa, SA *addr, socklen_t *len, p_timeout tm) {
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    for ( ;; ) {
        int err;
        if ((*pa = accept(*ps, addr, len)) != SOCKET_INVALID) return IO_DONE;
        err = errno;
        if (err == EINTR) continue;
        if (err != EAGAIN && err != ECONNABORTED) return err;
        if ((err = socket_waitfd(ps, WAITFD_R, tm)) != IO_DONE) return err;
    }
    /* can't reach here */
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Send with timeout
\*-------------------------------------------------------------------------*/
int socket_send(p_socket ps, const char *data, size_t count,
        size_t *sent, p_timeout tm)
{
    int err;
    *sent = 0;
    /* avoid making system calls on closed sockets */
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    /* loop until we send something or we give up on error */
    for ( ;; ) {
        long put = (long) send(*ps, data, count, 0);
        /* if we sent anything, we are done */
        if (put >= 0) {
            *sent = put;
            return IO_DONE;
        }
        err = errno;
        /* EPIPE means the connection was closed */
        if (err == EPIPE) return IO_CLOSED;
        /* EPROTOTYPE means the connection is being closed (on Yosemite!)*/
        if (err == EPROTOTYPE) continue;
        /* we call was interrupted, just try again */
        if (err == EINTR) continue;
        /* if failed fatal reason, report error */
        if (err != EAGAIN) return err;
        /* wait until we can send something or we timeout */
        if ((err = socket_waitfd(ps, WAITFD_W, tm)) != IO_DONE) return err;
    }
    /* can't reach here */
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Sendto with timeout
\*-------------------------------------------------------------------------*/
int socket_sendto(p_socket ps, const char *data, size_t count, size_t *sent,
        SA *addr, socklen_t len, p_timeout tm)
{
    int err;
    *sent = 0;
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    for ( ;; ) {
        long put = (long) sendto(*ps, data, count, 0, addr, len); 
        if (put >= 0) {
            *sent = put;
            return IO_DONE;
        }
        err = errno;
        if (err == EPIPE) return IO_CLOSED;
        if (err == EPROTOTYPE) continue;
        if (err == EINTR) continue;
        if (err != EAGAIN) return err;
        if ((err = socket_waitfd(ps, WAITFD_W, tm)) != IO_DONE) return err;
    }
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Receive with timeout
\*-------------------------------------------------------------------------*/
int socket_recv(p_socket ps, char *data, size_t count, size_t *got, p_timeout tm) {
    int err;
    *got = 0;
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    for ( ;; ) {
        long taken = (long) recv(*ps, data, count, 0);
        if (taken > 0) {
            *got = taken;
            return IO_DONE;
        }
        err = errno;
        if (taken == 0) return IO_CLOSED;
        if (err == EINTR) continue;
        if (err != EAGAIN) return err;
        if ((err = socket_waitfd(ps, WAITFD_R, tm)) != IO_DONE) return err;
    }
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Recvfrom with timeout
\*-------------------------------------------------------------------------*/
int socket_recvfrom(p_socket ps, char *data, size_t count, size_t *got,
        SA *addr, socklen_t *len, p_timeout tm) {
    int err;
    *got = 0;
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    for ( ;; ) {
        long taken = (long) recvfrom(*ps, data, count, 0, addr, len);
        if (taken > 0) {
            *got = taken;
            return IO_DONE;
        }
        err = errno;
        if (taken == 0) return IO_CLOSED;
        if (err == EINTR) continue;
        if (err != EAGAIN) return err;
        if ((err = socket_waitfd(ps, WAITFD_R, tm)) != IO_DONE) return err;
    }
    return IO_UNKNOWN;
}


/*-------------------------------------------------------------------------*\
* Write with timeout
*
* socket_read and socket_write are cut-n-paste of socket_send and socket_recv,
* with send/recv replaced with write/read. We can't just use write/read
* in the socket version, because behaviour when size is zero is different.
\*-------------------------------------------------------------------------*/
int socket_write(p_socket ps, const char *data, size_t count,
        size_t *sent, p_timeout tm)
{
    int err;
    *sent = 0;
    /* avoid making system calls on closed sockets */
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    /* loop until we send something or we give up on error */
    for ( ;; ) {
        long put = (long) write(*ps, data, count);
        /* if we sent anything, we are done */
        if (put >= 0) {
            *sent = put;
            return IO_DONE;
        }
        err = errno;
        /* EPIPE means the connection was closed */
        if (err == EPIPE) return IO_CLOSED;
        /* EPROTOTYPE means the connection is being closed (on Yosemite!)*/
        if (err == EPROTOTYPE) continue;
        /* we call was interrupted, just try again */
        if (err == EINTR) continue;
        /* if failed fatal reason, report error */
        if (err != EAGAIN) return err;
        /* wait until we can send something or we timeout */
        if ((err = socket_waitfd(ps, WAITFD_W, tm)) != IO_DONE) return err;
    }
    /* can't reach here */
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Read with timeout
* See note for socket_write
\*-------------------------------------------------------------------------*/
int socket_read(p_socket ps, char *data, size_t count, size_t *got, p_timeout tm) {
    int err;
    *got = 0;
    if (*ps == SOCKET_INVALID) return IO_CLOSED;
    for ( ;; ) {
        long taken = (long) read(*ps, data, count);
        if (taken > 0) {
            *got = taken;
            return IO_DONE;
        }
        err = errno;
        if (taken == 0) return IO_CLOSED;
        if (err == EINTR) continue;
        if (err != EAGAIN) return err;
        if ((err = socket_waitfd(ps, WAITFD_R, tm)) != IO_DONE) return err;
    }
    return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Put socket into blocking mode
\*-------------------------------------------------------------------------*/
void socket_setblocking(p_socket ps) {
    int flags = fcntl(*ps, F_GETFL, 0);
    flags &= (~(O_NONBLOCK));
    fcntl(*ps, F_SETFL, flags);
}

/*-------------------------------------------------------------------------*\
* Put socket into non-blocking mode
\*-------------------------------------------------------------------------*/
void socket_setnonblocking(p_socket ps) {
    int flags = fcntl(*ps, F_GETFL, 0);
    flags |= O_NONBLOCK;
    fcntl(*ps, F_SETFL, flags);
}

/*-------------------------------------------------------------------------*\
* DNS helpers
\*-------------------------------------------------------------------------*/
int socket_gethostbyaddr(const char *addr, socklen_t len, struct hostent **hp) {
    *hp = gethostbyaddr(addr, len, AF_INET);
    if (*hp) return IO_DONE;
    else if (h_errno) return h_errno;
    else if (errno) return errno;
    else return IO_UNKNOWN;
}

int socket_gethostbyname(const char *addr, struct hostent **hp) {
    *hp = gethostbyname(addr);
    if (*hp) return IO_DONE;
    else if (h_errno) return h_errno;
    else if (errno) return errno;
    else return IO_UNKNOWN;
}

/*-------------------------------------------------------------------------*\
* Error translation functions
* Make sure important error messages are standard
\*-------------------------------------------------------------------------*/
const char *socket_hoststrerror(int err) {
    if (err <= 0) return io_strerror(err);
    switch (err) {
        case HOST_NOT_FOUND: return PIE_HOST_NOT_FOUND;
        default: return hstrerror(err);
    }
}

const char *socket_strerror(int err) {
    if (err <= 0) return io_strerror(err);
    switch (err) {
        case EADDRINUSE: return PIE_ADDRINUSE;
        case EISCONN: return PIE_ISCONN;
        case EACCES: return PIE_ACCESS;
        case ECONNREFUSED: return PIE_CONNREFUSED;
        case ECONNABORTED: return PIE_CONNABORTED;
        case ECONNRESET: return PIE_CONNRESET;
        case ETIMEDOUT: return PIE_TIMEDOUT;
        default: {
            return strerror(err);
        }
    }
}

const char *socket_ioerror(p_socket ps, int err) {
    (void) ps;
    return socket_strerror(err);
}

const char *socket_gaistrerror(int err) {
    if (err == 0) return NULL;
    switch (err) {
        case EAI_AGAIN: return PIE_AGAIN;
        case EAI_BADFLAGS: return PIE_BADFLAGS;
#ifdef EAI_BADHINTS
        case EAI_BADHINTS: return PIE_BADHINTS;
#endif
        case EAI_FAIL: return PIE_FAIL;
        case EAI_FAMILY: return PIE_FAMILY;
        case EAI_MEMORY: return PIE_MEMORY;
        case EAI_NONAME: return PIE_NONAME;
#ifdef EAI_OVERFLOW
        case EAI_OVERFLOW: return PIE_OVERFLOW;
#endif
#ifdef EAI_PROTOCOL
        case EAI_PROTOCOL: return PIE_PROTOCOL;
#endif
        case EAI_SERVICE: return PIE_SERVICE;
        case EAI_SOCKTYPE: return PIE_SOCKTYPE;
        case EAI_SYSTEM: return strerror(errno);
        default: return LUA_GAI_STRERROR(err);
    }
}
