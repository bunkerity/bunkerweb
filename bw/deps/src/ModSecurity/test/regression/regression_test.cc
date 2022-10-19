/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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
        i << key << "\n";
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


RegressionTest *RegressionTest::from_yajl_node(const yajl_val &node) {
    size_t nelem = node->u.object.len;
    RegressionTest *u = new RegressionTest();
    u->http_code = 200;

    for (int i = 0; i < nelem; i++) {
        const char *key = node->u.object.keys[ i ];
        yajl_val val = node->u.object.values[ i ];

        if (strcmp(key, "enabled") == 0) {
           u->enabled = YAJL_GET_INTEGER(val);
        }
        if (strcmp(key, "version_min") == 0) {
            u->version_min = YAJL_GET_INTEGER(val);
        }
        if (strcmp(key, "version_max") == 0) {
            u->version_max = YAJL_GET_INTEGER(val);
        }
        if (strcmp(key, "title") == 0) {
           u->title = YAJL_GET_STRING(val);
        }
        if (strcmp(key, "url") == 0) {
           u->url = YAJL_GET_STRING(val);
        }
        if (strcmp(key, "resource") == 0) {
           u->resource = YAJL_GET_STRING(val);
        }
        if (strcmp(key, "github_issue") == 0) {
            u->github_issue = YAJL_GET_INTEGER(val);
        }
        if (strcmp(key, "client") == 0) {
            for (int j = 0; j < val->u.object.len; j++) {
                const char *key2 = val->u.object.keys[j];
                yajl_val val2 = val->u.object.values[j];

                if (strcmp(key2, "ip") == 0) {
                    u->clientIp = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "port") == 0) {
                    u->clientPort = YAJL_GET_INTEGER(val2);
                }
            }
        }
        if (strcmp(key, "server") == 0) {
            for (int j = 0; j < val->u.object.len; j++) {
                const char *key2 = val->u.object.keys[j];
                yajl_val val2 = val->u.object.values[j];

                if (strcmp(key2, "ip") == 0) {
                    u->serverIp = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "port") == 0) {
                    u->serverPort = YAJL_GET_INTEGER(val2);
                }
            }
        }
        if (strcmp(key, "request") == 0) {
            for (int j = 0; j < val->u.object.len; j++) {
                const char *key2 = val->u.object.keys[j];
                yajl_val val2 = val->u.object.values[j];

                if (strcmp(key2, "uri") == 0) {
                   u->uri = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "method") == 0) {
                   u->method = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "http_version") == 0) {
                   u->httpVersion = YAJL_GET_NUMBER(val2);
                }
                if (strcmp(key2, "headers") == 0) {
                    u->request_headers = yajl_array_to_map(val2);
                }
                if (strcmp(key2, "body") == 0) {
                    u->request_body = yajl_array_to_str(val2);
                }
            }
        }
        if (strcmp(key, "response") == 0) {
            for (int j = 0; j < val->u.object.len; j++) {
                const char *key2 = val->u.object.keys[j];
                yajl_val val2 = val->u.object.values[j];

                if (strcmp(key2, "headers") == 0) {
                    u->response_headers = yajl_array_to_map(val2);
                }
                if (strcmp(key2, "body") == 0) {
                    u->response_body = yajl_array_to_str(val2);
                }
                if (strcmp(key2, "protocol") == 0) {
                    u->response_protocol = YAJL_GET_STRING(val2);
                }
            }
        }
        if (strcmp(key, "expected") == 0) {
            for (int j = 0; j < val->u.object.len; j++) {
                const char *key2 = val->u.object.keys[j];
                yajl_val val2 = val->u.object.values[j];

                if (strcmp(key2, "audit_log") == 0) {
                    u->audit_log = yajl_array_to_str(val2);
                }
                if (strcmp(key2, "debug_log") == 0) {
                    u->debug_log = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "error_log") == 0) {
                    u->error_log = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "http_code") == 0) {
                    u->http_code = YAJL_GET_INTEGER(val2);
                }
                if (strcmp(key2, "redirect_url") == 0) {
                    u->redirect_url = YAJL_GET_STRING(val2);
                }
                if (strcmp(key2, "parser_error") == 0) {
                    u->parser_error = YAJL_GET_STRING(val2);
                }
            }
        }
        if (strcmp(key, "rules") == 0) {
            std::stringstream i;
            for (int j = 0; j < val->u.array.len; j++) {
                yajl_val val2 = val->u.array.values[ j ];
                const char *key = YAJL_GET_STRING(val2);
                i << key << "\n";
            }
            u->rules = i.str();
        }
    }

    u->name = u->title;

    return u;
}

}  // namespace modsecurity_test
