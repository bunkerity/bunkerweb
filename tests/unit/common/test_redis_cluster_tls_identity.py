"""Exercise the shipped cosocket certificate identity check with real OpenSSL SANs."""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_cosocket_verifies_ip_sans_and_dns_without_cross_type_fallback(tmp_path, subsystem):
    if shutil.which("cc") is None:
        pytest.skip("C compiler unavailable")
    module = "lua-nginx-module" if subsystem == "http" else "stream-lua-nginx-module"
    source = (ROOT / f"src/deps/src/{module}/src/ngx_{subsystem}_lua_socket_tcp.c").read_text()
    handler = source[source.index(f"\nngx_{subsystem}_lua_ssl_handshake_handler(ngx_connection_t *c)") :]
    verifier = re.search(r"&& (\w+)\(c, &u->ssl_name\) != NGX_OK", handler).group(1)
    # The identity check must remain inside the verified handshake, after chain validation.
    assert handler.index("if (u->ssl_verify)") < handler.index("SSL_get_verify_result") < handler.index(f"&& {verifier}")
    assert "goto failed;" in handler[handler.index("if (rc != X509_V_OK)") : handler.index(f"&& {verifier}")]
    nginx = (ROOT / "src/deps/src/nginx/src/event/ngx_event_openssl.c").read_text()
    native = re.search(r"ngx_int_t\nngx_ssl_check_host\(.*?\n}\n", nginx, re.S).group()
    extra = ""
    if verifier != "ngx_ssl_check_host":
        extra = re.search(rf"static ngx_int_t\n{verifier}\(.*?\n}}\n", source, re.S).group()
    program = tmp_path / "identity.c"
    program.write_text(
        """
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <openssl/ssl.h>
#include <openssl/x509v3.h>
typedef unsigned char u_char;
typedef int ngx_int_t;
typedef struct { size_t len; u_char *data; } ngx_str_t;
typedef struct { X509 *connection; } ngx_ssl_connection_t;
typedef struct { ngx_ssl_connection_t *ssl; void *log; } ngx_connection_t;
#define NGX_OK 0
#define NGX_ERROR -1
#define NGX_INET6_ADDRSTRLEN 45
#define ngx_memcpy memcpy
#define ngx_strlen(s) strlen((const char *) s)
#define ngx_log_debug0(...) ((void) 0)
#undef SSL_get_peer_certificate
#define SSL_get_peer_certificate(c) ((c) ? X509_dup(c) : NULL)
"""
        + native
        + extra
        + """
static X509 *certificate(const char *san, const char *cn) {
    X509 *cert = X509_new();
    X509_set_version(cert, 2);
    ASN1_INTEGER_set(X509_get_serialNumber(cert), 1);
    X509_gmtime_adj(X509_getm_notBefore(cert), 0);
    X509_gmtime_adj(X509_getm_notAfter(cert), 3600);
    EVP_PKEY *key = EVP_PKEY_Q_keygen(NULL, NULL, "EC", "prime256v1");
    X509_set_pubkey(cert, key);
    X509_NAME_add_entry_by_txt(X509_get_subject_name(cert), "CN", MBSTRING_ASC,
                              (const unsigned char *) cn, -1, -1, 0);
    X509_set_issuer_name(cert, X509_get_subject_name(cert));
    if (san) {
        X509_EXTENSION *ext = X509V3_EXT_conf_nid(NULL, NULL, NID_subject_alt_name, san);
        X509_add_ext(cert, ext, -1);
        X509_EXTENSION_free(ext);
    }
    X509_sign(cert, key, EVP_sha256());
    EVP_PKEY_free(key);
    return cert;
}
static int check_length(X509 *cert, const char *name, size_t length) {
    ngx_ssl_connection_t ssl = {cert};
    ngx_connection_t connection = {&ssl, NULL};
    ngx_str_t identity = {length, (u_char *) name};
    return VERIFIER(&connection, &identity) == NGX_OK;
}
static int check(X509 *cert, const char *name) {
    return check_length(cert, name, strlen(name));
}
#define EXPECT(condition, message) do { if (!(condition)) { puts(message); return 1; } } while (0)
int main(void) {
    X509 *ip = certificate("IP:192.0.2.10,IP:2001:db8::10", "unrelated.example");
    EXPECT(check(ip, "192.0.2.10"), "valid IPv4 SAN rejected");
    EXPECT(check(ip, "2001:0db8:0:0:0:0:0:10"), "valid IPv6 SAN rejected");
    EXPECT(!check(ip, "192.0.2.11"), "wrong IP accepted");
    EXPECT(!check(ip, "redis.example"), "DNS name accepted by IP-only SAN");
    const char invalid[] = "192.0.2.10\\0.other.example";
    EXPECT(!check_length(ip, invalid, sizeof(invalid) - 1), "embedded NUL accepted");
    EXPECT(check_length(ip, "192.0.2.10ignored", 10), "length-delimited IP rejected");
    X509_free(ip);
    X509 *dns = certificate("DNS:redis.example,DNS:192.0.2.10,DNS:2001:db8::10", "192.0.2.10");
    EXPECT(check(dns, "redis.example"), "valid DNS SAN rejected");
    EXPECT(!check(dns, "other.example"), "wrong DNS accepted");
    EXPECT(!check(dns, "192.0.2.10"), "numeric DNS SAN accepted as IP SAN");
    EXPECT(!check(dns, "2001:db8::10"), "IPv6 DNS SAN accepted as IP SAN");
    X509_free(dns);
    X509 *cn = certificate(NULL, "192.0.2.10");
    EXPECT(!check(cn, "192.0.2.10"), "numeric CN accepted as IP SAN");
    X509_free(cn);
    EXPECT(!check(NULL, "192.0.2.10"), "missing certificate accepted");
    puts("OK");
    return 0;
}
""".replace("VERIFIER", verifier)
    )
    binary = tmp_path / "identity"
    compile_result = subprocess.run(
        [
            "cc",
            "-Wall",
            "-Wextra",
            "-Werror",
            *shlex.split(os.environ.get("CPPFLAGS", "")),
            str(program),
            *shlex.split(os.environ.get("LDFLAGS", "")),
            "-lssl",
            "-lcrypto",
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
    )
    if "openssl/ssl.h: No such file" in compile_result.stderr or "cannot find -lssl" in compile_result.stderr:
        pytest.skip("OpenSSL development headers/libraries unavailable")
    assert compile_result.returncode == 0, compile_result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "OK"
