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

#ifdef MSC_WITH_CURL
#include <curl/curl.h>
#endif

#include <iostream>
#include <fstream>
#include <string>
#include <functional>

#ifndef SRC_UTILS_HTTPS_CLIENT_H_
#define SRC_UTILS_HTTPS_CLIENT_H_

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace Utils {


class HttpsClient {
 public:
    HttpsClient()
        : content(""),
        error(""),
        m_key(""),
        m_requestBody(""),
        m_requestType("") { }

    bool download(const std::string &uri);
    std::string content;

    static size_t handle(char * data, size_t size, size_t nmemb, void * p);
    size_t handle_impl(char * data, size_t size, size_t nmemb);
    void setKey(const std::string& key);
    void setRequestType(const std::string& requestType);
    void setRequestBody(const std::string& requestType);

    std::string error;
 private:
    std::string m_key;
    std::string m_requestBody;
    std::string m_requestType;
};


}  // namespace Utils
}  // namespace modsecurity

#endif  // SRC_UTILS_HTTPS_CLIENT_H_
