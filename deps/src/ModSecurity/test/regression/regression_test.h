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

#include <yajl/yajl_tree.h>

#include <iostream>
#include <sstream>
#include <unordered_map>
#include <map>
#include <vector>
#include <string>
#include <utility>

#ifndef TEST_REGRESSION_REGRESSION_TEST_H_
#define TEST_REGRESSION_REGRESSION_TEST_H_

namespace modsecurity_test {


class RegressionTest {
 public:
    static RegressionTest *from_yajl_node(const yajl_val &);

    std::string print();
    std::string filename;
    std::string name;
    std::string title;

    std::string rules;

    std::string url;
    int enabled;
    int version_min;
    int version_max;
    int github_issue;

    std::vector<std::pair<std::string, std::string>> request_headers;
    std::vector<std::pair<std::string, std::string>> response_headers;
    std::string request_body;
    std::string response_body;
    std::string response_protocol;

    std::string audit_log;
    std::string debug_log;
    std::string error_log;
    std::string parser_error;

    std::string clientIp;
    std::string serverIp;
    int clientPort;
    int serverPort;

    std::string method;
    std::string httpVersion;
    std::string uri;
    std::string resource;

    static inline std::string yajl_array_to_str(const yajl_val &node);
    static inline std::vector<std::string> yajl_array_to_vec_str(
        const yajl_val &node);
    static inline std::vector<std::pair<std::string, std::string>>
        yajl_array_to_map(const yajl_val &node);

    int http_code;
    std::string redirect_url;
};


class RegressionTestResult {
 public:
    RegressionTestResult() :
      passed(false),
      skipped(false),
      disabled(false),
      test(NULL) { }

    bool passed;
    bool skipped;
    bool disabled;
    RegressionTest *test;
    std::stringstream reason;
};


}  // namespace modsecurity_test

#endif  // TEST_REGRESSION_REGRESSION_TEST_H_
