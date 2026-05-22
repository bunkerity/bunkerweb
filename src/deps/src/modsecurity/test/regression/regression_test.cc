/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#include "test/regression/regression_test.h"

#include <string.h>

#include <sstream>
#include <unordered_map>
#include <string>
#include <algorithm>
#include <memory>

#ifdef WITH_YAJL
#include <yajl/yajl_gen.h>
#endif

namespace modsecurity_test {

std::string RegressionTest::print() {
    std::stringstream i;

#if 0
    i << KRED << "Test failed." << RESET << " From: " \
    i << this->filename << std::endl;
    i << "{" << std::endl;
    i << "  \"ret\": \"" << this->ret << "\"" << std::endl;
    i << "  \"type\": \"" << this->type << "\"" << std::endl;
    i << "  \"name\": \"" << this->name << "\"" << std::endl;
    i << "  \"input\": \"" << this->input << "\"" << std::endl;
    i << "  \"param\": \"" << this->param << "\"" << std::endl;
    i << "}" << std::endl;
    i << "Expecting: " << this->ret << " - operator returned: " << \
        this->obtained << std::endl;
#endif
    return i.str();
}


inline std::string RegressionTest::yajl_array_to_str(const yajl_val &node) {
    std::stringstream i;
    for (int z = 0; z < node->u.array.len; z++) {
        yajl_val val3 = node->u.array.values[z];
        const char *key = YAJL_GET_STRING(val3);
        i << key;
    }
    return i.str();
}


inline std::vector<std::string> RegressionTest::yajl_array_to_vec_str(
    const yajl_val &node) {
    std::vector<std::string> vec;
    for (int z = 0; z < node->u.array.len; z++) {
        yajl_val val3 = node->u.array.values[z];
        const char *key = YAJL_GET_STRING(val3);
        vec.push_back(key);
    }
    return vec;
}


inline std::vector<std::pair<std::string, std::string>>
    RegressionTest::yajl_array_to_map(const yajl_val &node) {
    std::vector<std::pair<std::string, std::string>> vec;
    for (int z = 0; z < node->u.object.len; z++) {
        const char *key = node->u.object.keys[z];
        yajl_val val3 = node->u.object.values[z];
        const char *value = YAJL_GET_STRING(val3);
        std::pair<std::string, std::string> a(key, value);
        vec.push_back(a);
    }
    return vec;
}

static inline void set_int_from_yajl(int &dest, std::string_view want_key, std::string_view key, const yajl_val &val) {
    if (key == want_key) {
        dest = YAJL_GET_INTEGER(val);
    }
}

static inline void set_opt_int_from_yajl(std::optional<int> &dest, std::string_view want_key, std::string_view key, const yajl_val &val) {
    if (key == want_key) {
        dest = YAJL_GET_INTEGER(val);
    }
}

static inline void set_string_from_yajl(std::string &dest, std::string_view want_key, std::string_view key, const yajl_val &val) {
    if (key == want_key) {
        dest = YAJL_GET_STRING(val);
    }
}

std::unique_ptr<RegressionTest> RegressionTest::from_yajl_node(const yajl_val &node) {
    size_t nelem = node->u.object.len;
    auto u = std::make_unique<RegressionTest>();
    u->http_code = 200;

    for (int i = 0; i < nelem; i++) {
        const char *key = node->u.object.keys[ i ];
        yajl_val val = node->u.object.values[ i ];

        set_int_from_yajl(u->enabled, "enabled", key, val);
        set_int_from_yajl(u->version_min, "version_min", key, val);
        set_opt_int_from_yajl(u->version_max, "version_max", key, val);
        set_string_from_yajl(u->title, "title", key, val);
        set_string_from_yajl(u->url, "url", key, val);
        set_string_from_yajl(u->resource, "resource", key, val);
        set_opt_int_from_yajl(u->github_issue, "github_issue", key, val);
        if (strcmp(key, "client") == 0) {
            u->update_client_from_yajl_node(val);
        }
        if (strcmp(key, "server") == 0) {
            u->update_server_from_yajl_node(val);
        }
        if (strcmp(key, "request") == 0) {
            u->update_request_from_yajl_node(val);
        }
        if (strcmp(key, "response") == 0) {
            u->update_response_from_yajl_node(val);
        }
        if (strcmp(key, "expected") == 0) {
            u->update_expected_from_yajl_node(val);
        }
        if (strcmp(key, "rules") == 0) {
            u->update_rules_from_yajl_node(val);
        }
    }

    u->name = u->title;

    return u;
}

void RegressionTest::update_client_from_yajl_node(const yajl_val &val) {
    for (int j = 0; j < val->u.object.len; j++) {
        const char *key2 = val->u.object.keys[j];
        yajl_val val2 = val->u.object.values[j];

        set_string_from_yajl(clientIp, "ip", key2, val2);
        set_int_from_yajl(clientPort, "port", key2, val2);
    }
}

void RegressionTest::update_server_from_yajl_node(const yajl_val &val) {
    for (int j = 0; j < val->u.object.len; j++) {
        const char *key2 = val->u.object.keys[j];
        yajl_val val2 = val->u.object.values[j];

        set_string_from_yajl(serverIp, "ip", key2, val2);
        set_int_from_yajl(serverPort, "port", key2, val2);
        set_string_from_yajl(hostname, "hostname", key2, val2);
    }
}

void RegressionTest::update_request_from_yajl_node(const yajl_val &val) {
    for (int j = 0; j < val->u.object.len; j++) {
        const char *key2 = val->u.object.keys[j];
        yajl_val val2 = val->u.object.values[j];

        set_string_from_yajl(uri, "uri", key2, val2);
        set_string_from_yajl(method, "method", key2, val2);
        if (strcmp(key2, "http_version") == 0) {
            httpVersion = YAJL_GET_NUMBER(val2);
        }
        if (strcmp(key2, "headers") == 0) {
            request_headers = yajl_array_to_map(val2);
        }
        if (strcmp(key2, "body") == 0) {
            request_body = yajl_array_to_str(val2);
            request_body_lines = yajl_array_to_vec_str(val2);
        }
    }
}

void RegressionTest::update_response_from_yajl_node(const yajl_val &val) {
    for (int j = 0; j < val->u.object.len; j++) {
        const char *key2 = val->u.object.keys[j];
        yajl_val val2 = val->u.object.values[j];

        if (strcmp(key2, "headers") == 0) {
            response_headers = yajl_array_to_map(val2);
        }
        if (strcmp(key2, "body") == 0) {
            response_body = yajl_array_to_str(val2);
            response_body_lines = yajl_array_to_vec_str(val2);
        }
        set_string_from_yajl(response_protocol, "protocol", key2, val2);
    }
}

void RegressionTest::update_expected_from_yajl_node(const yajl_val &val) {
    for (int j = 0; j < val->u.object.len; j++) {
        const char *key2 = val->u.object.keys[j];
        yajl_val val2 = val->u.object.values[j];

        set_string_from_yajl(audit_log, "audit_log", key2, val2);
        set_string_from_yajl(debug_log, "debug_log", key2, val2);
        set_string_from_yajl(error_log, "error_log", key2, val2);
        set_int_from_yajl(http_code, "http_code", key2, val2);
        set_string_from_yajl(redirect_url, "redirect_url", key2, val2);
        set_string_from_yajl(parser_error, "parser_error", key2, val2);
    }
}

void RegressionTest::update_rules_from_yajl_node(const yajl_val &val) {
    std::stringstream si;
    for (int j = 0; j < val->u.array.len; j++) {
        yajl_val val2 = val->u.array.values[ j ];
        const char *keyj = YAJL_GET_STRING(val2);
        si << keyj << "\n";
    }
    rules = si.str();
    rules_lines = yajl_array_to_vec_str(val);
}


constexpr char ascii_tolower(char c) {
    return 'A' <= c && c <= 'Z' ? (c + ('a' - 'A')) : c;
}

bool iequals_ascii(std::string_view a, std::string_view b) {
    return a.size() == b.size() &&
        std::equal(a.begin(), a.end(), b.begin(), b.end(),
            [](char x, char y) {
                return ascii_tolower(x) == ascii_tolower(y);
            });
}

static bool has_chunked_header(const std::vector<std::pair<std::string, std::string>> &headers) {
    return std::any_of(std::begin(headers), std::end(headers),
        [](const auto &header) {
            const auto &[name, value]{header};
            return iequals_ascii(name, "Transfer-Encoding") && iequals_ascii(value, "chunked");
        });
}

static void update_content_length(std::vector<std::pair<std::string, std::string>> &headers, size_t length) {
    if (has_chunked_header(headers)) {
        return;
    }

    bool has_content_length = false;
    for (auto &[name, value] : headers) {
        if (iequals_ascii(name, "Content-Length")) {
            value = std::to_string(length);
            has_content_length = true;
        }
    }
    if (!has_content_length) {
        headers.emplace_back(std::pair{"Content-Length", std::to_string(length)});
    }
}

void RegressionTest::update_content_lengths() {
    update_content_length(request_headers, request_body.size());
    update_content_length(response_headers, response_body.size());
}

std::unique_ptr<RegressionTests> RegressionTests::from_yajl_node(const yajl_val &node) {
    auto u = std::make_unique<RegressionTests>();
    size_t num_tests = node->u.array.len;
    for (int i = 0; i < num_tests; i++) {
        yajl_val obj = node->u.array.values[i];
        u->tests.emplace_back(std::move(RegressionTest::from_yajl_node(obj)));
    }
    return u;
}

void RegressionTests::update_content_lengths() {
    for (auto & test : tests) {
        test->update_content_lengths();
    }
}

#ifdef WITH_YAJL

static yajl_gen_status gen_string_view(yajl_gen g, std::string_view s) {
    return yajl_gen_string(g, reinterpret_cast<const unsigned char *>(s.data()), s.length());
}

static yajl_gen_status gen_key_str(yajl_gen g, std::string_view key, std::string_view val) {
    if (auto s{gen_string_view(g, key)}; s != yajl_gen_status_ok) {
        return s;
    }
    return gen_string_view(g, val);
}

static yajl_gen_status gen_key_str_if_non_empty(yajl_gen g, std::string_view key, std::string_view val) {
    if (val.empty()) {
        return yajl_gen_status_ok;
    }
    return gen_key_str(g, key, val);
}

static yajl_gen_status gen_key_int(yajl_gen g, std::string_view key, int val) {
    if (auto s{gen_string_view(g, key)}; s != yajl_gen_status_ok) {
        return s;
    }
    return yajl_gen_integer(g, val);
}

static yajl_gen_status gen_key_opt_int(yajl_gen g, std::string_view key, std::optional<int> val) {
    if (!val.has_value()) {
        return yajl_gen_status_ok;
    }
    return gen_key_int(g, key, val.value());
}

static yajl_gen_status gen_key_int_if_non_zero(yajl_gen g, std::string_view key, int val) {
    if (val == 0) {
        return yajl_gen_status_ok;
    }
    return gen_key_int(g, key, val);
}

static yajl_gen_status gen_key_number(yajl_gen g, std::string_view key, std::string_view raw_val) {
    if (auto s{gen_string_view(g, key)}; s != yajl_gen_status_ok) {
        return s;
    }
    return yajl_gen_number(g, reinterpret_cast<const char *>(raw_val.data()), raw_val.length());
}

static yajl_gen_status gen_key_str_array(yajl_gen g, std::string_view key, const std::vector<std::string> &lines) {
    if (auto s{gen_string_view(g, key)}; s != yajl_gen_status_ok) {
        return s;
    }
    if (auto s{yajl_gen_array_open(g)}; s != yajl_gen_status_ok) {
        return s;
    }
    for (const auto &line : lines) {
        if (auto s{gen_string_view(g, line)}; s != yajl_gen_status_ok) {
            return s;
        }
    }
    return yajl_gen_array_close(g);
}

static yajl_gen_status gen_key_headers(yajl_gen g, std::string_view key, const std::vector<std::pair<std::string, std::string>> &headers) {
    if (auto s{gen_string_view(g, key)}; s != yajl_gen_status_ok) {
        return s;
    }
    if (auto s{yajl_gen_map_open(g)}; s != yajl_gen_status_ok) {
        return s;
    }
    for (const auto &[name, value] : headers) {
        if (auto s{gen_key_str(g, name, value)}; s != yajl_gen_status_ok) {
            return s;
        }
    }
    return yajl_gen_map_close(g);
}

std::string RegressionTests::toJSON() const {
    const unsigned char *buf;
    size_t len;
    yajl_gen g;

    g = yajl_gen_alloc(NULL);
    if (g == NULL) {
        return "";
    }
    yajl_gen_config(g, yajl_gen_beautify, 1);
    yajl_gen_config(g, yajl_gen_indent_string, "  ");

    yajl_gen_array_open(g);
    for (const auto &t : tests) {
        yajl_gen_map_open(g);
        gen_key_int(g, "enabled", t->enabled);
        gen_key_int(g, "version_min", t->version_min);
        gen_key_opt_int(g, "version_max", t->version_max);
        gen_key_str(g, "title", t->title);
        gen_key_str_if_non_empty(g, "url", t->url);
        gen_key_str_if_non_empty(g, "resource", t->resource);
        gen_key_opt_int(g, "github_issue", t->github_issue);

        gen_string_view(g, "client");
        yajl_gen_map_open(g);
        gen_key_str(g, "ip", t->clientIp);
        gen_key_int(g, "port", t->clientPort);
        yajl_gen_map_close(g);

        gen_string_view(g, "server");
        yajl_gen_map_open(g);
        gen_key_str(g, "ip", t->serverIp);
        gen_key_int(g, "port", t->serverPort);
        yajl_gen_map_close(g);

        gen_string_view(g, "request");
        yajl_gen_map_open(g);
        gen_key_headers(g, "headers", t->request_headers);
        gen_key_str(g, "uri", t->uri);
        gen_key_str(g, "method", t->method);
        if (!t->httpVersion.empty()) {
            gen_key_number(g, "http_version", t->httpVersion);
        }

        auto request_body_lines{t->request_body_lines};
        if (request_body_lines.empty()) {
            request_body_lines.emplace_back("");
        }
        gen_key_str_array(g, "body", request_body_lines);

        yajl_gen_map_close(g);

        gen_string_view(g, "response");
        yajl_gen_map_open(g);
        gen_key_headers(g, "headers", t->response_headers);

        auto response_body_lines{t->response_body_lines};
        if (response_body_lines.empty()) {
            response_body_lines.emplace_back("");
        }
        gen_key_str_array(g, "body", response_body_lines);

        gen_key_str_if_non_empty(g, "protocol", t->response_protocol);
        yajl_gen_map_close(g);

        gen_string_view(g, "expected");
        yajl_gen_map_open(g);
        gen_key_str_if_non_empty(g, "audit_log", t->audit_log);
        gen_key_str_if_non_empty(g, "debug_log", t->debug_log);
        gen_key_str_if_non_empty(g, "error_log", t->error_log);
        gen_key_int(g, "http_code", t->http_code);
        gen_key_str_if_non_empty(g, "redirect_url", t->redirect_url);
        gen_key_str_if_non_empty(g, "parser_error", t->parser_error);
        yajl_gen_map_close(g);

        gen_key_str_array(g, "rules", t->rules_lines);

        yajl_gen_map_close(g);
    }
    yajl_gen_array_close(g);

    yajl_gen_get_buf(g, &buf, &len);
    std::string s{reinterpret_cast<const char*>(buf), len};
    yajl_gen_free(g);
    return s;
}

#endif // WITH_YAJL

}  // namespace modsecurity_test
