/** \file ssl_helpers.c
 *
 * \brief Helper functions to set up a TLS connection.
 */

/*
 *  Copyright The Mbed TLS Contributors
 *  SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
 */

#include <test/ssl_helpers.h>
#include "mbedtls/psa_util.h"

#if defined(MBEDTLS_SSL_TLS_C)
int mbedtls_test_random(void *p_rng, unsigned char *output, size_t output_len)
{
    (void) p_rng;
    for (size_t i = 0; i < output_len; i++) {
        output[i] = rand();
    }

    return 0;
}

void mbedtls_test_ssl_log_analyzer(void *ctx, int level,
                                   const char *file, int line,
                                   const char *str)
{
    mbedtls_test_ssl_log_pattern *p = (mbedtls_test_ssl_log_pattern *) ctx;

    (void) level;
    (void) line;
    (void) file;

    if (NULL != p &&
        NULL != p->pattern &&
        NULL != strstr(str, p->pattern)) {
        p->counter++;
    }
}

void mbedtls_test_init_handshake_options(
    mbedtls_test_handshake_test_options *opts)
{
#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)
    static int rng_seed = 0xBEEF;

    srand(rng_seed);
    rng_seed += 0xD0;
#endif

    memset(opts, 0, sizeof(*opts));

    opts->cipher = "";
    opts->client_min_version = MBEDTLS_SSL_VERSION_UNKNOWN;
    opts->client_max_version = MBEDTLS_SSL_VERSION_UNKNOWN;
    opts->server_min_version = MBEDTLS_SSL_VERSION_UNKNOWN;
    opts->server_max_version = MBEDTLS_SSL_VERSION_UNKNOWN;
    opts->expected_negotiated_version = MBEDTLS_SSL_VERSION_TLS1_3;
    opts->pk_alg = MBEDTLS_PK_RSA;
    opts->srv_auth_mode = MBEDTLS_SSL_VERIFY_NONE;
    opts->mfl = MBEDTLS_SSL_MAX_FRAG_LEN_NONE;
    opts->cli_msg_len = 100;
    opts->srv_msg_len = 100;
    opts->expected_cli_fragments = 1;
    opts->expected_srv_fragments = 1;
    opts->legacy_renegotiation = MBEDTLS_SSL_LEGACY_NO_RENEGOTIATION;
    opts->resize_buffers = 1;
    opts->early_data = MBEDTLS_SSL_EARLY_DATA_DISABLED;
    opts->max_early_data_size = -1;
#if defined(MBEDTLS_SSL_CACHE_C)
    TEST_CALLOC(opts->cache, 1);
    mbedtls_ssl_cache_init(opts->cache);
#if defined(MBEDTLS_HAVE_TIME)
    TEST_EQUAL(mbedtls_ssl_cache_get_timeout(opts->cache),
               MBEDTLS_SSL_CACHE_DEFAULT_TIMEOUT);
#endif
exit:
    return;
#endif
}

void mbedtls_test_free_handshake_options(
    mbedtls_test_handshake_test_options *opts)
{
#if defined(MBEDTLS_SSL_CACHE_C)
    mbedtls_ssl_cache_free(opts->cache);
    mbedtls_free(opts->cache);
#else
    (void) opts;
#endif
}

#if defined(MBEDTLS_TEST_HOOKS)
static void set_chk_buf_ptr_args(
    mbedtls_ssl_chk_buf_ptr_args *args,
    unsigned char *cur, unsigned char *end, size_t need)
{
    args->cur = cur;
    args->end = end;
    args->need = need;
}

static void reset_chk_buf_ptr_args(mbedtls_ssl_chk_buf_ptr_args *args)
{
    memset(args, 0, sizeof(*args));
}
#endif /* MBEDTLS_TEST_HOOKS */

void mbedtls_test_ssl_buffer_init(mbedtls_test_ssl_buffer *buf)
{
    memset(buf, 0, sizeof(*buf));
}

int mbedtls_test_ssl_buffer_setup(mbedtls_test_ssl_buffer *buf,
                                  size_t capacity)
{
    buf->buffer = (unsigned char *) mbedtls_calloc(capacity,
                                                   sizeof(unsigned char));
    if (NULL == buf->buffer) {
        return MBEDTLS_ERR_SSL_ALLOC_FAILED;
    }
    buf->capacity = capacity;

    return 0;
}

void mbedtls_test_ssl_buffer_free(mbedtls_test_ssl_buffer *buf)
{
    if (buf->buffer != NULL) {
        mbedtls_free(buf->buffer);
    }

    memset(buf, 0, sizeof(*buf));
}

int mbedtls_test_ssl_buffer_put(mbedtls_test_ssl_buffer *buf,
                                const unsigned char *input, size_t input_len)
{
    size_t overflow = 0;

    if ((buf == NULL) || (buf->buffer == NULL)) {
        return -1;
    }

    /* Reduce input_len to a number that fits in the buffer. */
    if ((buf->content_length + input_len) > buf->capacity) {
        input_len = buf->capacity - buf->content_length;
    }

    if (input == NULL) {
        return (input_len == 0) ? 0 : -1;
    }

    /* Check if the buffer has not come full circle and free space is not in
     * the middle */
    if (buf->start + buf->content_length < buf->capacity) {

        /* Calculate the number of bytes that need to be placed at lower memory
         * address */
        if (buf->start + buf->content_length + input_len
            > buf->capacity) {
            overflow = (buf->start + buf->content_length + input_len)
                       % buf->capacity;
        }

        memcpy(buf->buffer + buf->start + buf->content_length, input,
               input_len - overflow);
        memcpy(buf->buffer, input + input_len - overflow, overflow);

    } else {
        /* The buffer has come full circle and free space is in the middle */
        memcpy(buf->buffer + buf->start + buf->content_length - buf->capacity,
               input, input_len);
    }

    buf->content_length += input_len;
    return (input_len > INT_MAX) ? INT_MAX : (int) input_len;
}

int mbedtls_test_ssl_buffer_get(mbedtls_test_ssl_buffer *buf,
                                unsigned char *output, size_t output_len)
{
    size_t overflow = 0;

    if ((buf == NULL) || (buf->buffer == NULL)) {
        return -1;
    }

    if (output == NULL && output_len == 0) {
        return 0;
    }

    if (buf->content_length < output_len) {
        output_len = buf->content_length;
    }

    /* Calculate the number of bytes that need to be drawn from lower memory
     * address */
    if (buf->start + output_len > buf->capacity) {
        overflow = (buf->start + output_len) % buf->capacity;
    }

    if (output != NULL) {
        memcpy(output, buf->buffer + buf->start, output_len - overflow);
        memcpy(output + output_len - overflow, buf->buffer, overflow);
    }

    buf->content_length -= output_len;
    buf->start = (buf->start + output_len) % buf->capacity;

    return (output_len > INT_MAX) ? INT_MAX : (int) output_len;
}

int mbedtls_test_ssl_message_queue_setup(
    mbedtls_test_ssl_message_queue *queue, size_t capacity)
{
    queue->messages = (size_t *) mbedtls_calloc(capacity, sizeof(size_t));
    if (NULL == queue->messages) {
        return MBEDTLS_ERR_SSL_ALLOC_FAILED;
    }

    queue->capacity = (capacity > INT_MAX) ? INT_MAX : (int) capacity;
    queue->pos = 0;
    queue->num = 0;

    return 0;
}

void mbedtls_test_ssl_message_queue_free(
    mbedtls_test_ssl_message_queue *queue)
{
    if (queue == NULL) {
        return;
    }

    if (queue->messages != NULL) {
        mbedtls_free(queue->messages);
    }

    memset(queue, 0, sizeof(*queue));
}

int mbedtls_test_ssl_message_queue_push_info(
    mbedtls_test_ssl_message_queue *queue, size_t len)
{
    int place;
    if (queue == NULL) {
        return MBEDTLS_TEST_ERROR_ARG_NULL;
    }

    if (queue->num >= queue->capacity) {
        return MBEDTLS_ERR_SSL_WANT_WRITE;
    }

    place = (queue->pos + queue->num) % queue->capacity;
    queue->messages[place] = len;
    queue->num++;
    return (len > INT_MAX) ? INT_MAX : (int) len;
}

int mbedtls_test_ssl_message_queue_pop_info(
    mbedtls_test_ssl_message_queue *queue, size_t buf_len)
{
    size_t message_length;
    if (queue == NULL) {
        return MBEDTLS_TEST_ERROR_ARG_NULL;
    }
    if (queue->num == 0) {
        return MBEDTLS_ERR_SSL_WANT_READ;
    }

    message_length = queue->messages[queue->pos];
    queue->messages[queue->pos] = 0;
    queue->num--;
    queue->pos++;
    queue->pos %= queue->capacity;
    if (queue->pos < 0) {
        queue->pos += queue->capacity;
    }

    return (message_length > INT_MAX && buf_len > INT_MAX) ? INT_MAX :
           (message_length > buf_len) ? (int) buf_len : (int) message_length;
}

/*
 * Take a peek on the info about the next message length from the queue.
 * This will be the oldest inserted message length(fifo).
 *
 * \retval  MBEDTLS_TEST_ERROR_ARG_NULL, if the queue is null.
 * \retval  MBEDTLS_ERR_SSL_WANT_READ, if the queue is empty.
 * \retval  0, if the peek was successful.
 * \retval  MBEDTLS_TEST_ERROR_MESSAGE_TRUNCATED, if the given buffer length is
 *          too small to fit the message. In this case the \p msg_len will be
 *          set to the full message length so that the
 *          caller knows what portion of the message can be dropped.
 */
static int test_ssl_message_queue_peek_info(
    mbedtls_test_ssl_message_queue *queue,
    size_t buf_len, size_t *msg_len)
{
    if (queue == NULL || msg_len == NULL) {
        return MBEDTLS_TEST_ERROR_ARG_NULL;
    }
    if (queue->num == 0) {
        return MBEDTLS_ERR_SSL_WANT_READ;
    }

    *msg_len = queue->messages[queue->pos];
    return (*msg_len > buf_len) ? MBEDTLS_TEST_ERROR_MESSAGE_TRUNCATED : 0;
}

void mbedtls_test_mock_socket_init(mbedtls_test_mock_socket *socket)
{
    memset(socket, 0, sizeof(*socket));
}

void mbedtls_test_mock_socket_close(mbedtls_test_mock_socket *socket)
{
    if (socket == NULL) {
        return;
    }

    if (socket->input != NULL) {
        mbedtls_test_ssl_buffer_free(socket->input);
        mbedtls_free(socket->input);
    }

    if (socket->output != NULL) {
        mbedtls_test_ssl_buffer_free(socket->output);
        mbedtls_free(socket->output);
    }

    if (socket->peer != NULL) {
        memset(socket->peer, 0, sizeof(*socket->peer));
    }

    memset(socket, 0, sizeof(*socket));
}

int mbedtls_test_mock_socket_connect(mbedtls_test_mock_socket *peer1,
                                     mbedtls_test_mock_socket *peer2,
                                     size_t bufsize)
{
    int ret = -1;

    peer1->output =
        (mbedtls_test_ssl_buffer *) mbedtls_calloc(
            1, sizeof(mbedtls_test_ssl_buffer));
    if (peer1->output == NULL) {
        ret = MBEDTLS_ERR_SSL_ALLOC_FAILED;
        goto exit;
    }
    mbedtls_test_ssl_buffer_init(peer1->output);
    if (0 != (ret = mbedtls_test_ssl_buffer_setup(peer1->output, bufsize))) {
        goto exit;
    }

    peer2->output =
        (mbedtls_test_ssl_buffer *) mbedtls_calloc(
            1, sizeof(mbedtls_test_ssl_buffer));
    if (peer2->output == NULL) {
        ret = MBEDTLS_ERR_SSL_ALLOC_FAILED;
        goto exit;
    }
    mbedtls_test_ssl_buffer_init(peer2->output);
    if (0 != (ret = mbedtls_test_ssl_buffer_setup(peer2->output, bufsize))) {
        goto exit;
    }

    peer1->peer = peer2;
    peer2->peer = peer1;
    peer1->input = peer2->output;
    peer2->input = peer1->output;

    peer1->status = peer2->status = MBEDTLS_MOCK_SOCKET_CONNECTED;
    ret = 0;

exit:

    if (ret != 0) {
        mbedtls_test_mock_socket_close(peer1);
        mbedtls_test_mock_socket_close(peer2);
    }

    return ret;
}

int mbedtls_test_mock_tcp_send_b(void *ctx,
                                 const unsigned char *buf, size_t len)
{
    mbedtls_test_mock_socket *socket = (mbedtls_test_mock_socket *) ctx;

    if (socket == NULL || socket->status != MBEDTLS_MOCK_SOCKET_CONNECTED) {
        return -1;
    }

    return mbedtls_test_ssl_buffer_put(socket->output, buf, len);
}

int mbedtls_test_mock_tcp_recv_b(void *ctx, unsigned char *buf, size_t len)
{
    mbedtls_test_mock_socket *socket = (mbedtls_test_mock_socket *) ctx;

    if (socket == NULL || socket->status != MBEDTLS_MOCK_SOCKET_CONNECTED) {
        return -1;
    }

    return mbedtls_test_ssl_buffer_get(socket->input, buf, len);
}

int mbedtls_test_mock_tcp_send_nb(void *ctx,
                                  const unsigned char *buf, size_t len)
{
    mbedtls_test_mock_socket *socket = (mbedtls_test_mock_socket *) ctx;

    if (socket == NULL || socket->status != MBEDTLS_MOCK_SOCKET_CONNECTED) {
        return -1;
    }

    if (socket->output->capacity == socket->output->content_length) {
        return MBEDTLS_ERR_SSL_WANT_WRITE;
    }

    return mbedtls_test_ssl_buffer_put(socket->output, buf, len);
}

int mbedtls_test_mock_tcp_recv_nb(void *ctx, unsigned char *buf, size_t len)
{
    mbedtls_test_mock_socket *socket = (mbedtls_test_mock_socket *) ctx;

    if (socket == NULL || socket->status != MBEDTLS_MOCK_SOCKET_CONNECTED) {
        return -1;
    }

    if (socket->input->content_length == 0) {
        return MBEDTLS_ERR_SSL_WANT_READ;
    }

    return mbedtls_test_ssl_buffer_get(socket->input, buf, len);
}

void mbedtls_test_message_socket_init(
    mbedtls_test_message_socket_context *ctx)
{
    ctx->queue_input = NULL;
    ctx->queue_output = NULL;
    ctx->socket = NULL;
}

int mbedtls_test_message_socket_setup(
    mbedtls_test_ssl_message_queue *queue_input,
    mbedtls_test_ssl_message_queue *queue_output,
    size_t queue_capacity,
    mbedtls_test_mock_socket *socket,
    mbedtls_test_message_socket_context *ctx)
{
    int ret = mbedtls_test_ssl_message_queue_setup(queue_input, queue_capacity);
    if (ret != 0) {
        return ret;
    }
    ctx->queue_input = queue_input;
    ctx->queue_output = queue_output;
    ctx->socket = socket;
    mbedtls_test_mock_socket_init(socket);

    return 0;
}

void mbedtls_test_message_socket_close(
    mbedtls_test_message_socket_context *ctx)
{
    if (ctx == NULL) {
        return;
    }

    mbedtls_test_ssl_message_queue_free(ctx->queue_input);
    mbedtls_test_mock_socket_close(ctx->socket);
    memset(ctx, 0, sizeof(*ctx));
}

int mbedtls_test_mock_tcp_send_msg(void *ctx,
                                   const unsigned char *buf, size_t len)
{
    mbedtls_test_ssl_message_queue *queue;
    mbedtls_test_mock_socket *socket;
    mbedtls_test_message_socket_context *context =
        (mbedtls_test_message_socket_context *) ctx;

    if (context == NULL || context->socket == NULL
        || context->queue_output == NULL) {
        return MBEDTLS_TEST_ERROR_CONTEXT_ERROR;
    }

    queue = context->queue_output;
    socket = context->socket;

    if (queue->num >= queue->capacity) {
        return MBEDTLS_ERR_SSL_WANT_WRITE;
    }

    if (mbedtls_test_mock_tcp_send_b(socket, buf, len) != (int) len) {
        return MBEDTLS_TEST_ERROR_SEND_FAILED;
    }

    return mbedtls_test_ssl_message_queue_push_info(queue, len);
}

int mbedtls_test_mock_tcp_recv_msg(void *ctx,
                                   unsigned char *buf, size_t buf_len)
{
    mbedtls_test_ssl_message_queue *queue;
    mbedtls_test_mock_socket *socket;
    mbedtls_test_message_socket_context *context =
        (mbedtls_test_message_socket_context *) ctx;
    size_t drop_len = 0;
    size_t msg_len;
    int ret;

    if (context == NULL || context->socket == NULL
        || context->queue_input == NULL) {
        return MBEDTLS_TEST_ERROR_CONTEXT_ERROR;
    }

    queue = context->queue_input;
    socket = context->socket;

    /* Peek first, so that in case of a socket error the data remains in
     * the queue. */
    ret = test_ssl_message_queue_peek_info(queue, buf_len, &msg_len);
    if (ret == MBEDTLS_TEST_ERROR_MESSAGE_TRUNCATED) {
        /* Calculate how much to drop */
        drop_len = msg_len - buf_len;

        /* Set the requested message len to be buffer length */
        msg_len = buf_len;
    } else if (ret != 0) {
        return ret;
    }

    if (mbedtls_test_mock_tcp_recv_b(socket, buf, msg_len) != (int) msg_len) {
        return MBEDTLS_TEST_ERROR_RECV_FAILED;
    }

    if (ret == MBEDTLS_TEST_ERROR_MESSAGE_TRUNCATED) {
        /* Drop the remaining part of the message */
        if (mbedtls_test_mock_tcp_recv_b(socket, NULL, drop_len) !=
            (int) drop_len) {
            /* Inconsistent state - part of the message was read,
             * and a part couldn't. Not much we can do here, but it should not
             * happen in test environment, unless forced manually. */
        }
    }
    ret = mbedtls_test_ssl_message_queue_pop_info(queue, buf_len);
    if (ret < 0) {
        return ret;
    }

    return (msg_len > INT_MAX) ? INT_MAX : (int) msg_len;
}

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)

/*
 * Deinitializes certificates from endpoint represented by \p ep.
 */
static void test_ssl_endpoint_certificate_free(mbedtls_test_ssl_endpoint *ep)
{
    mbedtls_test_ssl_endpoint_certificate *cert = &(ep->cert);
    if (cert != NULL) {
        if (cert->ca_cert != NULL) {
            mbedtls_x509_crt_free(cert->ca_cert);
            mbedtls_free(cert->ca_cert);
            cert->ca_cert = NULL;
        }
        if (cert->cert != NULL) {
            mbedtls_x509_crt_free(cert->cert);
            mbedtls_free(cert->cert);
            cert->cert = NULL;
        }
        if (cert->pkey != NULL) {
#if defined(MBEDTLS_USE_PSA_CRYPTO)
            if (mbedtls_pk_get_type(cert->pkey) == MBEDTLS_PK_OPAQUE) {
                psa_destroy_key(cert->pkey->priv_id);
            }
#endif
            mbedtls_pk_free(cert->pkey);
            mbedtls_free(cert->pkey);
            cert->pkey = NULL;
        }
    }
}

int mbedtls_test_ssl_endpoint_certificate_init(mbedtls_test_ssl_endpoint *ep,
                                               int pk_alg,
                                               int opaque_alg, int opaque_alg2,
                                               int opaque_usage)
{
    int i = 0;
    int ret = -1;
    mbedtls_test_ssl_endpoint_certificate *cert = NULL;
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    mbedtls_svc_key_id_t key_slot = MBEDTLS_SVC_KEY_ID_INIT;
#endif

    if (ep == NULL) {
        return MBEDTLS_ERR_SSL_BAD_INPUT_DATA;
    }

    cert = &(ep->cert);
    TEST_CALLOC(cert->ca_cert, 1);
    TEST_CALLOC(cert->cert, 1);
    TEST_CALLOC(cert->pkey, 1);

    mbedtls_x509_crt_init(cert->ca_cert);
    mbedtls_x509_crt_init(cert->cert);
    mbedtls_pk_init(cert->pkey);

    /* Load the trusted CA */

    for (i = 0; mbedtls_test_cas_der[i] != NULL; i++) {
        ret = mbedtls_x509_crt_parse_der(
            cert->ca_cert,
            (const unsigned char *) mbedtls_test_cas_der[i],
            mbedtls_test_cas_der_len[i]);
        TEST_ASSERT(ret == 0);
    }

    /* Load own certificate and private key */

    if (ep->conf.endpoint == MBEDTLS_SSL_IS_SERVER) {
        if (pk_alg == MBEDTLS_PK_RSA) {
            ret = mbedtls_x509_crt_parse(
                cert->cert,
                (const unsigned char *) mbedtls_test_srv_crt_rsa_sha256_der,
                mbedtls_test_srv_crt_rsa_sha256_der_len);
            TEST_ASSERT(ret == 0);

            ret = mbedtls_pk_parse_key(
                cert->pkey,
                (const unsigned char *) mbedtls_test_srv_key_rsa_der,
                mbedtls_test_srv_key_rsa_der_len, NULL, 0,
                mbedtls_test_rnd_std_rand, NULL);
            TEST_ASSERT(ret == 0);
        } else {
            ret = mbedtls_x509_crt_parse(
                cert->cert,
                (const unsigned char *) mbedtls_test_srv_crt_ec_der,
                mbedtls_test_srv_crt_ec_der_len);
            TEST_ASSERT(ret == 0);

            ret = mbedtls_pk_parse_key(
                cert->pkey,
                (const unsigned char *) mbedtls_test_srv_key_ec_der,
                mbedtls_test_srv_key_ec_der_len, NULL, 0,
                mbedtls_test_rnd_std_rand, NULL);
            TEST_ASSERT(ret == 0);
        }
    } else {
        if (pk_alg == MBEDTLS_PK_RSA) {
            ret = mbedtls_x509_crt_parse(
                cert->cert,
                (const unsigned char *) mbedtls_test_cli_crt_rsa_der,
                mbedtls_test_cli_crt_rsa_der_len);
            TEST_ASSERT(ret == 0);

            ret = mbedtls_pk_parse_key(
                cert->pkey,
                (const unsigned char *) mbedtls_test_cli_key_rsa_der,
                mbedtls_test_cli_key_rsa_der_len, NULL, 0,
                mbedtls_test_rnd_std_rand, NULL);
            TEST_ASSERT(ret == 0);
        } else {
            ret = mbedtls_x509_crt_parse(
                cert->cert,
                (const unsigned char *) mbedtls_test_cli_crt_ec_der,
                mbedtls_test_cli_crt_ec_len);
            TEST_ASSERT(ret == 0);

            ret = mbedtls_pk_parse_key(
                cert->pkey,
                (const unsigned char *) mbedtls_test_cli_key_ec_der,
                mbedtls_test_cli_key_ec_der_len, NULL, 0,
                mbedtls_test_rnd_std_rand, NULL);
            TEST_ASSERT(ret == 0);
        }
    }

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    if (opaque_alg != 0) {
        psa_key_attributes_t key_attr = PSA_KEY_ATTRIBUTES_INIT;
        /* Use a fake key usage to get a successful initial guess for the PSA attributes. */
        TEST_EQUAL(mbedtls_pk_get_psa_attributes(cert->pkey, PSA_KEY_USAGE_SIGN_HASH,
                                                 &key_attr), 0);
        /* Then manually usage, alg and alg2 as requested by the test. */
        psa_set_key_usage_flags(&key_attr, opaque_usage);
        psa_set_key_algorithm(&key_attr, opaque_alg);
        if (opaque_alg2 != PSA_ALG_NONE) {
            psa_set_key_enrollment_algorithm(&key_attr, opaque_alg2);
        }
        TEST_EQUAL(mbedtls_pk_import_into_psa(cert->pkey, &key_attr, &key_slot), 0);
        mbedtls_pk_free(cert->pkey);
        mbedtls_pk_init(cert->pkey);
        TEST_EQUAL(mbedtls_pk_setup_opaque(cert->pkey, key_slot), 0);
    }
#else
    (void) opaque_alg;
    (void) opaque_alg2;
    (void) opaque_usage;
#endif

    mbedtls_ssl_conf_ca_chain(&(ep->conf), cert->ca_cert, NULL);

    ret = mbedtls_ssl_conf_own_cert(&(ep->conf), cert->cert,
                                    cert->pkey);
    TEST_ASSERT(ret == 0);
    TEST_ASSERT(ep->conf.key_cert != NULL);

    ret = mbedtls_ssl_conf_own_cert(&(ep->conf), NULL, NULL);
    TEST_ASSERT(ret == 0);
    TEST_ASSERT(ep->conf.key_cert == NULL);

    ret = mbedtls_ssl_conf_own_cert(&(ep->conf), cert->cert,
                                    cert->pkey);
    TEST_ASSERT(ret == 0);

exit:
    if (ret != 0) {
        test_ssl_endpoint_certificate_free(ep);
    }

    return ret;
}

int mbedtls_test_ssl_endpoint_init(
    mbedtls_test_ssl_endpoint *ep, int endpoint_type,
    mbedtls_test_handshake_test_options *options,
    mbedtls_test_message_socket_context *dtls_context,
    mbedtls_test_ssl_message_queue *input_queue,
    mbedtls_test_ssl_message_queue *output_queue)
{
    int ret = -1;
    uintptr_t user_data_n;

    if (dtls_context != NULL &&
        (input_queue == NULL || output_queue == NULL)) {
        return MBEDTLS_ERR_SSL_BAD_INPUT_DATA;

    }

    if (ep == NULL) {
        return MBEDTLS_ERR_SSL_BAD_INPUT_DATA;
    }

    memset(ep, 0, sizeof(*ep));

    ep->name = (endpoint_type == MBEDTLS_SSL_IS_SERVER) ? "Server" : "Client";

    mbedtls_ssl_init(&(ep->ssl));
    mbedtls_ssl_config_init(&(ep->conf));
    mbedtls_ssl_conf_rng(&(ep->conf), mbedtls_test_random, NULL);

    TEST_ASSERT(mbedtls_ssl_conf_get_user_data_p(&ep->conf) == NULL);
    TEST_EQUAL(mbedtls_ssl_conf_get_user_data_n(&ep->conf), 0);
    TEST_ASSERT(mbedtls_ssl_get_user_data_p(&ep->ssl) == NULL);
    TEST_EQUAL(mbedtls_ssl_get_user_data_n(&ep->ssl), 0);

    (void) mbedtls_test_rnd_std_rand(NULL,
                                     (void *) &user_data_n,
                                     sizeof(user_data_n));
    mbedtls_ssl_conf_set_user_data_n(&ep->conf, user_data_n);
    mbedtls_ssl_set_user_data_n(&ep->ssl, user_data_n);

    if (dtls_context != NULL) {
        TEST_ASSERT(mbedtls_test_message_socket_setup(input_queue, output_queue,
                                                      100, &(ep->socket),
                                                      dtls_context) == 0);
    } else {
        mbedtls_test_mock_socket_init(&(ep->socket));
    }

    /* Non-blocking callbacks without timeout */
    if (dtls_context != NULL) {
        mbedtls_ssl_set_bio(&(ep->ssl), dtls_context,
                            mbedtls_test_mock_tcp_send_msg,
                            mbedtls_test_mock_tcp_recv_msg,
                            NULL);
    } else {
        mbedtls_ssl_set_bio(&(ep->ssl), &(ep->socket),
                            mbedtls_test_mock_tcp_send_nb,
                            mbedtls_test_mock_tcp_recv_nb,
                            NULL);
    }

    ret = mbedtls_ssl_config_defaults(&(ep->conf), endpoint_type,
                                      (dtls_context != NULL) ?
                                      MBEDTLS_SSL_TRANSPORT_DATAGRAM :
                                      MBEDTLS_SSL_TRANSPORT_STREAM,
                                      MBEDTLS_SSL_PRESET_DEFAULT);
    TEST_ASSERT(ret == 0);

    if (MBEDTLS_SSL_IS_CLIENT == endpoint_type) {
        if (options->client_min_version != MBEDTLS_SSL_VERSION_UNKNOWN) {
            mbedtls_ssl_conf_min_tls_version(&(ep->conf),
                                             options->client_min_version);
        }

        if (options->client_max_version != MBEDTLS_SSL_VERSION_UNKNOWN) {
            mbedtls_ssl_conf_max_tls_version(&(ep->conf),
                                             options->client_max_version);
        }
    } else {
        if (options->server_min_version != MBEDTLS_SSL_VERSION_UNKNOWN) {
            mbedtls_ssl_conf_min_tls_version(&(ep->conf),
                                             options->server_min_version);
        }

        if (options->server_max_version != MBEDTLS_SSL_VERSION_UNKNOWN) {
            mbedtls_ssl_conf_max_tls_version(&(ep->conf),
                                             options->server_max_version);
        }
    }

    if (options->group_list != NULL) {
        mbedtls_ssl_conf_groups(&(ep->conf), options->group_list);
    }

    mbedtls_ssl_conf_authmode(&(ep->conf), MBEDTLS_SSL_VERIFY_REQUIRED);

#if defined(MBEDTLS_SSL_EARLY_DATA)
    mbedtls_ssl_conf_early_data(&(ep->conf), options->early_data);
#if defined(MBEDTLS_SSL_SRV_C)
    if (endpoint_type == MBEDTLS_SSL_IS_SERVER &&
        (options->max_early_data_size >= 0)) {
        mbedtls_ssl_conf_max_early_data_size(&(ep->conf),
                                             options->max_early_data_size);
    }
#endif
#if defined(MBEDTLS_SSL_ALPN)
    /* check that alpn_list contains at least one valid entry */
    if (options->alpn_list[0] != NULL) {
        mbedtls_ssl_conf_alpn_protocols(&(ep->conf), options->alpn_list);
    }
#endif
#endif

#if defined(MBEDTLS_SSL_CACHE_C) && defined(MBEDTLS_SSL_SRV_C)
    if (endpoint_type == MBEDTLS_SSL_IS_SERVER && options->cache != NULL) {
        mbedtls_ssl_conf_session_cache(&(ep->conf), options->cache,
                                       mbedtls_ssl_cache_get,
                                       mbedtls_ssl_cache_set);
    }
#endif

    ret = mbedtls_ssl_setup(&(ep->ssl), &(ep->conf));
    TEST_ASSERT(ret == 0);

#if defined(MBEDTLS_SSL_PROTO_DTLS) && defined(MBEDTLS_SSL_SRV_C)
    if (endpoint_type == MBEDTLS_SSL_IS_SERVER && dtls_context != NULL) {
        mbedtls_ssl_conf_dtls_cookies(&(ep->conf), NULL, NULL, NULL);
    }
#endif

#if defined(MBEDTLS_DEBUG_C)
#if defined(MBEDTLS_SSL_SRV_C)
    if (endpoint_type == MBEDTLS_SSL_IS_SERVER &&
        options->srv_log_fun != NULL) {
        mbedtls_ssl_conf_dbg(&(ep->conf), options->srv_log_fun,
                             options->srv_log_obj);
    }
#endif
#if defined(MBEDTLS_SSL_CLI_C)
    if (endpoint_type == MBEDTLS_SSL_IS_CLIENT &&
        options->cli_log_fun != NULL) {
        mbedtls_ssl_conf_dbg(&(ep->conf), options->cli_log_fun,
                             options->cli_log_obj);
    }
#endif
#endif /* MBEDTLS_DEBUG_C */

    ret = mbedtls_test_ssl_endpoint_certificate_init(ep, options->pk_alg,
                                                     options->opaque_alg,
                                                     options->opaque_alg2,
                                                     options->opaque_usage);
    TEST_ASSERT(ret == 0);

    TEST_EQUAL(mbedtls_ssl_conf_get_user_data_n(&ep->conf), user_data_n);
    mbedtls_ssl_conf_set_user_data_p(&ep->conf, ep);
    TEST_EQUAL(mbedtls_ssl_get_user_data_n(&ep->ssl), user_data_n);
    mbedtls_ssl_set_user_data_p(&ep->ssl, ep);

exit:
    return ret;
}

void mbedtls_test_ssl_endpoint_free(
    mbedtls_test_ssl_endpoint *ep,
    mbedtls_test_message_socket_context *context)
{
    test_ssl_endpoint_certificate_free(ep);

    mbedtls_ssl_free(&(ep->ssl));
    mbedtls_ssl_config_free(&(ep->conf));

    if (context != NULL) {
        mbedtls_test_message_socket_close(context);
    } else {
        mbedtls_test_mock_socket_close(&(ep->socket));
    }
}

int mbedtls_test_move_handshake_to_state(mbedtls_ssl_context *ssl,
                                         mbedtls_ssl_context *second_ssl,
                                         int state)
{
    enum { BUFFSIZE = 1024 };
    int max_steps = 1000;
    int ret = 0;

    if (ssl == NULL || second_ssl == NULL) {
        return MBEDTLS_ERR_SSL_BAD_INPUT_DATA;
    }

    /* Perform communication via connected sockets */
    while ((ssl->state != state) && (--max_steps >= 0)) {
        /* If /p second_ssl ends the handshake procedure before /p ssl then
         * there is no need to call the next step */
        if (!mbedtls_ssl_is_handshake_over(second_ssl)) {
            ret = mbedtls_ssl_handshake_step(second_ssl);
            if (ret != 0 && ret != MBEDTLS_ERR_SSL_WANT_READ &&
                ret != MBEDTLS_ERR_SSL_WANT_WRITE) {
                return ret;
            }
        }

        /* We only care about the \p ssl state and returns, so we call it last,
         * to leave the iteration as soon as the state is as expected. */
        ret = mbedtls_ssl_handshake_step(ssl);
        if (ret != 0 && ret != MBEDTLS_ERR_SSL_WANT_READ &&
            ret != MBEDTLS_ERR_SSL_WANT_WRITE) {
            return ret;
        }
    }

    return (max_steps >= 0) ? ret : -1;
}

#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED */

/*
 * Write application data. Increase write counter if necessary.
 */
static int mbedtls_ssl_write_fragment(mbedtls_ssl_context *ssl,
                                      unsigned char *buf, int buf_len,
                                      int *written,
                                      const int expected_fragments)
{
    int ret;
    /* Verify that calling mbedtls_ssl_write with a NULL buffer and zero length is
     * a valid no-op for TLS connections. */
    if (ssl->conf->transport != MBEDTLS_SSL_TRANSPORT_DATAGRAM) {
        TEST_ASSERT(mbedtls_ssl_write(ssl, NULL, 0) == 0);
    }

    ret = mbedtls_ssl_write(ssl, buf + *written, buf_len - *written);
    if (ret > 0) {
        *written += ret;
    }

    if (expected_fragments == 0) {
        /* Used for DTLS and the message size larger than MFL. In that case
         * the message can not be fragmented and the library should return
         * MBEDTLS_ERR_SSL_BAD_INPUT_DATA error. This error must be returned
         * to prevent a dead loop inside mbedtls_test_ssl_exchange_data(). */
        return ret;
    } else if (expected_fragments == 1) {
        /* Used for TLS/DTLS and the message size lower than MFL */
        TEST_ASSERT(ret == buf_len ||
                    ret == MBEDTLS_ERR_SSL_WANT_READ ||
                    ret == MBEDTLS_ERR_SSL_WANT_WRITE);
    } else {
        /* Used for TLS and the message size larger than MFL */
        TEST_ASSERT(expected_fragments > 1);
        TEST_ASSERT((ret >= 0 && ret <= buf_len) ||
                    ret == MBEDTLS_ERR_SSL_WANT_READ ||
                    ret == MBEDTLS_ERR_SSL_WANT_WRITE);
    }

    return 0;

exit:
    /* Some of the tests failed */
    return -1;
}

/*
 * Read application data and increase read counter and fragments counter
 * if necessary.
 */
static int mbedtls_ssl_read_fragment(mbedtls_ssl_context *ssl,
                                     unsigned char *buf, int buf_len,
                                     int *read, int *fragments,
                                     const int expected_fragments)
{
    int ret;
    /* Verify that calling mbedtls_ssl_write with a NULL buffer and zero length is
     * a valid no-op for TLS connections. */
    if (ssl->conf->transport != MBEDTLS_SSL_TRANSPORT_DATAGRAM) {
        TEST_ASSERT(mbedtls_ssl_read(ssl, NULL, 0) == 0);
    }

    ret = mbedtls_ssl_read(ssl, buf + *read, buf_len - *read);
    if (ret > 0) {
        (*fragments)++;
        *read += ret;
    }

    if (expected_fragments == 0) {
        TEST_ASSERT(ret == 0);
    } else if (expected_fragments == 1) {
        TEST_ASSERT(ret == buf_len ||
                    ret == MBEDTLS_ERR_SSL_WANT_READ ||
                    ret == MBEDTLS_ERR_SSL_WANT_WRITE);
    } else {
        TEST_ASSERT(expected_fragments > 1);
        TEST_ASSERT((ret >= 0 && ret <= buf_len) ||
                    ret == MBEDTLS_ERR_SSL_WANT_READ ||
                    ret == MBEDTLS_ERR_SSL_WANT_WRITE);
    }

    return 0;

exit:
    /* Some of the tests failed */
    return -1;
}

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)
static void set_ciphersuite(mbedtls_ssl_config *conf, const char *cipher,
                            int *forced_ciphersuite)
{
    const mbedtls_ssl_ciphersuite_t *ciphersuite_info;
    forced_ciphersuite[0] = mbedtls_ssl_get_ciphersuite_id(cipher);
    forced_ciphersuite[1] = 0;

    ciphersuite_info =
        mbedtls_ssl_ciphersuite_from_id(forced_ciphersuite[0]);

    TEST_ASSERT(ciphersuite_info != NULL);
    TEST_ASSERT(ciphersuite_info->min_tls_version <= conf->max_tls_version);
    TEST_ASSERT(ciphersuite_info->max_tls_version >= conf->min_tls_version);

    if (conf->max_tls_version > ciphersuite_info->max_tls_version) {
        conf->max_tls_version = (mbedtls_ssl_protocol_version) ciphersuite_info->max_tls_version;
    }
    if (conf->min_tls_version < ciphersuite_info->min_tls_version) {
        conf->min_tls_version = (mbedtls_ssl_protocol_version) ciphersuite_info->min_tls_version;
    }

    mbedtls_ssl_conf_ciphersuites(conf, forced_ciphersuite);

exit:
    return;
}
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED */

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED) && \
    defined(MBEDTLS_SSL_HANDSHAKE_WITH_PSK_ENABLED)  && \
    defined(MBEDTLS_SSL_SRV_C)
static int psk_dummy_callback(void *p_info, mbedtls_ssl_context *ssl,
                              const unsigned char *name, size_t name_len)
{
    (void) p_info;
    (void) ssl;
    (void) name;
    (void) name_len;

    return 0;
}
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED &&
          MBEDTLS_SSL_HANDSHAKE_WITH_PSK_ENABLED  &&
          MBEDTLS_SSL_SRV_C */

#if defined(MBEDTLS_SSL_PROTO_TLS1_2) && \
    defined(MBEDTLS_SSL_HAVE_CBC) && defined(MBEDTLS_SSL_HAVE_AES)
int mbedtls_test_psa_cipher_encrypt_helper(mbedtls_ssl_transform *transform,
                                           const unsigned char *iv,
                                           size_t iv_len,
                                           const unsigned char *input,
                                           size_t ilen,
                                           unsigned char *output,
                                           size_t *olen)
{
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;
    psa_cipher_operation_t cipher_op = PSA_CIPHER_OPERATION_INIT;
    size_t part_len;

    status = psa_cipher_encrypt_setup(&cipher_op,
                                      transform->psa_key_enc,
                                      transform->psa_alg);

    if (status != PSA_SUCCESS) {
        return PSA_TO_MBEDTLS_ERR(status);
    }

    status = psa_cipher_set_iv(&cipher_op, iv, iv_len);

    if (status != PSA_SUCCESS) {
        return PSA_TO_MBEDTLS_ERR(status);
    }

    status = psa_cipher_update(&cipher_op, input, ilen, output, ilen, olen);

    if (status != PSA_SUCCESS) {
        return PSA_TO_MBEDTLS_ERR(status);
    }

    status = psa_cipher_finish(&cipher_op, output + *olen, ilen - *olen,
                               &part_len);

    if (status != PSA_SUCCESS) {
        return PSA_TO_MBEDTLS_ERR(status);
    }

    *olen += part_len;
    return 0;
#else
    return mbedtls_cipher_crypt(&transform->cipher_ctx_enc,
                                iv, iv_len, input, ilen, output, olen);
#endif /* MBEDTLS_USE_PSA_CRYPTO */
}
#endif /* MBEDTLS_SSL_PROTO_TLS1_2 && MBEDTLS_SSL_HAVE_CBC &&
          MBEDTLS_SSL_HAVE_AES */

static void mbedtls_test_ssl_cipher_info_from_type(mbedtls_cipher_type_t cipher_type,
                                                   mbedtls_cipher_mode_t *cipher_mode,
                                                   size_t *key_bits, size_t *iv_len)
{
    switch (cipher_type) {
        case MBEDTLS_CIPHER_AES_128_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 128;
            *iv_len = 16;
            break;
        case MBEDTLS_CIPHER_AES_256_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 256;
            *iv_len = 16;
            break;
        case MBEDTLS_CIPHER_ARIA_128_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 128;
            *iv_len = 16;
            break;
        case MBEDTLS_CIPHER_ARIA_256_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 256;
            *iv_len = 16;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_128_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 128;
            *iv_len = 16;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_256_CBC:
            *cipher_mode = MBEDTLS_MODE_CBC;
            *key_bits = 256;
            *iv_len = 16;
            break;

        case MBEDTLS_CIPHER_AES_128_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 128;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_AES_192_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 192;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_AES_256_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 256;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_128_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 128;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_192_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 192;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_256_CCM:
            *cipher_mode = MBEDTLS_MODE_CCM;
            *key_bits = 256;
            *iv_len = 12;
            break;

        case MBEDTLS_CIPHER_AES_128_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 128;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_AES_192_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 192;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_AES_256_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 256;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_128_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 128;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_192_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 192;
            *iv_len = 12;
            break;
        case MBEDTLS_CIPHER_CAMELLIA_256_GCM:
            *cipher_mode = MBEDTLS_MODE_GCM;
            *key_bits = 256;
            *iv_len = 12;
            break;

        case MBEDTLS_CIPHER_CHACHA20_POLY1305:
            *cipher_mode = MBEDTLS_MODE_CHACHAPOLY;
            *key_bits = 256;
            *iv_len = 12;
            break;

        case MBEDTLS_CIPHER_NULL:
            *cipher_mode = MBEDTLS_MODE_STREAM;
            *key_bits = 0;
            *iv_len = 0;
            break;

        default:
            *cipher_mode = MBEDTLS_MODE_NONE;
            *key_bits = 0;
            *iv_len = 0;
    }
}

int mbedtls_test_ssl_build_transforms(mbedtls_ssl_transform *t_in,
                                      mbedtls_ssl_transform *t_out,
                                      int cipher_type, int hash_id,
                                      int etm, int tag_mode,
                                      mbedtls_ssl_protocol_version tls_version,
                                      size_t cid0_len,
                                      size_t cid1_len)
{
    mbedtls_cipher_mode_t cipher_mode = MBEDTLS_MODE_NONE;
    size_t key_bits = 0;
    int ret = 0;

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_key_type_t key_type;
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_algorithm_t alg;
    psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;
#else
    mbedtls_cipher_info_t const *cipher_info;
#endif

    size_t keylen, maclen, ivlen = 0;
    unsigned char *key0 = NULL, *key1 = NULL;
    unsigned char *md0 = NULL, *md1 = NULL;
    unsigned char iv_enc[16], iv_dec[16];

#if defined(MBEDTLS_SSL_DTLS_CONNECTION_ID)
    unsigned char cid0[SSL_CID_LEN_MIN];
    unsigned char cid1[SSL_CID_LEN_MIN];

    mbedtls_test_rnd_std_rand(NULL, cid0, sizeof(cid0));
    mbedtls_test_rnd_std_rand(NULL, cid1, sizeof(cid1));
#else
    ((void) cid0_len);
    ((void) cid1_len);
#endif /* MBEDTLS_SSL_DTLS_CONNECTION_ID */

    maclen = 0;
    mbedtls_test_ssl_cipher_info_from_type((mbedtls_cipher_type_t) cipher_type,
                                           &cipher_mode, &key_bits, &ivlen);

    /* Pick keys */
    keylen = key_bits / 8;
    /* Allocate `keylen + 1` bytes to ensure that we get
     * a non-NULL pointers from `mbedtls_calloc` even if
     * `keylen == 0` in the case of the NULL cipher. */
    CHK((key0 = mbedtls_calloc(1, keylen + 1)) != NULL);
    CHK((key1 = mbedtls_calloc(1, keylen + 1)) != NULL);
    memset(key0, 0x1, keylen);
    memset(key1, 0x2, keylen);

#if !defined(MBEDTLS_USE_PSA_CRYPTO)
    /* Pick cipher */
    cipher_info = mbedtls_cipher_info_from_type((mbedtls_cipher_type_t) cipher_type);
    CHK(cipher_info != NULL);
    CHK(mbedtls_cipher_info_get_iv_size(cipher_info) <= 16);
    CHK(mbedtls_cipher_info_get_key_bitlen(cipher_info) % 8 == 0);

    /* Setup cipher contexts */
    CHK(mbedtls_cipher_setup(&t_in->cipher_ctx_enc,  cipher_info) == 0);
    CHK(mbedtls_cipher_setup(&t_in->cipher_ctx_dec,  cipher_info) == 0);
    CHK(mbedtls_cipher_setup(&t_out->cipher_ctx_enc, cipher_info) == 0);
    CHK(mbedtls_cipher_setup(&t_out->cipher_ctx_dec, cipher_info) == 0);

#if defined(MBEDTLS_CIPHER_MODE_CBC)
    if (cipher_mode == MBEDTLS_MODE_CBC) {
        CHK(mbedtls_cipher_set_padding_mode(&t_in->cipher_ctx_enc,
                                            MBEDTLS_PADDING_NONE) == 0);
        CHK(mbedtls_cipher_set_padding_mode(&t_in->cipher_ctx_dec,
                                            MBEDTLS_PADDING_NONE) == 0);
        CHK(mbedtls_cipher_set_padding_mode(&t_out->cipher_ctx_enc,
                                            MBEDTLS_PADDING_NONE) == 0);
        CHK(mbedtls_cipher_set_padding_mode(&t_out->cipher_ctx_dec,
                                            MBEDTLS_PADDING_NONE) == 0);
    }
#endif /* MBEDTLS_CIPHER_MODE_CBC */

    CHK(mbedtls_cipher_setkey(&t_in->cipher_ctx_enc, key0,
                              (keylen << 3 > INT_MAX) ? INT_MAX : (int) keylen << 3,
                              MBEDTLS_ENCRYPT)
        == 0);
    CHK(mbedtls_cipher_setkey(&t_in->cipher_ctx_dec, key1,
                              (keylen << 3 > INT_MAX) ? INT_MAX : (int) keylen << 3,
                              MBEDTLS_DECRYPT)
        == 0);
    CHK(mbedtls_cipher_setkey(&t_out->cipher_ctx_enc, key1,
                              (keylen << 3 > INT_MAX) ? INT_MAX : (int) keylen << 3,
                              MBEDTLS_ENCRYPT)
        == 0);
    CHK(mbedtls_cipher_setkey(&t_out->cipher_ctx_dec, key0,
                              (keylen << 3 > INT_MAX) ? INT_MAX : (int) keylen << 3,
                              MBEDTLS_DECRYPT)
        == 0);
#endif /* !MBEDTLS_USE_PSA_CRYPTO */

    /* Setup MAC contexts */
#if defined(MBEDTLS_SSL_SOME_SUITES_USE_MAC)
    if (cipher_mode == MBEDTLS_MODE_CBC ||
        cipher_mode == MBEDTLS_MODE_STREAM) {
#if !defined(MBEDTLS_USE_PSA_CRYPTO)
        mbedtls_md_info_t const *md_info = mbedtls_md_info_from_type((mbedtls_md_type_t) hash_id);
        CHK(md_info != NULL);
#endif
        maclen = mbedtls_md_get_size_from_type((mbedtls_md_type_t) hash_id);
        CHK(maclen != 0);
        /* Pick hash keys */
        CHK((md0 = mbedtls_calloc(1, maclen)) != NULL);
        CHK((md1 = mbedtls_calloc(1, maclen)) != NULL);
        memset(md0, 0x5, maclen);
        memset(md1, 0x6, maclen);

#if defined(MBEDTLS_USE_PSA_CRYPTO)
        alg = mbedtls_md_psa_alg_from_type(hash_id);

        CHK(alg != 0);

        t_out->psa_mac_alg = PSA_ALG_HMAC(alg);
        t_in->psa_mac_alg = PSA_ALG_HMAC(alg);
        t_in->psa_mac_enc = MBEDTLS_SVC_KEY_ID_INIT;
        t_out->psa_mac_enc = MBEDTLS_SVC_KEY_ID_INIT;
        t_in->psa_mac_dec = MBEDTLS_SVC_KEY_ID_INIT;
        t_out->psa_mac_dec = MBEDTLS_SVC_KEY_ID_INIT;

        psa_reset_key_attributes(&attributes);
        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_SIGN_MESSAGE);
        psa_set_key_algorithm(&attributes, PSA_ALG_HMAC(alg));
        psa_set_key_type(&attributes, PSA_KEY_TYPE_HMAC);

        CHK(psa_import_key(&attributes,
                           md0, maclen,
                           &t_in->psa_mac_enc) == PSA_SUCCESS);

        CHK(psa_import_key(&attributes,
                           md1, maclen,
                           &t_out->psa_mac_enc) == PSA_SUCCESS);

        if (cipher_mode == MBEDTLS_MODE_STREAM ||
            etm == MBEDTLS_SSL_ETM_DISABLED) {
            /* mbedtls_ct_hmac() requires the key to be exportable */
            psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_EXPORT |
                                    PSA_KEY_USAGE_VERIFY_HASH);
        } else {
            psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_VERIFY_HASH);
        }

        CHK(psa_import_key(&attributes,
                           md1, maclen,
                           &t_in->psa_mac_dec) == PSA_SUCCESS);

        CHK(psa_import_key(&attributes,
                           md0, maclen,
                           &t_out->psa_mac_dec) == PSA_SUCCESS);
#else
        CHK(mbedtls_md_setup(&t_out->md_ctx_enc, md_info, 1) == 0);
        CHK(mbedtls_md_setup(&t_out->md_ctx_dec, md_info, 1) == 0);
        CHK(mbedtls_md_setup(&t_in->md_ctx_enc,  md_info, 1) == 0);
        CHK(mbedtls_md_setup(&t_in->md_ctx_dec,  md_info, 1) == 0);

        CHK(mbedtls_md_hmac_starts(&t_in->md_ctx_enc,
                                   md0, maclen) == 0);
        CHK(mbedtls_md_hmac_starts(&t_in->md_ctx_dec,
                                   md1, maclen) == 0);
        CHK(mbedtls_md_hmac_starts(&t_out->md_ctx_enc,
                                   md1, maclen) == 0);
        CHK(mbedtls_md_hmac_starts(&t_out->md_ctx_dec,
                                   md0, maclen) == 0);
#endif
    }
#else
    ((void) hash_id);
#endif /* MBEDTLS_SSL_SOME_SUITES_USE_MAC */


    /* Pick IV's (regardless of whether they
     * are being used by the transform). */
    memset(iv_enc, 0x3, sizeof(iv_enc));
    memset(iv_dec, 0x4, sizeof(iv_dec));

    /*
     * Setup transforms
     */

#if defined(MBEDTLS_SSL_ENCRYPT_THEN_MAC) && \
    defined(MBEDTLS_SSL_SOME_SUITES_USE_MAC)
    t_out->encrypt_then_mac = etm;
    t_in->encrypt_then_mac = etm;
#else
    ((void) etm);
#endif

    t_out->tls_version = tls_version;
    t_in->tls_version = tls_version;
    t_out->ivlen = ivlen;
    t_in->ivlen = ivlen;

    switch (cipher_mode) {
        case MBEDTLS_MODE_GCM:
        case MBEDTLS_MODE_CCM:
#if defined(MBEDTLS_SSL_PROTO_TLS1_3)
            if (tls_version == MBEDTLS_SSL_VERSION_TLS1_3) {
                t_out->fixed_ivlen = 12;
                t_in->fixed_ivlen  = 12;
            } else
#endif /* MBEDTLS_SSL_PROTO_TLS1_3 */
            {
                t_out->fixed_ivlen = 4;
                t_in->fixed_ivlen = 4;
            }
            t_out->maclen = 0;
            t_in->maclen = 0;
            switch (tag_mode) {
                case 0: /* Full tag */
                    t_out->taglen = 16;
                    t_in->taglen = 16;
                    break;
                case 1: /* Partial tag */
                    t_out->taglen = 8;
                    t_in->taglen = 8;
                    break;
                default:
                    ret = 1;
                    goto cleanup;
            }
            break;

        case MBEDTLS_MODE_CHACHAPOLY:
            t_out->fixed_ivlen = 12;
            t_in->fixed_ivlen = 12;
            t_out->maclen = 0;
            t_in->maclen = 0;
            switch (tag_mode) {
                case 0: /* Full tag */
                    t_out->taglen = 16;
                    t_in->taglen = 16;
                    break;
                case 1: /* Partial tag */
                    t_out->taglen = 8;
                    t_in->taglen = 8;
                    break;
                default:
                    ret = 1;
                    goto cleanup;
            }
            break;

        case MBEDTLS_MODE_STREAM:
        case MBEDTLS_MODE_CBC:
            t_out->fixed_ivlen = 0; /* redundant, must be 0 */
            t_in->fixed_ivlen = 0;  /* redundant, must be 0 */
            t_out->taglen = 0;
            t_in->taglen = 0;
            switch (tag_mode) {
                case 0: /* Full tag */
                    t_out->maclen = maclen;
                    t_in->maclen = maclen;
                    break;
                default:
                    ret = 1;
                    goto cleanup;
            }
            break;
        default:
            ret = 1;
            goto cleanup;
            break;
    }

    /* Setup IV's */

    memcpy(&t_in->iv_dec, iv_dec, sizeof(iv_dec));
    memcpy(&t_in->iv_enc, iv_enc, sizeof(iv_enc));
    memcpy(&t_out->iv_dec, iv_enc, sizeof(iv_enc));
    memcpy(&t_out->iv_enc, iv_dec, sizeof(iv_dec));

#if defined(MBEDTLS_SSL_DTLS_CONNECTION_ID)
    /* Add CID */
    memcpy(&t_in->in_cid,  cid0, cid0_len);
    memcpy(&t_in->out_cid, cid1, cid1_len);
    t_in->in_cid_len = (uint8_t) cid0_len;
    t_in->out_cid_len = (uint8_t) cid1_len;
    memcpy(&t_out->in_cid,  cid1, cid1_len);
    memcpy(&t_out->out_cid, cid0, cid0_len);
    t_out->in_cid_len = (uint8_t) cid1_len;
    t_out->out_cid_len = (uint8_t) cid0_len;
#endif /* MBEDTLS_SSL_DTLS_CONNECTION_ID */

#if defined(MBEDTLS_USE_PSA_CRYPTO)
    status = mbedtls_ssl_cipher_to_psa(cipher_type,
                                       t_in->taglen,
                                       &alg,
                                       &key_type,
                                       &key_bits);

    if (status != PSA_SUCCESS) {
        ret = PSA_TO_MBEDTLS_ERR(status);
        goto cleanup;
    }

    t_in->psa_alg = alg;
    t_out->psa_alg = alg;

    if (alg != MBEDTLS_SSL_NULL_CIPHER) {
        psa_reset_key_attributes(&attributes);
        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_ENCRYPT);
        psa_set_key_algorithm(&attributes, alg);
        psa_set_key_type(&attributes, key_type);

        status = psa_import_key(&attributes,
                                key0,
                                PSA_BITS_TO_BYTES(key_bits),
                                &t_in->psa_key_enc);

        if (status != PSA_SUCCESS) {
            ret = PSA_TO_MBEDTLS_ERR(status);
            goto cleanup;
        }

        status = psa_import_key(&attributes,
                                key1,
                                PSA_BITS_TO_BYTES(key_bits),
                                &t_out->psa_key_enc);

        if (status != PSA_SUCCESS) {
            ret = PSA_TO_MBEDTLS_ERR(status);
            goto cleanup;
        }

        psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DECRYPT);

        status = psa_import_key(&attributes,
                                key1,
                                PSA_BITS_TO_BYTES(key_bits),
                                &t_in->psa_key_dec);

        if (status != PSA_SUCCESS) {
            ret = PSA_TO_MBEDTLS_ERR(status);
            goto cleanup;
        }

        status = psa_import_key(&attributes,
                                key0,
                                PSA_BITS_TO_BYTES(key_bits),
                                &t_out->psa_key_dec);

        if (status != PSA_SUCCESS) {
            ret = PSA_TO_MBEDTLS_ERR(status);
            goto cleanup;
        }
    }
#endif /* MBEDTLS_USE_PSA_CRYPTO */

cleanup:

    mbedtls_free(key0);
    mbedtls_free(key1);

    mbedtls_free(md0);
    mbedtls_free(md1);

    return ret;
}

#if defined(MBEDTLS_SSL_SOME_SUITES_USE_MAC)
int mbedtls_test_ssl_prepare_record_mac(mbedtls_record *record,
                                        mbedtls_ssl_transform *transform_out)
{
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_mac_operation_t operation = PSA_MAC_OPERATION_INIT;
#endif

    /* Serialized version of record header for MAC purposes */
    unsigned char add_data[13];
    memcpy(add_data, record->ctr, 8);
    add_data[8] = record->type;
    add_data[9] = record->ver[0];
    add_data[10] = record->ver[1];
    add_data[11] = (record->data_len >> 8) & 0xff;
    add_data[12] = (record->data_len >> 0) & 0xff;

    /* MAC with additional data */
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    size_t sign_mac_length = 0;
    TEST_EQUAL(PSA_SUCCESS, psa_mac_sign_setup(&operation,
                                               transform_out->psa_mac_enc,
                                               transform_out->psa_mac_alg));
    TEST_EQUAL(PSA_SUCCESS, psa_mac_update(&operation, add_data, 13));
    TEST_EQUAL(PSA_SUCCESS, psa_mac_update(&operation,
                                           record->buf + record->data_offset,
                                           record->data_len));
    /* Use a temporary buffer for the MAC, because with the truncated HMAC
     * extension, there might not be enough room in the record for the
     * full-length MAC. */
    unsigned char mac[PSA_HASH_MAX_SIZE];
    TEST_EQUAL(PSA_SUCCESS, psa_mac_sign_finish(&operation,
                                                mac, sizeof(mac),
                                                &sign_mac_length));
#else
    TEST_EQUAL(0, mbedtls_md_hmac_update(&transform_out->md_ctx_enc, add_data, 13));
    TEST_EQUAL(0, mbedtls_md_hmac_update(&transform_out->md_ctx_enc,
                                         record->buf + record->data_offset,
                                         record->data_len));
    /* Use a temporary buffer for the MAC, because with the truncated HMAC
     * extension, there might not be enough room in the record for the
     * full-length MAC. */
    unsigned char mac[MBEDTLS_MD_MAX_SIZE];
    TEST_EQUAL(0, mbedtls_md_hmac_finish(&transform_out->md_ctx_enc, mac));
#endif
    memcpy(record->buf + record->data_offset + record->data_len, mac, transform_out->maclen);
    record->data_len += transform_out->maclen;

    return 0;

exit:
#if defined(MBEDTLS_USE_PSA_CRYPTO)
    psa_mac_abort(&operation);
#endif
    return -1;
}
#endif /* MBEDTLS_SSL_SOME_SUITES_USE_MAC */

#if defined(MBEDTLS_SSL_PROTO_TLS1_2)
int mbedtls_test_ssl_tls12_populate_session(mbedtls_ssl_session *session,
                                            int ticket_len,
                                            int endpoint_type,
                                            const char *crt_file)
{
    (void) ticket_len;

#if defined(MBEDTLS_HAVE_TIME)
    session->start = mbedtls_time(NULL) - 42;
#endif
    session->tls_version = MBEDTLS_SSL_VERSION_TLS1_2;

    TEST_ASSERT(endpoint_type == MBEDTLS_SSL_IS_CLIENT ||
                endpoint_type == MBEDTLS_SSL_IS_SERVER);

    session->endpoint = endpoint_type;
    session->ciphersuite = 0xabcd;
    session->id_len = sizeof(session->id);
    memset(session->id, 66, session->id_len);
    memset(session->master, 17, sizeof(session->master));

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED) && defined(MBEDTLS_FS_IO)
    if (crt_file != NULL && strlen(crt_file) != 0) {
        mbedtls_x509_crt tmp_crt;
        int ret;

        mbedtls_x509_crt_init(&tmp_crt);
        ret = mbedtls_x509_crt_parse_file(&tmp_crt, crt_file);
        if (ret != 0) {
            return ret;
        }

#if defined(MBEDTLS_SSL_KEEP_PEER_CERTIFICATE)
        /* Move temporary CRT. */
        session->peer_cert = mbedtls_calloc(1, sizeof(*session->peer_cert));
        if (session->peer_cert == NULL) {
            return -1;
        }
        *session->peer_cert = tmp_crt;
        memset(&tmp_crt, 0, sizeof(tmp_crt));
#else /* MBEDTLS_SSL_KEEP_PEER_CERTIFICATE */
        /* Calculate digest of temporary CRT. */
        session->peer_cert_digest =
            mbedtls_calloc(1, MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_LEN);
        if (session->peer_cert_digest == NULL) {
            return -1;
        }

#if defined(MBEDTLS_USE_PSA_CRYPTO)
        psa_algorithm_t psa_alg = mbedtls_md_psa_alg_from_type(
            MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_TYPE);
        size_t hash_size = 0;
        psa_status_t status = psa_hash_compute(
            psa_alg, tmp_crt.raw.p,
            tmp_crt.raw.len,
            session->peer_cert_digest,
            MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_LEN,
            &hash_size);
        ret = PSA_TO_MBEDTLS_ERR(status);
#else
        ret = mbedtls_md(mbedtls_md_info_from_type(
                             MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_TYPE),
                         tmp_crt.raw.p, tmp_crt.raw.len,
                         session->peer_cert_digest);
#endif /* MBEDTLS_USE_PSA_CRYPTO */
        if (ret != 0) {
            return ret;
        }
        session->peer_cert_digest_type =
            MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_TYPE;
        session->peer_cert_digest_len =
            MBEDTLS_SSL_PEER_CERT_DIGEST_DFL_LEN;
#endif /* MBEDTLS_SSL_KEEP_PEER_CERTIFICATE */

        mbedtls_x509_crt_free(&tmp_crt);
    }
#else /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED && MBEDTLS_FS_IO */
    (void) crt_file;
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED && MBEDTLS_FS_IO */
    session->verify_result = 0xdeadbeef;

#if defined(MBEDTLS_SSL_SESSION_TICKETS)
#if defined(MBEDTLS_SSL_CLI_C)
    if (ticket_len != 0) {
        session->ticket = mbedtls_calloc(1, ticket_len);
        if (session->ticket == NULL) {
            return -1;
        }
        memset(session->ticket, 33, ticket_len);
    }
    session->ticket_len = ticket_len;
    session->ticket_lifetime = 86401;
#endif /* MBEDTLS_SSL_CLI_C */

#if defined(MBEDTLS_SSL_SRV_C) && defined(MBEDTLS_HAVE_TIME)
    if (session->endpoint == MBEDTLS_SSL_IS_SERVER) {
        session->ticket_creation_time = mbedtls_ms_time() - 42;
    }
#endif
#endif /* MBEDTLS_SSL_SESSION_TICKETS */

#if defined(MBEDTLS_SSL_MAX_FRAGMENT_LENGTH)
    session->mfl_code = 1;
#endif
#if defined(MBEDTLS_SSL_ENCRYPT_THEN_MAC)
    session->encrypt_then_mac = 1;
#endif

exit:
    return 0;
}
#endif /* MBEDTLS_SSL_PROTO_TLS1_2 */

#if defined(MBEDTLS_SSL_PROTO_TLS1_3)
int mbedtls_test_ssl_tls13_populate_session(mbedtls_ssl_session *session,
                                            int ticket_len,
                                            int endpoint_type)
{
    ((void) ticket_len);
    session->tls_version = MBEDTLS_SSL_VERSION_TLS1_3;
    session->endpoint = endpoint_type == MBEDTLS_SSL_IS_CLIENT ?
                        MBEDTLS_SSL_IS_CLIENT : MBEDTLS_SSL_IS_SERVER;
    session->ciphersuite = 0xabcd;

#if defined(MBEDTLS_SSL_SESSION_TICKETS)
    session->ticket_age_add = 0x87654321;
    session->ticket_flags = 0x7;
    session->resumption_key_len = 32;
    memset(session->resumption_key, 0x99, sizeof(session->resumption_key));
#endif

#if defined(MBEDTLS_SSL_SRV_C)
    if (session->endpoint == MBEDTLS_SSL_IS_SERVER) {
#if defined(MBEDTLS_SSL_SESSION_TICKETS)
#if defined(MBEDTLS_SSL_EARLY_DATA) && defined(MBEDTLS_SSL_ALPN)
        int ret = mbedtls_ssl_session_set_ticket_alpn(session, "ALPNExample");
        if (ret != 0) {
            return -1;
        }
#endif
#if defined(MBEDTLS_HAVE_TIME)
        session->ticket_creation_time = mbedtls_ms_time() - 42;
#endif
#endif /* MBEDTLS_SSL_SESSION_TICKETS */
    }
#endif /* MBEDTLS_SSL_SRV_C */

#if defined(MBEDTLS_SSL_CLI_C)
    if (session->endpoint == MBEDTLS_SSL_IS_CLIENT) {
#if defined(MBEDTLS_SSL_SESSION_TICKETS)
#if defined(MBEDTLS_HAVE_TIME)
        session->ticket_reception_time = mbedtls_ms_time() - 40;
#endif
        session->ticket_lifetime = 0xfedcba98;

        session->ticket_len = ticket_len;
        if (ticket_len != 0) {
            session->ticket = mbedtls_calloc(1, ticket_len);
            if (session->ticket == NULL) {
                return -1;
            }
            memset(session->ticket, 33, ticket_len);
        }
#if defined(MBEDTLS_SSL_SERVER_NAME_INDICATION)
        char hostname[] = "hostname example";
        session->hostname = mbedtls_calloc(1, sizeof(hostname));
        if (session->hostname == NULL) {
            return -1;
        }
        memcpy(session->hostname, hostname, sizeof(hostname));
#endif
#endif /* MBEDTLS_SSL_SESSION_TICKETS */
    }
#endif /* MBEDTLS_SSL_CLI_C */

#if defined(MBEDTLS_SSL_EARLY_DATA)
    session->max_early_data_size = 0x87654321;
#endif /* MBEDTLS_SSL_EARLY_DATA */

#if defined(MBEDTLS_SSL_RECORD_SIZE_LIMIT)
    session->record_size_limit = 2048;
#endif

    return 0;
}
#endif /* MBEDTLS_SSL_PROTO_TLS1_3 */

int mbedtls_test_ssl_exchange_data(
    mbedtls_ssl_context *ssl_1,
    int msg_len_1, const int expected_fragments_1,
    mbedtls_ssl_context *ssl_2,
    int msg_len_2, const int expected_fragments_2)
{
    unsigned char *msg_buf_1 = malloc(msg_len_1);
    unsigned char *msg_buf_2 = malloc(msg_len_2);
    unsigned char *in_buf_1  = malloc(msg_len_2);
    unsigned char *in_buf_2  = malloc(msg_len_1);
    int msg_type, ret = -1;

    /* Perform this test with two message types. At first use a message
     * consisting of only 0x00 for the client and only 0xFF for the server.
     * At the second time use message with generated data */
    for (msg_type = 0; msg_type < 2; msg_type++) {
        int written_1 = 0;
        int written_2 = 0;
        int read_1 = 0;
        int read_2 = 0;
        int fragments_1 = 0;
        int fragments_2 = 0;

        if (msg_type == 0) {
            memset(msg_buf_1, 0x00, msg_len_1);
            memset(msg_buf_2, 0xff, msg_len_2);
        } else {
            int i, j = 0;
            for (i = 0; i < msg_len_1; i++) {
                msg_buf_1[i] = j++ & 0xFF;
            }
            for (i = 0; i < msg_len_2; i++) {
                msg_buf_2[i] = (j -= 5) & 0xFF;
            }
        }

        while (read_1 < msg_len_2 || read_2 < msg_len_1) {
            /* ssl_1 sending */
            if (msg_len_1 > written_1) {
                ret = mbedtls_ssl_write_fragment(ssl_1, msg_buf_1,
                                                 msg_len_1, &written_1,
                                                 expected_fragments_1);
                if (expected_fragments_1 == 0) {
                    /* This error is expected when the message is too large and
                     * cannot be fragmented */
                    TEST_ASSERT(ret == MBEDTLS_ERR_SSL_BAD_INPUT_DATA);
                    msg_len_1 = 0;
                } else {
                    TEST_ASSERT(ret == 0);
                }
            }

            /* ssl_2 sending */
            if (msg_len_2 > written_2) {
                ret = mbedtls_ssl_write_fragment(ssl_2, msg_buf_2,
                                                 msg_len_2, &written_2,
                                                 expected_fragments_2);
                if (expected_fragments_2 == 0) {
                    /* This error is expected when the message is too large and
                     * cannot be fragmented */
                    TEST_ASSERT(ret == MBEDTLS_ERR_SSL_BAD_INPUT_DATA);
                    msg_len_2 = 0;
                } else {
                    TEST_ASSERT(ret == 0);
                }
            }

            /* ssl_1 reading */
            if (read_1 < msg_len_2) {
                ret = mbedtls_ssl_read_fragment(ssl_1, in_buf_1,
                                                msg_len_2, &read_1,
                                                &fragments_2,
                                                expected_fragments_2);
                TEST_ASSERT(ret == 0);
            }

            /* ssl_2 reading */
            if (read_2 < msg_len_1) {
                ret = mbedtls_ssl_read_fragment(ssl_2, in_buf_2,
                                                msg_len_1, &read_2,
                                                &fragments_1,
                                                expected_fragments_1);
                TEST_ASSERT(ret == 0);
            }
        }

        ret = -1;
        TEST_ASSERT(0 == memcmp(msg_buf_1, in_buf_2, msg_len_1));
        TEST_ASSERT(0 == memcmp(msg_buf_2, in_buf_1, msg_len_2));
        TEST_ASSERT(fragments_1 == expected_fragments_1);
        TEST_ASSERT(fragments_2 == expected_fragments_2);
    }

    ret = 0;

exit:
    free(msg_buf_1);
    free(in_buf_1);
    free(msg_buf_2);
    free(in_buf_2);

    return ret;
}

/*
 * Perform data exchanging between \p ssl_1 and \p ssl_2. Both of endpoints
 * must be initialized and connected beforehand.
 *
 * \retval  0 on success, otherwise error code.
 */
#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED) && \
    (defined(MBEDTLS_SSL_RENEGOTIATION)              || \
    defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH))
static int exchange_data(mbedtls_ssl_context *ssl_1,
                         mbedtls_ssl_context *ssl_2)
{
    return mbedtls_test_ssl_exchange_data(ssl_1, 256, 1,
                                          ssl_2, 256, 1);
}
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED &&
          (MBEDTLS_SSL_RENEGOTIATION              ||
          MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH) */

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)
static int check_ssl_version(
    mbedtls_ssl_protocol_version expected_negotiated_version,
    const mbedtls_ssl_context *ssl)
{
    const char *version_string = mbedtls_ssl_get_version(ssl);
    mbedtls_ssl_protocol_version version_number =
        mbedtls_ssl_get_version_number(ssl);

    TEST_EQUAL(ssl->tls_version, expected_negotiated_version);

    if (ssl->conf->transport == MBEDTLS_SSL_TRANSPORT_DATAGRAM) {
        TEST_EQUAL(version_string[0], 'D');
        ++version_string;
    }

    switch (expected_negotiated_version) {
        case MBEDTLS_SSL_VERSION_TLS1_2:
            TEST_EQUAL(version_number, MBEDTLS_SSL_VERSION_TLS1_2);
            TEST_ASSERT(strcmp(version_string, "TLSv1.2") == 0);
            break;

        case MBEDTLS_SSL_VERSION_TLS1_3:
            TEST_EQUAL(version_number, MBEDTLS_SSL_VERSION_TLS1_3);
            TEST_ASSERT(strcmp(version_string, "TLSv1.3") == 0);
            break;

        default:
            TEST_FAIL(
                "Version check not implemented for this protocol version");
    }

    return 1;

exit:
    return 0;
}
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED */

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)
void mbedtls_test_ssl_perform_handshake(
    mbedtls_test_handshake_test_options *options)
{
    /* forced_ciphersuite needs to last until the end of the handshake */
    int forced_ciphersuite[2];
    enum { BUFFSIZE = 17000 };
    mbedtls_test_ssl_endpoint client, server;
#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_PSK_ENABLED)
    const char *psk_identity = "foo";
#endif
#if defined(MBEDTLS_TIMING_C)
    mbedtls_timing_delay_context timer_client, timer_server;
#endif
#if defined(MBEDTLS_SSL_CONTEXT_SERIALIZATION)
    unsigned char *context_buf = NULL;
    size_t context_buf_len;
#endif
#if defined(MBEDTLS_SSL_RENEGOTIATION)
    int ret = -1;
#endif
    int expected_handshake_result = options->expected_handshake_result;

    MD_OR_USE_PSA_INIT();
    mbedtls_platform_zeroize(&client, sizeof(client));
    mbedtls_platform_zeroize(&server, sizeof(server));
    mbedtls_test_ssl_message_queue server_queue, client_queue;
    mbedtls_test_message_socket_context server_context, client_context;
    mbedtls_test_message_socket_init(&server_context);
    mbedtls_test_message_socket_init(&client_context);

#if defined(MBEDTLS_DEBUG_C)
    if (options->cli_log_fun || options->srv_log_fun) {
        mbedtls_debug_set_threshold(4);
    }
#endif

    /* Client side */
    if (options->dtls != 0) {
        TEST_ASSERT(mbedtls_test_ssl_endpoint_init(&client,
                                                   MBEDTLS_SSL_IS_CLIENT,
                                                   options, &client_context,
                                                   &client_queue,
                                                   &server_queue) == 0);
#if defined(MBEDTLS_TIMING_C)
        mbedtls_ssl_set_timer_cb(&client.ssl, &timer_client,
                                 mbedtls_timing_set_delay,
                                 mbedtls_timing_get_delay);
#endif
    } else {
        TEST_ASSERT(mbedtls_test_ssl_endpoint_init(&client,
                                                   MBEDTLS_SSL_IS_CLIENT,
                                                   options, NULL, NULL,
                                                   NULL) == 0);
    }

    if (strlen(options->cipher) > 0) {
        set_ciphersuite(&client.conf, options->cipher, forced_ciphersuite);
    }

    /* Server side */
    if (options->dtls != 0) {
        TEST_ASSERT(mbedtls_test_ssl_endpoint_init(&server,
                                                   MBEDTLS_SSL_IS_SERVER,
                                                   options, &server_context,
                                                   &server_queue,
                                                   &client_queue) == 0);
#if defined(MBEDTLS_TIMING_C)
        mbedtls_ssl_set_timer_cb(&server.ssl, &timer_server,
                                 mbedtls_timing_set_delay,
                                 mbedtls_timing_get_delay);
#endif
    } else {
        TEST_ASSERT(mbedtls_test_ssl_endpoint_init(&server,
                                                   MBEDTLS_SSL_IS_SERVER,
                                                   options, NULL, NULL,
                                                   NULL) == 0);
    }

    mbedtls_ssl_conf_authmode(&server.conf, options->srv_auth_mode);

#if defined(MBEDTLS_SSL_MAX_FRAGMENT_LENGTH)
    TEST_ASSERT(mbedtls_ssl_conf_max_frag_len(&(server.conf),
                                              (unsigned char) options->mfl)
                == 0);
    TEST_ASSERT(mbedtls_ssl_conf_max_frag_len(&(client.conf),
                                              (unsigned char) options->mfl)
                == 0);
#else
    TEST_ASSERT(MBEDTLS_SSL_MAX_FRAG_LEN_NONE == options->mfl);
#endif /* MBEDTLS_SSL_MAX_FRAGMENT_LENGTH */

#if defined(MBEDTLS_SSL_HANDSHAKE_WITH_PSK_ENABLED)
    if (options->psk_str != NULL && options->psk_str->len > 0) {
        TEST_ASSERT(mbedtls_ssl_conf_psk(
                        &client.conf, options->psk_str->x,
                        options->psk_str->len,
                        (const unsigned char *) psk_identity,
                        strlen(psk_identity)) == 0);

        TEST_ASSERT(mbedtls_ssl_conf_psk(
                        &server.conf, options->psk_str->x,
                        options->psk_str->len,
                        (const unsigned char *) psk_identity,
                        strlen(psk_identity)) == 0);
#if defined(MBEDTLS_SSL_SRV_C)
        mbedtls_ssl_conf_psk_cb(&server.conf, psk_dummy_callback, NULL);
#endif
    }
#endif
#if defined(MBEDTLS_SSL_RENEGOTIATION)
    if (options->renegotiate) {
        mbedtls_ssl_conf_renegotiation(&(server.conf),
                                       MBEDTLS_SSL_RENEGOTIATION_ENABLED);
        mbedtls_ssl_conf_renegotiation(&(client.conf),
                                       MBEDTLS_SSL_RENEGOTIATION_ENABLED);

        mbedtls_ssl_conf_legacy_renegotiation(&(server.conf),
                                              options->legacy_renegotiation);
        mbedtls_ssl_conf_legacy_renegotiation(&(client.conf),
                                              options->legacy_renegotiation);
    }
#endif /* MBEDTLS_SSL_RENEGOTIATION */

    TEST_ASSERT(mbedtls_test_mock_socket_connect(&(client.socket),
                                                 &(server.socket),
                                                 BUFFSIZE) == 0);

#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
    if (options->resize_buffers != 0) {
        /* Ensure that the buffer sizes are appropriate before resizes */
        TEST_ASSERT(client.ssl.out_buf_len == MBEDTLS_SSL_OUT_BUFFER_LEN);
        TEST_ASSERT(client.ssl.in_buf_len == MBEDTLS_SSL_IN_BUFFER_LEN);
        TEST_ASSERT(server.ssl.out_buf_len == MBEDTLS_SSL_OUT_BUFFER_LEN);
        TEST_ASSERT(server.ssl.in_buf_len == MBEDTLS_SSL_IN_BUFFER_LEN);
    }
#endif

    if (options->expected_negotiated_version == MBEDTLS_SSL_VERSION_UNKNOWN) {
        expected_handshake_result = MBEDTLS_ERR_SSL_BAD_PROTOCOL_VERSION;
    }

    TEST_ASSERT(mbedtls_test_move_handshake_to_state(&(client.ssl),
                                                     &(server.ssl),
                                                     MBEDTLS_SSL_HANDSHAKE_OVER)
                ==  expected_handshake_result);

    if (expected_handshake_result != 0) {
        /* Connection will have failed by this point, skip to cleanup */
        goto exit;
    }

    TEST_ASSERT(mbedtls_ssl_is_handshake_over(&client.ssl) == 1);

    /* Make sure server state is moved to HANDSHAKE_OVER also. */
    TEST_EQUAL(mbedtls_test_move_handshake_to_state(&(server.ssl),
                                                    &(client.ssl),
                                                    MBEDTLS_SSL_HANDSHAKE_OVER),
               0);

    TEST_ASSERT(mbedtls_ssl_is_handshake_over(&server.ssl) == 1);
    /* Check that both sides have negotiated the expected version. */
    mbedtls_test_set_step(0);
    if (!check_ssl_version(options->expected_negotiated_version,
                           &client.ssl)) {
        goto exit;
    }

    mbedtls_test_set_step(1);
    if (!check_ssl_version(options->expected_negotiated_version,
                           &server.ssl)) {
        goto exit;
    }

    if (options->expected_ciphersuite != 0) {
        TEST_EQUAL(server.ssl.session->ciphersuite,
                   options->expected_ciphersuite);
    }

#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
    if (options->resize_buffers != 0) {
        /* A server, when using DTLS, might delay a buffer resize to happen
         * after it receives a message, so we force it. */
        TEST_ASSERT(exchange_data(&(client.ssl), &(server.ssl)) == 0);

        TEST_ASSERT(client.ssl.out_buf_len ==
                    mbedtls_ssl_get_output_buflen(&client.ssl));
        TEST_ASSERT(client.ssl.in_buf_len ==
                    mbedtls_ssl_get_input_buflen(&client.ssl));
        TEST_ASSERT(server.ssl.out_buf_len ==
                    mbedtls_ssl_get_output_buflen(&server.ssl));
        TEST_ASSERT(server.ssl.in_buf_len ==
                    mbedtls_ssl_get_input_buflen(&server.ssl));
    }
#endif

    if (options->cli_msg_len != 0 || options->srv_msg_len != 0) {
        /* Start data exchanging test */
        TEST_ASSERT(mbedtls_test_ssl_exchange_data(
                        &(client.ssl), options->cli_msg_len,
                        options->expected_cli_fragments,
                        &(server.ssl), options->srv_msg_len,
                        options->expected_srv_fragments)
                    == 0);
    }
#if defined(MBEDTLS_SSL_CONTEXT_SERIALIZATION)
    if (options->serialize == 1) {
        TEST_ASSERT(options->dtls == 1);

        TEST_ASSERT(mbedtls_ssl_context_save(&(server.ssl), NULL,
                                             0, &context_buf_len)
                    == MBEDTLS_ERR_SSL_BUFFER_TOO_SMALL);

        context_buf = mbedtls_calloc(1, context_buf_len);
        TEST_ASSERT(context_buf != NULL);

        TEST_ASSERT(mbedtls_ssl_context_save(&(server.ssl), context_buf,
                                             context_buf_len,
                                             &context_buf_len)
                    == 0);

        mbedtls_ssl_free(&(server.ssl));
        mbedtls_ssl_init(&(server.ssl));

        TEST_ASSERT(mbedtls_ssl_setup(&(server.ssl), &(server.conf)) == 0);

        mbedtls_ssl_set_bio(&(server.ssl), &server_context,
                            mbedtls_test_mock_tcp_send_msg,
                            mbedtls_test_mock_tcp_recv_msg,
                            NULL);

        mbedtls_ssl_set_user_data_p(&server.ssl, &server);

#if defined(MBEDTLS_TIMING_C)
        mbedtls_ssl_set_timer_cb(&server.ssl, &timer_server,
                                 mbedtls_timing_set_delay,
                                 mbedtls_timing_get_delay);
#endif
#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
        if (options->resize_buffers != 0) {
            /* Ensure that the buffer sizes are appropriate before resizes */
            TEST_ASSERT(server.ssl.out_buf_len == MBEDTLS_SSL_OUT_BUFFER_LEN);
            TEST_ASSERT(server.ssl.in_buf_len == MBEDTLS_SSL_IN_BUFFER_LEN);
        }
#endif
        TEST_ASSERT(mbedtls_ssl_context_load(&(server.ssl), context_buf,
                                             context_buf_len) == 0);

#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
        /* Validate buffer sizes after context deserialization */
        if (options->resize_buffers != 0) {
            TEST_ASSERT(server.ssl.out_buf_len ==
                        mbedtls_ssl_get_output_buflen(&server.ssl));
            TEST_ASSERT(server.ssl.in_buf_len ==
                        mbedtls_ssl_get_input_buflen(&server.ssl));
        }
#endif
        /* Retest writing/reading */
        if (options->cli_msg_len != 0 || options->srv_msg_len != 0) {
            TEST_ASSERT(mbedtls_test_ssl_exchange_data(
                            &(client.ssl), options->cli_msg_len,
                            options->expected_cli_fragments,
                            &(server.ssl), options->srv_msg_len,
                            options->expected_srv_fragments)
                        == 0);
        }
    }
#endif /* MBEDTLS_SSL_CONTEXT_SERIALIZATION */

#if defined(MBEDTLS_SSL_RENEGOTIATION)
    if (options->renegotiate) {
        /* Start test with renegotiation */
        TEST_ASSERT(server.ssl.renego_status ==
                    MBEDTLS_SSL_INITIAL_HANDSHAKE);
        TEST_ASSERT(client.ssl.renego_status ==
                    MBEDTLS_SSL_INITIAL_HANDSHAKE);

        /* After calling this function for the server, it only sends a handshake
         * request. All renegotiation should happen during data exchanging */
        TEST_ASSERT(mbedtls_ssl_renegotiate(&(server.ssl)) == 0);
        TEST_ASSERT(server.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_PENDING);
        TEST_ASSERT(client.ssl.renego_status ==
                    MBEDTLS_SSL_INITIAL_HANDSHAKE);

        TEST_ASSERT(exchange_data(&(client.ssl), &(server.ssl)) == 0);
        TEST_ASSERT(server.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_DONE);
        TEST_ASSERT(client.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_DONE);

        /* After calling mbedtls_ssl_renegotiate for the client,
         * all renegotiation should happen inside this function.
         * However in this test, we cannot perform simultaneous communication
         * between client and server so this function will return waiting error
         * on the socket. All rest of renegotiation should happen
         * during data exchanging */
        ret = mbedtls_ssl_renegotiate(&(client.ssl));
#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
        if (options->resize_buffers != 0) {
            /* Ensure that the buffer sizes are appropriate before resizes */
            TEST_ASSERT(client.ssl.out_buf_len == MBEDTLS_SSL_OUT_BUFFER_LEN);
            TEST_ASSERT(client.ssl.in_buf_len == MBEDTLS_SSL_IN_BUFFER_LEN);
        }
#endif
        TEST_ASSERT(ret == 0 ||
                    ret == MBEDTLS_ERR_SSL_WANT_READ ||
                    ret == MBEDTLS_ERR_SSL_WANT_WRITE);
        TEST_ASSERT(server.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_DONE);
        TEST_ASSERT(client.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_IN_PROGRESS);

        TEST_ASSERT(exchange_data(&(client.ssl), &(server.ssl)) == 0);
        TEST_ASSERT(server.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_DONE);
        TEST_ASSERT(client.ssl.renego_status ==
                    MBEDTLS_SSL_RENEGOTIATION_DONE);
#if defined(MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH)
        /* Validate buffer sizes after renegotiation */
        if (options->resize_buffers != 0) {
            TEST_ASSERT(client.ssl.out_buf_len ==
                        mbedtls_ssl_get_output_buflen(&client.ssl));
            TEST_ASSERT(client.ssl.in_buf_len ==
                        mbedtls_ssl_get_input_buflen(&client.ssl));
            TEST_ASSERT(server.ssl.out_buf_len ==
                        mbedtls_ssl_get_output_buflen(&server.ssl));
            TEST_ASSERT(server.ssl.in_buf_len ==
                        mbedtls_ssl_get_input_buflen(&server.ssl));
        }
#endif /* MBEDTLS_SSL_VARIABLE_BUFFER_LENGTH */
    }
#endif /* MBEDTLS_SSL_RENEGOTIATION */

    TEST_ASSERT(mbedtls_ssl_conf_get_user_data_p(&client.conf) == &client);
    TEST_ASSERT(mbedtls_ssl_get_user_data_p(&client.ssl) == &client);
    TEST_ASSERT(mbedtls_ssl_conf_get_user_data_p(&server.conf) == &server);
    TEST_ASSERT(mbedtls_ssl_get_user_data_p(&server.ssl) == &server);

exit:
    mbedtls_test_ssl_endpoint_free(&client,
                                   options->dtls != 0 ? &client_context : NULL);
    mbedtls_test_ssl_endpoint_free(&server,
                                   options->dtls != 0 ? &server_context : NULL);
#if defined(MBEDTLS_DEBUG_C)
    if (options->cli_log_fun || options->srv_log_fun) {
        mbedtls_debug_set_threshold(0);
    }
#endif
#if defined(MBEDTLS_SSL_CONTEXT_SERIALIZATION)
    if (context_buf != NULL) {
        mbedtls_free(context_buf);
    }
#endif
    MD_OR_USE_PSA_DONE();
}
#endif /* MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED */

#if defined(MBEDTLS_TEST_HOOKS)
int mbedtls_test_tweak_tls13_certificate_msg_vector_len(
    unsigned char *buf, unsigned char **end, int tweak,
    int *expected_result, mbedtls_ssl_chk_buf_ptr_args *args)
{
/*
 * The definition of the tweaks assume that the certificate list contains only
 * one certificate.
 */

/*
 * struct {
 *     opaque cert_data<1..2^24-1>;
 *     Extension extensions<0..2^16-1>;
 * } CertificateEntry;
 *
 * struct {
 *     opaque certificate_request_context<0..2^8-1>;
 *     CertificateEntry certificate_list<0..2^24-1>;
 * } Certificate;
 */
    unsigned char *p_certificate_request_context_len = buf;
    size_t certificate_request_context_len = buf[0];

    unsigned char *p_certificate_list_len =
        buf + 1 + certificate_request_context_len;
    unsigned char *certificate_list = p_certificate_list_len + 3;
    size_t certificate_list_len =
        MBEDTLS_GET_UINT24_BE(p_certificate_list_len, 0);

    unsigned char *p_cert_data_len = certificate_list;
    unsigned char *cert_data = p_cert_data_len + 3;
    size_t cert_data_len = MBEDTLS_GET_UINT24_BE(p_cert_data_len, 0);

    unsigned char *p_extensions_len = cert_data + cert_data_len;
    unsigned char *extensions = p_extensions_len + 2;
    size_t extensions_len = MBEDTLS_GET_UINT16_BE(p_extensions_len, 0);

    *expected_result = MBEDTLS_ERR_SSL_DECODE_ERROR;

    switch (tweak) {
        case 1:
            /* Failure when checking if the certificate request context length
             * and certificate list length can be read
             */
            *end = buf + 3;
            set_chk_buf_ptr_args(args, buf, *end, 4);
            break;

        case 2:
            /* Invalid certificate request context length.
             */
            *p_certificate_request_context_len =
                (unsigned char) certificate_request_context_len + 1;
            reset_chk_buf_ptr_args(args);
            break;

        case 3:
            /* Failure when checking if certificate_list data can be read. */
            MBEDTLS_PUT_UINT24_BE(certificate_list_len + 1,
                                  p_certificate_list_len, 0);
            set_chk_buf_ptr_args(args, certificate_list, *end,
                                 certificate_list_len + 1);
            break;

        case 4:
            /* Failure when checking if the cert_data length can be read. */
            MBEDTLS_PUT_UINT24_BE(2, p_certificate_list_len, 0);
            set_chk_buf_ptr_args(args, p_cert_data_len, certificate_list + 2, 3);
            break;

        case 5:
            /* Failure when checking if cert_data data can be read. */
            MBEDTLS_PUT_UINT24_BE(certificate_list_len - 3 + 1,
                                  p_cert_data_len, 0);
            set_chk_buf_ptr_args(args, cert_data,
                                 certificate_list + certificate_list_len,
                                 certificate_list_len - 3 + 1);
            break;

        case 6:
            /* Failure when checking if the extensions length can be read. */
            MBEDTLS_PUT_UINT24_BE(certificate_list_len - extensions_len - 1,
                                  p_certificate_list_len, 0);
            set_chk_buf_ptr_args(
                args, p_extensions_len,
                certificate_list + certificate_list_len - extensions_len - 1, 2);
            break;

        case 7:
            /* Failure when checking if extensions data can be read. */
            MBEDTLS_PUT_UINT16_BE(extensions_len + 1, p_extensions_len, 0);

            set_chk_buf_ptr_args(
                args, extensions,
                certificate_list + certificate_list_len, extensions_len + 1);
            break;

        default:
            return -1;
    }

    return 0;
}
#endif /* MBEDTLS_TEST_HOOKS */

/*
 * Functions for tests based on tickets. Implementations of the
 * write/parse ticket interfaces as defined by mbedtls_ssl_ticket_write/parse_t.
 * Basically same implementations as in ticket.c without the encryption. That
 * way we can tweak easily tickets characteristics to simulate misbehaving
 * peers.
 */
#if defined(MBEDTLS_SSL_SESSION_TICKETS)
int mbedtls_test_ticket_write(
    void *p_ticket, const mbedtls_ssl_session *session,
    unsigned char *start, const unsigned char *end,
    size_t *tlen, uint32_t *lifetime)
{
    int ret;
    ((void) p_ticket);

    if ((ret = mbedtls_ssl_session_save(session, start, end - start,
                                        tlen)) != 0) {
        return ret;
    }

    /* Maximum ticket lifetime as defined in RFC 8446 */
    *lifetime = 7 * 24 * 3600;

    return 0;
}

int mbedtls_test_ticket_parse(void *p_ticket, mbedtls_ssl_session *session,
                              unsigned char *buf, size_t len)
{
    ((void) p_ticket);

    return mbedtls_ssl_session_load(session, buf, len);
}
#endif /* MBEDTLS_SSL_SESSION_TICKETS */

#if defined(MBEDTLS_SSL_CLI_C) && defined(MBEDTLS_SSL_SRV_C) && \
    defined(MBEDTLS_SSL_PROTO_TLS1_3) && defined(MBEDTLS_SSL_SESSION_TICKETS) && \
    defined(MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED)
int mbedtls_test_get_tls13_ticket(
    mbedtls_test_handshake_test_options *client_options,
    mbedtls_test_handshake_test_options *server_options,
    mbedtls_ssl_session *session)
{
    int ret = -1;
    unsigned char buf[64];
    mbedtls_test_ssl_endpoint client_ep, server_ep;

    mbedtls_platform_zeroize(&client_ep, sizeof(client_ep));
    mbedtls_platform_zeroize(&server_ep, sizeof(server_ep));

    ret = mbedtls_test_ssl_endpoint_init(&client_ep, MBEDTLS_SSL_IS_CLIENT,
                                         client_options, NULL, NULL, NULL);
    TEST_EQUAL(ret, 0);

    ret = mbedtls_test_ssl_endpoint_init(&server_ep, MBEDTLS_SSL_IS_SERVER,
                                         server_options, NULL, NULL, NULL);
    TEST_EQUAL(ret, 0);

    mbedtls_ssl_conf_tls13_enable_signal_new_session_tickets(
        &client_ep.conf, MBEDTLS_SSL_TLS1_3_SIGNAL_NEW_SESSION_TICKETS_ENABLED);

    mbedtls_ssl_conf_session_tickets_cb(&server_ep.conf,
                                        mbedtls_test_ticket_write,
                                        mbedtls_test_ticket_parse,
                                        NULL);

    ret = mbedtls_test_mock_socket_connect(&(client_ep.socket),
                                           &(server_ep.socket), 1024);
    TEST_EQUAL(ret, 0);

    TEST_EQUAL(mbedtls_test_move_handshake_to_state(
                   &(server_ep.ssl), &(client_ep.ssl),
                   MBEDTLS_SSL_HANDSHAKE_OVER), 0);

    TEST_EQUAL(server_ep.ssl.handshake->new_session_tickets_count, 0);

    do {
        ret = mbedtls_ssl_read(&(client_ep.ssl), buf, sizeof(buf));
    } while (ret != MBEDTLS_ERR_SSL_RECEIVED_NEW_SESSION_TICKET);

    ret = mbedtls_ssl_get_session(&(client_ep.ssl), session);
    TEST_EQUAL(ret, 0);

exit:
    mbedtls_test_ssl_endpoint_free(&client_ep, NULL);
    mbedtls_test_ssl_endpoint_free(&server_ep, NULL);

    return ret;
}
#endif /* MBEDTLS_SSL_CLI_C && MBEDTLS_SSL_SRV_C &&
          MBEDTLS_SSL_PROTO_TLS1_3 && MBEDTLS_SSL_SESSION_TICKETS &&
          MBEDTLS_SSL_HANDSHAKE_WITH_CERT_ENABLED */

#endif /* MBEDTLS_SSL_TLS_C */
